from django.shortcuts import render
from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .face_utils import FaceRecognitionEngine, OPENCV_AVAILABLE
from attendance.models import AttendanceRecord, AttendanceSettings, PresenceTracking
from enrollment.models import Employee
from django.utils import timezone
import threading
import json
import time
from datetime import datetime, timedelta, date
import io

if OPENCV_AVAILABLE:
    import cv2
else:
    cv2 = None


# Global variables for camera and recognition engine
camera = None
camera_lock = threading.Lock()
recognition_engine = None
last_recognized = {}  # Track last recognition time for each employee
streaming_active = False  # Track if streaming should continue


def initialize_recognition_engine():
    """Initialize face recognition engine with encodings from database"""
    global recognition_engine
    if not OPENCV_AVAILABLE:
        return None
    if recognition_engine is None:
        recognition_engine = FaceRecognitionEngine()
        count = recognition_engine.load_encodings_from_db()
        print(f"Loaded {count} face encodings from database")
    return recognition_engine


def get_camera():
    """Get or create camera instance"""
    global camera
    if not OPENCV_AVAILABLE:
        return None
    with camera_lock:
        if camera is None or not camera.isOpened():
            # Try multiple camera backends
            for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, 0]:
                camera = cv2.VideoCapture(0, backend) if backend != 0 else cv2.VideoCapture(0)
                if camera.isOpened():
                    # Set camera properties for better quality
                    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    camera.set(cv2.CAP_PROP_FPS, 30)
                    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    print(f"Camera initialized successfully with backend: {backend}")
                    break
            else:
                print("Failed to open camera with any backend")
                camera = None
    return camera


def release_camera():
    """Release camera resource"""
    global camera
    with camera_lock:
        if camera is not None:
            camera.release()
            camera = None


def generate_error_frame(message):
    """Generate an error frame with a message"""
    import numpy as np
    
    # Create a black frame with error message
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Add text to frame
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame, "Camera Error", (180, 200), font, 1.5, (0, 0, 255), 3)
    cv2.putText(frame, message, (100, 250), font, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, "Please check camera connection", (120, 300), font, 0.7, (255, 255, 255), 1)
    
    # Encode to JPEG
    ret, buffer = cv2.imencode('.jpg', frame)
    if ret:
        return buffer.tobytes()
    return None


def generate_frames():
    """Generate video frames with face recognition - direct camera reading"""
    global last_recognized, camera
    
    try:
        engine = initialize_recognition_engine()
        
        # Get camera directly
        cam = get_camera()
        if cam is None or not cam.isOpened():
            print("ERROR: Could not open camera")
            error_frame = generate_error_frame("Camera not available")
            if error_frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + error_frame + b'\r\n')
            return
        
        print("Starting video stream - camera opened successfully")
        
        frame_count = 0
        process_every_n_frames = 2  # Process every 2nd frame for better responsiveness
        consecutive_failures = 0
        max_failures = 30
        
        while True:
            # Read frame directly from camera
            ret, frame = cam.read()
            
            if not ret or frame is None:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    print("Too many consecutive failures, stopping stream")
                    error_frame = generate_error_frame("Camera read failed")
                    if error_frame:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + error_frame + b'\r\n')
                    break
                time.sleep(0.05)
                continue
            
            consecutive_failures = 0
            frame_count += 1
            
            # Process recognition every N frames
            if frame_count % process_every_n_frames == 0:
                results = engine.recognize_faces(frame)
                
                # Auto-mark attendance for recognized faces
                current_time = timezone.now()
                for result in results:
                    if result['employee_id'] and result['name'] != "Unknown":
                        # Check if we should mark attendance (avoid duplicates within 5 minutes)
                        employee_id = result['employee_id']
                        last_time = last_recognized.get(employee_id)
                        
                        if last_time is None or (current_time - last_time).seconds > 300:  # 5 minutes
                            # Mark attendance
                            try:
                                employee = Employee.objects.get(id=employee_id)
                                today = current_time.date()
                                
                                record, created = AttendanceRecord.objects.get_or_create(
                                    employee=employee,
                                    date=today,
                                    defaults={'status': 'ABSENT'}
                                )
                                
                                if not record.check_in:
                                    record.check_in = current_time
                                    record.checkin_method = 'ADMIN'  # Mark as admin tracking
                                    
                                    # Determine if late
                                    settings_obj = AttendanceSettings.objects.first()
                                    if settings_obj:
                                        standard_time = datetime.combine(today, settings_obj.standard_check_in_time)
                                        standard_time = timezone.make_aware(standard_time)
                                        late_threshold = standard_time + timedelta(minutes=settings_obj.late_threshold_minutes)
                                        
                                        if current_time > late_threshold:
                                            record.status = 'LATE'
                                        else:
                                            record.status = 'PRESENT'
                                    else:
                                        record.status = 'PRESENT'
                                    
                                    record.save()
                                    print(f"Auto check-in: {employee.full_name} at {current_time}")
                                
                                last_recognized[employee_id] = current_time
                            except Exception as e:
                                print(f"Error marking attendance: {e}")
                
                # Draw results on frame
                frame = engine.draw_results(frame, results)
            
            # Encode frame to JPEG with higher quality to reduce artifacts
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                print("ERROR: Failed to encode frame")
                continue
                
            frame_bytes = buffer.tobytes()
            
            # Simpler multipart format - more compatible
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            # Slower frame rate for more stable streaming - 15 FPS
            time.sleep(0.066)
    
    except GeneratorExit:
        print("Client disconnected, stopping stream...")
    except Exception as e:
        print(f"ERROR in generate_frames: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Stopping video stream...")


def live_recognition(request):
    """Live recognition page"""
    from django.utils import timezone
    return render(request, 'recognition/live_recognition.html', {
        'timestamp': timezone.now().timestamp()
    })


def video_feed(request):
    """Video streaming route - synchronous streaming"""
    global streaming_active
    streaming_active = True
    
    def stream_wrapper():
        """Wrapper to handle streaming properly"""
        try:
            for chunk in generate_frames():
                if not streaming_active:
                    break
                yield chunk
        except Exception as e:
            print(f"Stream error: {e}")
        finally:
            print("Stream wrapper finished")
    
    response = StreamingHttpResponse(
        stream_wrapper(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Accel-Buffering'] = 'no'
    return response


@csrf_exempt
def reload_encodings(request):
    """Reload face encodings from database"""
    if request.method == 'POST':
        global recognition_engine
        from enrollment.models import FaceEncoding
        
        # Check if there are any face encodings in database
        total_encodings = FaceEncoding.objects.count()
        print(f"Total face encodings in database: {total_encodings}")
        
        if total_encodings == 0:
            return JsonResponse({
                'success': False,
                'message': 'No face encodings found in database. Please enroll employees first.'
            })
        
        # Reinitialize engine
        recognition_engine = None
        engine = initialize_recognition_engine()
        
        if engine.is_trained:
            return JsonResponse({
                'success': True,
                'message': f'Successfully reloaded {total_encodings} face encodings. Recognizer trained.',
                'is_trained': True
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'Found {total_encodings} encodings but recognizer failed to train. Check console for errors.',
                'is_trained': False
            })
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@csrf_exempt
def stop_camera(request):
    """Stop camera (accepts POST or GET; CSRF exempt for sendBeacon)"""
    global streaming_active
    if request.method not in ['POST', 'GET']:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)

    # Auto check-out all employees who checked in via ADMIN tracking today
    today = timezone.now().date()
    now = timezone.now()
    
    checked_out_count = 0
    records_to_checkout = AttendanceRecord.objects.filter(
        date=today,
        checkin_method='ADMIN',
        check_in__isnull=False,
        is_checked_out=False
    )
    
    for record in records_to_checkout:
        record.check_out = now
        record.is_checked_out = True
        record.remarks = (record.remarks or '') + ' [Auto checkout when admin stopped tracking]'
        record.calculate_work_hours()
        record.save()
        checked_out_count += 1
    
    # Signal streaming to stop
    streaming_active = False
    release_camera()
    
    message = 'Camera stopped'
    if checked_out_count > 0:
        message += f' and {checked_out_count} employee(s) checked out'
    
    return JsonResponse({'success': True, 'message': message})


def get_recognition_status(request):
    """Get recent recognition and attendance status"""
    from django.db.models import Count, Q
    
    today = timezone.now().date()
    
    # Get recent recognitions (last 5)
    recent_records = AttendanceRecord.objects.filter(
        date=today,
        check_in__isnull=False
    ).order_by('-check_in')[:5]
    
    recognitions = []
    for record in recent_records:
        recognitions.append({
            'employee_id': record.employee.employee_id,
            'name': record.employee.full_name,
            'status': record.status,
            'time': record.check_in.strftime('%I:%M %p')
        })
    
    # Get attendance counts
    present_count = AttendanceRecord.objects.filter(
        date=today,
        status__in=['PRESENT', 'LATE']
    ).count()
    
    total_employees = Employee.objects.filter(is_active=True).count()
    absent_count = total_employees - present_count
    
    return JsonResponse({
        'success': True,
        'recent_recognitions': recognitions,
        'present_count': present_count,
        'absent_count': absent_count
    })


def test_camera(request):
    """Test if camera is accessible"""
    try:
        global camera
        temporary_cam = None
        with camera_lock:
            # If camera already opened by the app, reuse it for test
            if camera is not None and camera.isOpened():
                cam = camera
            else:
                # Try the same backends we use elsewhere
                for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, 0]:
                    temporary_cam = cv2.VideoCapture(0, backend) if backend != 0 else cv2.VideoCapture(0)
                    if temporary_cam.isOpened():
                        cam = temporary_cam
                        break
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Camera could not be opened. Please check if it is connected and free.'
                    })

        success, frame = cam.read()

        # If we opened a temporary camera, release it so we don't steal the device
        if temporary_cam:
            temporary_cam.release()

        if not success or frame is None:
            return JsonResponse({
                'success': False,
                'message': 'Camera opened but could not read a frame.'
            })
        
        return JsonResponse({
            'success': True,
            'message': f'Camera is working. Frame size: {frame.shape[1]}x{frame.shape[0]}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error accessing camera: {str(e)}'
        })


def recognition_settings(request):
    """Admin settings page for face recognition parameters"""
    global recognition_engine
    
    # Get current settings from the engine
    if recognition_engine is None:
        initialize_recognition_engine()
    
    # Current settings
    current_settings = {
        'recognition_threshold': getattr(recognition_engine, 'recognition_threshold', 65),
        'scale_factor': 1.1,
        'min_neighbors': 5,
        'min_face_size': 80,
        'cooldown_seconds': 300,  # 5 minutes
    }
    
    # Get attendance settings
    try:
        attendance_settings = AttendanceSettings.objects.first()
        if attendance_settings:
            current_settings['work_start_time'] = attendance_settings.work_start_time.strftime('%H:%M')
            current_settings['late_threshold_minutes'] = attendance_settings.late_threshold_minutes
            current_settings['work_end_time'] = attendance_settings.standard_check_out_time.strftime('%H:%M')
            current_settings['full_day_hours'] = attendance_settings.full_day_hours
            current_settings['half_day_hours'] = attendance_settings.half_day_hours
        else:
            current_settings['work_start_time'] = '09:00'
            current_settings['late_threshold_minutes'] = 15
            current_settings['work_end_time'] = '18:00'
            current_settings['full_day_hours'] = 8
            current_settings['half_day_hours'] = 4
    except:
        current_settings['work_start_time'] = '09:00'
        current_settings['late_threshold_minutes'] = 15
        current_settings['work_end_time'] = '18:00'
        current_settings['full_day_hours'] = 8
        current_settings['half_day_hours'] = 4
    
    # Get all employees for individual settings
    employees = Employee.objects.filter(is_active=True).order_by('first_name', 'last_name')
    
    return render(request, 'recognition/settings.html', {
        'settings': current_settings,
        'employees': employees,
    })


@csrf_exempt
def update_settings(request):
    """Update recognition settings via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'})
    
    try:
        data = json.loads(request.body)
        setting_name = data.get('setting')
        value = data.get('value')
        
        global recognition_engine
        if recognition_engine is None:
            initialize_recognition_engine()
        
        # Update recognition engine settings
        if setting_name == 'recognition_threshold':
            recognition_engine.recognition_threshold = int(value)
            message = f'Recognition threshold updated to {value}'
        
        elif setting_name == 'cooldown_seconds':
            # This would need to be stored globally or in database
            global COOLDOWN_SECONDS
            COOLDOWN_SECONDS = int(value)
            message = f'Cooldown updated to {value} seconds'
        
        elif setting_name == 'work_start_time':
            settings_obj, created = AttendanceSettings.objects.get_or_create(id=1)
            settings_obj.work_start_time = datetime.strptime(value, '%H:%M').time()
            settings_obj.save()
            message = f'Work start time updated to {value}'
        
        elif setting_name == 'work_end_time':
            settings_obj, created = AttendanceSettings.objects.get_or_create(id=1)
            settings_obj.standard_check_out_time = datetime.strptime(value, '%H:%M').time()
            settings_obj.save()
            message = f'Work end time updated to {value}'
        
        elif setting_name == 'late_threshold_minutes':
            settings_obj, created = AttendanceSettings.objects.get_or_create(id=1)
            settings_obj.late_threshold_minutes = int(value)
            settings_obj.save()
            message = f'Late threshold updated to {value} minutes'
        
        elif setting_name == 'full_day_hours':
            settings_obj, created = AttendanceSettings.objects.get_or_create(id=1)
            settings_obj.full_day_hours = float(value)
            settings_obj.save()
            message = f'Full day hours updated to {value}'
        
        elif setting_name == 'half_day_hours':
            settings_obj, created = AttendanceSettings.objects.get_or_create(id=1)
            settings_obj.half_day_hours = float(value)
            settings_obj.save()
            message = f'Half day hours updated to {value}'
        
        else:
            return JsonResponse({'success': False, 'message': f'Unknown setting: {setting_name}'})
        
        return JsonResponse({'success': True, 'message': message})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
def update_employee_hours(request):
    """Update individual employee working hours via AJAX or POST"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'})
    
    try:
        # Handle both JSON and form data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        employee_id = data.get('employee_id')
        employee = Employee.objects.get(id=employee_id)
        
        use_custom = data.get('use_custom_hours')
        if isinstance(use_custom, str):
            use_custom = use_custom.lower() in ['true', 'on', '1']
        
        employee.use_custom_hours = use_custom
        
        if use_custom:
            # Support both naming conventions (from attendance page and settings page)
            custom_check_in = data.get('check_in_time') or data.get('custom_check_in_time')
            custom_check_out = data.get('check_out_time') or data.get('custom_check_out_time')
            custom_full_day = data.get('full_day_hours') or data.get('custom_full_day_hours')
            custom_half_day = data.get('half_day_hours') or data.get('custom_half_day_hours')
            
            employee.custom_check_in_time = custom_check_in if custom_check_in else None
            employee.custom_check_out_time = custom_check_out if custom_check_out else None
            employee.custom_full_day_hours = float(custom_full_day) if custom_full_day else None
            employee.custom_half_day_hours = float(custom_half_day) if custom_half_day else None
        else:
            employee.custom_check_in_time = None
            employee.custom_check_out_time = None
            employee.custom_full_day_hours = None
            employee.custom_half_day_hours = None
        
        employee.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Settings for {employee.full_name} updated successfully!'
        })
        
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
def run_presence_scan(request):
    """
    Run a single presence scan to check all employees.
    This is used for the auto-absent/auto-checkout feature.
    
    Logic:
    - 1st not detected: Mark as "Not Present" (warning)
    - 3rd consecutive not detected: 
        - If no check-in today -> Mark as ABSENT
        - If already checked in -> Auto check-out
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'})
    
    try:
        engine = initialize_recognition_engine()
        cam = get_camera()
        
        if cam is None or not cam.isOpened():
            return JsonResponse({'success': False, 'message': 'Camera not available'})
        
        # Capture multiple frames and detect faces
        detected_employee_ids = set()
        
        # Take 5 frames over 2 seconds for better accuracy
        for _ in range(5):
            ret, frame = cam.read()
            if ret and frame is not None:
                results = engine.recognize_faces(frame)
                for result in results:
                    if result['employee_id'] and result['name'] != "Unknown":
                        detected_employee_ids.add(result['employee_id'])
            time.sleep(0.4)
        
        # Get all active employees with enrolled faces
        from enrollment.models import FaceEncoding
        enrolled_employee_ids = FaceEncoding.objects.values_list('employee_id', flat=True).distinct()
        all_employees = Employee.objects.filter(id__in=enrolled_employee_ids, is_active=True)
        
        today = date.today()
        current_time = timezone.now()
        scan_results = {
            'present': [],
            'not_present_warning': [],
            'marked_absent': [],
            'auto_checked_out': [],
            'total_scanned': all_employees.count(),
            'total_detected': len(detected_employee_ids)
        }
        
        for employee in all_employees:
            # Get or create presence tracking for today
            tracking, created = PresenceTracking.objects.get_or_create(
                employee=employee,
                date=today,
                defaults={'scan_count': 0, 'not_present_count': 0}
            )
            
            tracking.scan_count += 1
            tracking.last_scan = current_time
            
            # Get attendance record for today
            attendance, att_created = AttendanceRecord.objects.get_or_create(
                employee=employee,
                date=today,
                defaults={'status': 'ABSENT'}
            )
            
            if employee.id in detected_employee_ids:
                # Employee detected - reset not present count
                tracking.reset_not_present_count()
                scan_results['present'].append({
                    'id': employee.id,
                    'name': employee.full_name,
                    'status': 'PRESENT'
                })
                
                # Mark check-in if not already
                if not attendance.check_in:
                    attendance.check_in = current_time
                    attendance.checkin_method = 'ADMIN'
                    
                    # Determine if late
                    settings_obj = AttendanceSettings.objects.first()
                    if settings_obj:
                        standard_time = datetime.combine(today, settings_obj.standard_check_in_time)
                        standard_time = timezone.make_aware(standard_time)
                        late_threshold = standard_time + timedelta(minutes=settings_obj.late_threshold_minutes)
                        
                        if current_time > late_threshold:
                            attendance.status = 'LATE'
                        else:
                            attendance.status = 'PRESENT'
                    else:
                        attendance.status = 'PRESENT'
                    
                    attendance.save()
            else:
                # Employee NOT detected
                not_present_count = tracking.increment_not_present()
                
                if not_present_count == 1:
                    # First time not detected - warning
                    scan_results['not_present_warning'].append({
                        'id': employee.id,
                        'name': employee.full_name,
                        'warning_count': 1,
                        'message': 'First warning - not detected'
                    })
                
                elif not_present_count >= 3:
                    # 3rd time not detected - take action
                    if attendance.check_in and not attendance.is_checked_out:
                        # Already checked in - auto check-out
                        attendance.check_out = current_time
                        attendance.is_checked_out = True
                        attendance.calculate_work_hours()
                        attendance.remarks = f"Auto check-out after {not_present_count} consecutive scans without detection"
                        attendance.save()
                        
                        tracking.auto_checked_out = True
                        tracking.save()
                        
                        scan_results['auto_checked_out'].append({
                            'id': employee.id,
                            'name': employee.full_name,
                            'work_hours': str(attendance.work_hours),
                            'message': f'Auto checked-out after {not_present_count} missed scans'
                        })
                    
                    elif not attendance.check_in:
                        # No check-in - mark as absent
                        attendance.status = 'ABSENT'
                        attendance.remarks = f"Marked absent after {not_present_count} consecutive scans without detection"
                        attendance.save()
                        
                        tracking.auto_marked_absent = True
                        tracking.save()
                        
                        scan_results['marked_absent'].append({
                            'id': employee.id,
                            'name': employee.full_name,
                            'message': f'Marked absent after {not_present_count} missed scans'
                        })
                else:
                    # 2nd time not detected
                    scan_results['not_present_warning'].append({
                        'id': employee.id,
                        'name': employee.full_name,
                        'warning_count': not_present_count,
                        'message': f'Warning {not_present_count}/3 - not detected'
                    })
        
        return JsonResponse({
            'success': True,
            'message': f'Scan completed. Detected {len(detected_employee_ids)} of {all_employees.count()} employees.',
            'detected_count': len(detected_employee_ids),
            'warning_count': len(scan_results['not_present_warning']),
            'absent_count': len(scan_results['marked_absent']),
            'checkout_count': len(scan_results['auto_checked_out']),
            'results': scan_results,
            'timestamp': current_time.isoformat()
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
def get_presence_status(request):
    """Get current presence status for all employees"""
    try:
        today = date.today()
        
        from enrollment.models import FaceEncoding
        enrolled_employee_ids = FaceEncoding.objects.values_list('employee_id', flat=True).distinct()
        all_employees = Employee.objects.filter(id__in=enrolled_employee_ids, is_active=True)
        
        employees_list = []
        stats = {
            'present': 0,
            'warning': 0,
            'absent': 0,
            'checked_out': 0
        }
        
        for employee in all_employees:
            tracking = PresenceTracking.objects.filter(employee=employee, date=today).first()
            attendance = AttendanceRecord.objects.filter(employee=employee, date=today).first()
            
            # Determine status
            status = 'unknown'
            if tracking:
                if tracking.auto_marked_absent:
                    status = 'absent'
                    stats['absent'] += 1
                elif tracking.auto_checked_out:
                    status = 'checked_out'
                    stats['checked_out'] += 1
                elif tracking.not_present_count > 0:
                    status = 'warning'
                    stats['warning'] += 1
                elif tracking.not_present_count == 0 and tracking.scan_count > 0:
                    status = 'present'
                    stats['present'] += 1
            elif attendance and attendance.check_in:
                status = 'present'
                stats['present'] += 1
            
            # Format times
            last_seen_str = None
            if tracking and tracking.last_seen:
                last_seen_str = tracking.last_seen.strftime('%I:%M %p')
            
            checkin_str = None
            checkout_str = None
            if attendance:
                if attendance.check_in:
                    checkin_str = attendance.check_in.strftime('%I:%M %p')
                if attendance.check_out:
                    checkout_str = attendance.check_out.strftime('%I:%M %p')
            
            employees_list.append({
                'id': employee.id,
                'employee_id': employee.employee_id,
                'name': employee.full_name,
                'department': employee.department.name if employee.department else 'N/A',
                'status': status,
                'not_present_count': tracking.not_present_count if tracking else 0,
                'last_seen': last_seen_str,
                'checkin_time': checkin_str,
                'checkout_time': checkout_str,
                'auto_checked_out': tracking.auto_checked_out if tracking else False,
                'auto_marked_absent': tracking.auto_marked_absent if tracking else False,
            })
        
        return JsonResponse({
            'success': True,
            'employees': employees_list,
            'stats': stats,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
def reset_presence_tracking(request):
    """Reset presence tracking for all employees (for a new day or manual reset)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'})
    
    try:
        today = date.today()
        deleted_count = PresenceTracking.objects.filter(date=today).delete()[0]
        
        return JsonResponse({
            'success': True,
            'message': f'Reset {deleted_count} presence tracking records for today.',
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def get_attendance_statistics(request):
    """Get attendance statistics including average working hours"""
    try:
        from django.db.models import Avg, Count, Sum, Q
        from django.db.models.functions import TruncMonth, TruncWeek
        
        # Get date range from request
        days = int(request.GET.get('days', 30))
        employee_id = request.GET.get('employee_id')
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Base queryset
        records = AttendanceRecord.objects.filter(date__gte=start_date, date__lte=end_date)
        
        if employee_id:
            records = records.filter(employee_id=employee_id)
        
        # Calculate statistics
        total_records = records.count()
        present_count = records.filter(status='PRESENT').count()
        late_count = records.filter(status='LATE').count()
        absent_count = records.filter(status='ABSENT').count()
        half_day_count = records.filter(status='HALF_DAY').count()
        
        # Average working hours (exclude null work_hours)
        from django.db.models.functions import Cast, Coalesce
        from django.db.models import FloatField
        
        records_with_hours = records.filter(work_hours__isnull=False)
        
        # Calculate average work hours manually to handle timedelta
        avg_work_hours = 0
        total_seconds = 0
        count = 0
        for record in records_with_hours:
            if record.work_hours:
                total_seconds += record.work_hours.total_seconds()
                count += 1
        
        if count > 0:
            avg_work_hours = (total_seconds / count) / 3600  # Convert seconds to hours
        
        # Total working hours
        total_work_hours = total_seconds / 3600 if total_seconds > 0 else 0
        
        # Employees with most absences
        absent_leaders = AttendanceRecord.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            status='ABSENT'
        ).values('employee__full_name', 'employee_id').annotate(
            absent_days=Count('id')
        ).order_by('-absent_days')[:5]
        
        # Employees with most late arrivals
        late_leaders = AttendanceRecord.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            status='LATE'
        ).values('employee__full_name', 'employee_id').annotate(
            late_days=Count('id')
        ).order_by('-late_days')[:5]
        
        # Attendance rate
        total_possible = Employee.objects.filter(is_active=True).count() * days
        attendance_rate = ((present_count + late_count) / total_possible * 100) if total_possible > 0 else 0
        
        return JsonResponse({
            'success': True,
            'stats': {
                'avg_work_hours': round(avg_work_hours, 1),
                'total_work_hours': round(total_work_hours, 1),
                'attendance_rate': round(attendance_rate, 1),
                'present_count': present_count,
                'late_count': late_count,
                'absent_count': absent_count,
            },
            'statistics': {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'counts': {
                    'total_records': total_records,
                    'present': present_count,
                    'late': late_count,
                    'absent': absent_count,
                    'half_day': half_day_count,
                },
                'hours': {
                    'average_work_hours': round(avg_work_hours, 2),
                    'total_work_hours': round(total_work_hours, 2),
                },
                'rates': {
                    'attendance_rate': round(attendance_rate, 1),
                    'present_rate': round(present_count / total_records * 100, 1) if total_records > 0 else 0,
                    'late_rate': round(late_count / total_records * 100, 1) if total_records > 0 else 0,
                    'absent_rate': round(absent_count / total_records * 100, 1) if total_records > 0 else 0,
                },
                'top_absentees': list(absent_leaders),
                'top_late_arrivals': list(late_leaders),
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)})
