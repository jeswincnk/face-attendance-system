from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, date, timedelta
import json
import base64
import numpy as np
import cv2

from enrollment.models import Employee, FaceEncoding
from attendance.models import AttendanceRecord, AttendanceSettings
from recognition.face_utils import FaceRecognitionEngine


def login_view(request):
    """Employee and Admin login page"""
    if request.user.is_authenticated:
        # Redirect based on role
        try:
            employee = request.user.employee_profile
            if employee.role == 'admin':
                return redirect('home')
            return redirect('accounts:employee_portal')
        except:
            return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            
            # Redirect based on role
            try:
                employee = user.employee_profile
                if employee.role == 'admin':
                    return redirect('home')
                return redirect('accounts:employee_portal')
            except:
                # Superuser without employee profile
                return redirect('home')
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'accounts/login.html')


def logout_view(request):
    """Logout and auto check-out"""
    if request.user.is_authenticated:
        try:
            employee = request.user.employee_profile
            # Auto check-out on logout
            today = date.today()
            record = AttendanceRecord.objects.filter(
                employee=employee,
                date=today,
                is_checked_out=False
            ).first()
            
            if record and record.check_in:
                record.check_out = timezone.now()
                record.is_checked_out = True
                record.calculate_work_hours()
                record.save()
                messages.info(request, f'You have been checked out. Work hours: {record.work_hours}')
        except:
            pass
    
    logout(request)
    messages.success(request, 'You have been logged out successfully')
    return redirect('accounts:login')


@login_required
def employee_portal(request):
    """Employee self-service portal dashboard"""
    try:
        employee = request.user.employee_profile
    except:
        messages.error(request, 'No employee profile linked to your account')
        return redirect('accounts:login')
    
    # Check if admin trying to access employee portal
    if employee.role == 'admin':
        return redirect('home')
    
    today = date.today()
    
    # Get today's attendance
    today_record = AttendanceRecord.objects.filter(
        employee=employee,
        date=today
    ).first()
    
    # Get this month's attendance
    month_start = today.replace(day=1)
    month_records = AttendanceRecord.objects.filter(
        employee=employee,
        date__gte=month_start,
        date__lte=today
    )
    
    present_days = month_records.filter(status__in=['PRESENT', 'LATE']).count()
    late_days = month_records.filter(status='LATE').count()
    
    # Check if face is enrolled
    has_face_enrolled = FaceEncoding.objects.filter(employee=employee).exists()
    
    context = {
        'employee': employee,
        'today_record': today_record,
        'is_checked_in': today_record and today_record.check_in and not today_record.is_checked_out,
        'present_days': present_days,
        'late_days': late_days,
        'has_face_enrolled': has_face_enrolled,
    }
    
    return render(request, 'accounts/employee_portal.html', context)


@login_required
def employee_profile(request):
    """View and edit employee profile"""
    try:
        employee = request.user.employee_profile
    except:
        messages.error(request, 'No employee profile linked')
        return redirect('accounts:login')
    
    if request.method == 'POST':
        action = request.POST.get('action', 'update_profile')
        
        if action == 'change_password':
            # Handle password change
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            
            if not current_password or not new_password or not confirm_password:
                messages.error(request, 'All password fields are required')
            elif not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match')
            elif len(new_password) < 6:
                messages.error(request, 'Password must be at least 6 characters')
            else:
                request.user.set_password(new_password)
                request.user.save()
                # Re-authenticate to keep user logged in
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password changed successfully!')
        else:
            # Update basic profile info
            employee.phone = request.POST.get('phone', employee.phone)
            if request.FILES.get('photo'):
                employee.photo = request.FILES['photo']
            employee.save()
            messages.success(request, 'Profile updated successfully')
    
    # Get face encodings
    face_encodings = FaceEncoding.objects.filter(employee=employee)
    
    context = {
        'employee': employee,
        'face_encodings': face_encodings,
    }
    
    return render(request, 'accounts/employee_profile.html', context)


@login_required
def self_checkin(request):
    """Self check-in page with webcam face verification"""
    try:
        employee = request.user.employee_profile
    except:
        messages.error(request, 'No employee profile linked')
        return redirect('accounts:login')
    
    # Check if already checked in today
    today = date.today()
    today_record = AttendanceRecord.objects.filter(
        employee=employee,
        date=today
    ).first()
    
    if today_record and today_record.check_in and not today_record.is_checked_out:
        messages.warning(request, 'You are already checked in for today')
        return redirect('accounts:employee_portal')
    
    # Check if face is enrolled
    has_face = FaceEncoding.objects.filter(employee=employee).exists()
    
    context = {
        'employee': employee,
        'has_face': has_face,
    }
    
    return render(request, 'accounts/self_checkin.html', context)


@csrf_exempt
@login_required
def verify_face(request):
    """Verify captured face matches employee's enrolled face"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'})
    
    try:
        employee = request.user.employee_profile
    except:
        return JsonResponse({'success': False, 'message': 'No employee profile'})
    
    try:
        data = json.loads(request.body)
        image_data = data.get('image')
        action = data.get('action', 'checkin')  # checkin or checkout
        
        if not image_data:
            return JsonResponse({'success': False, 'message': 'No image provided'})
        
        # Decode base64 image
        image_data = image_data.split(',')[1] if ',' in image_data else image_data
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return JsonResponse({'success': False, 'message': 'Invalid image'})
        
        # Initialize recognition engine
        engine = FaceRecognitionEngine()
        engine.load_encodings_from_db()
        
        # Detect and recognize face
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
        
        if len(faces) == 0:
            return JsonResponse({'success': False, 'message': 'No face detected. Please position your face in the camera.'})
        
        if len(faces) > 1:
            return JsonResponse({'success': False, 'message': 'Multiple faces detected. Please ensure only your face is visible.'})
        
        # Get the face region with padding (same as training)
        (x, y, w, h) = faces[0]
        
        # Add padding around face for better recognition (same as training)
        padding = int(0.1 * w)
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(gray.shape[1], x + w + padding)
        y2 = min(gray.shape[0], y + h + padding)
        
        face_roi = gray[y1:y2, x1:x2]
        
        # Resize to standard size (same as training)
        face_roi = cv2.resize(face_roi, (200, 200))
        
        # Recognize the face with lenient mode (user is already authenticated)
        recognized_id, confidence = engine.recognize_face(face_roi, lenient=True)
        
        if recognized_id is None:
            # Provide more helpful message with confidence info
            conf_msg = f" (confidence: {confidence:.1f})" if confidence else ""
            return JsonResponse({'success': False, 'message': f'Face not recognized{conf_msg}. Please try again with better lighting.'})
        
        # Verify it matches the logged-in employee
        recognized_employee = Employee.objects.filter(id=recognized_id).first()
        
        if not recognized_employee or recognized_employee.id != employee.id:
            return JsonResponse({
                'success': False, 
                'message': 'Face does not match your profile. Please ensure you are the registered employee.'
            })
        
        # Face verified! Process check-in or check-out
        today = date.today()
        now = timezone.now()
        
        if action == 'checkin':
            # Create or get attendance record
            record, created = AttendanceRecord.objects.get_or_create(
                employee=employee,
                date=today,
                defaults={'check_in': now, 'checkin_method': 'SELF'}
            )
            
            if not created and record.check_in and not record.is_checked_out:
                return JsonResponse({'success': False, 'message': 'Already checked in'})
            
            if not record.check_in:
                record.check_in = now
                record.checkin_method = 'SELF'
            
            # Determine status based on time
            settings = AttendanceSettings.objects.first()
            if settings:
                work_start = datetime.combine(today, settings.standard_check_in_time)
                work_start = timezone.make_aware(work_start)
                late_threshold = work_start + timedelta(minutes=settings.late_threshold_minutes)
                
                if now <= late_threshold:
                    record.status = 'PRESENT'
                else:
                    record.status = 'LATE'
            else:
                record.status = 'PRESENT'
            
            record.is_checked_out = False
            record.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Check-in successful! Status: {record.status}',
                'time': now.strftime('%H:%M:%S'),
                'status': record.status
            })
        
        elif action == 'checkout':
            record = AttendanceRecord.objects.filter(
                employee=employee,
                date=today,
                is_checked_out=False
            ).first()
            
            if not record or not record.check_in:
                return JsonResponse({'success': False, 'message': 'No check-in found for today'})
            
            record.check_out = now
            record.is_checked_out = True
            record.calculate_work_hours()
            record.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Check-out successful! Work hours: {record.work_hours}',
                'time': now.strftime('%H:%M:%S'),
                'work_hours': str(record.work_hours)
            })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


@csrf_exempt
@login_required
def self_checkout(request):
    """Manual self check-out (without face verification for quick exit)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'})
    
    try:
        employee = request.user.employee_profile
        today = date.today()
        now = timezone.now()
        
        record = AttendanceRecord.objects.filter(
            employee=employee,
            date=today,
            is_checked_out=False
        ).first()
        
        if not record or not record.check_in:
            return JsonResponse({'success': False, 'message': 'No check-in found for today'})
        
        record.check_out = now
        record.is_checked_out = True
        record.calculate_work_hours()
        record.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Checked out successfully! Work hours: {record.work_hours}',
            'work_hours': str(record.work_hours)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
def beacon_checkout(request):
    """Called when browser is closing to auto check-out (using sendBeacon API)"""
    if request.method != 'POST':
        return JsonResponse({'success': False})
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({'success': False})
        
        from django.contrib.auth.models import User
        user = User.objects.filter(id=user_id).first()
        
        if not user:
            return JsonResponse({'success': False})
        
        try:
            employee = user.employee_profile
        except:
            return JsonResponse({'success': False})
        
        today = date.today()
        now = timezone.now()
        
        record = AttendanceRecord.objects.filter(
            employee=employee,
            date=today,
            is_checked_out=False
        ).first()
        
        if record and record.check_in:
            record.check_out = now
            record.is_checked_out = True
            record.remarks = (record.remarks or '') + ' [Auto checkout on browser close]'
            record.calculate_work_hours()
            record.save()
        
        return JsonResponse({'success': True})
        
    except:
        return JsonResponse({'success': False})


@login_required
def my_attendance(request):
    """View personal attendance history"""
    try:
        employee = request.user.employee_profile
    except:
        messages.error(request, 'No employee profile linked')
        return redirect('accounts:login')
    
    # Get date range filter
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    
    records_qs = AttendanceRecord.objects.filter(employee=employee)
    
    if from_date:
        records_qs = records_qs.filter(date__gte=from_date)
    if to_date:
        records_qs = records_qs.filter(date__lte=to_date)
    
    # Calculate stats BEFORE slicing
    total_records = records_qs.count()
    present_days = records_qs.filter(status__in=['PRESENT', 'LATE']).count()
    late_days = records_qs.filter(status='LATE').count()
    
    # Now slice for display
    records = records_qs.order_by('-date')[:30]  # Last 30 records
    total_hours = sum([r.work_hours or 0 for r in records])
    
    context = {
        'employee': employee,
        'records': records,
        'total_records': total_records,
        'present_days': present_days,
        'late_days': late_days,
        'total_hours': total_hours,
    }
    
    return render(request, 'accounts/my_attendance.html', context)
