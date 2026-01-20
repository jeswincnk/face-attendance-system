from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
from .models import Employee, Department, FaceEncoding
from .forms import EmployeeForm, DepartmentForm, FaceEncodingForm
from recognition.face_utils import FaceRecognitionEngine, save_face_encoding_to_db, OPENCV_AVAILABLE
import json
import base64
from PIL import Image
import io

try:
    import numpy as np
except ImportError:
    np = None


def employee_list(request):
    """List all employees"""
    employees = Employee.objects.all().select_related('department')
    context = {
        'employees': employees,
        'active_count': employees.filter(is_active=True).count(),
        'total_count': employees.count(),
    }
    return render(request, 'enrollment/employee_list.html', context)


def employee_detail(request, pk):
    """View employee details with attendance and presence tracking"""
    from attendance.models import AttendanceRecord, PresenceTracking
    
    employee = get_object_or_404(Employee, pk=pk)
    face_encodings = employee.face_encodings.all()
    
    # Get recent attendance records
    recent_attendance = AttendanceRecord.objects.filter(
        employee=employee
    ).order_by('-date')[:10]
    
    # Get today's data
    today = timezone.now().date()
    today_attendance = AttendanceRecord.objects.filter(employee=employee, date=today).first()
    today_tracking = PresenceTracking.objects.filter(employee=employee, date=today).first()
    
    # Calculate stats for last 30 days
    last_30_days = today - timedelta(days=30)
    records_30_days = AttendanceRecord.objects.filter(
        employee=employee,
        date__gte=last_30_days
    )
    
    present_count = records_30_days.filter(status__in=['PRESENT', 'LATE']).count()
    absent_count = records_30_days.filter(status='ABSENT').count()
    late_count = records_30_days.filter(status='LATE').count()
    
    # Calculate average work hours
    work_records = records_30_days.filter(work_hours__isnull=False)
    avg_work_hours = 0
    if work_records.exists():
        total_seconds = 0
        count = 0
        for r in work_records:
            if r.work_hours:
                total_seconds += r.work_hours.total_seconds()
                count += 1
        if count > 0:
            avg_work_hours = (total_seconds / count) / 3600
    
    # Get presence tracking history
    presence_history = PresenceTracking.objects.filter(
        employee=employee,
        date__gte=last_30_days
    ).order_by('-date')[:10]
    
    auto_absent_count = presence_history.filter(auto_marked_absent=True).count()
    auto_checkout_count = presence_history.filter(auto_checked_out=True).count()
    
    context = {
        'employee': employee,
        'face_encodings': face_encodings,
        'recent_attendance': recent_attendance,
        'today_attendance': today_attendance,
        'today_tracking': today_tracking,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'avg_work_hours': round(avg_work_hours, 1),
        'auto_absent_count': auto_absent_count,
        'auto_checkout_count': auto_checkout_count,
    }
    return render(request, 'enrollment/employee_detail.html', context)


def employee_create(request):
    """Create new employee"""
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Employee {employee.full_name} created successfully!')
            return redirect('enrollment:employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm()
    
    context = {'form': form, 'action': 'Create'}
    return render(request, 'enrollment/employee_form.html', context)


def employee_update(request, pk):
    """Update employee details"""
    employee = get_object_or_404(Employee, pk=pk)
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Employee {employee.full_name} updated successfully!')
            return redirect('enrollment:employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee)
    
    context = {'form': form, 'action': 'Update', 'employee': employee}
    return render(request, 'enrollment/employee_form.html', context)


def employee_delete(request, pk):
    """Delete employee"""
    employee = get_object_or_404(Employee, pk=pk)
    
    if request.method == 'POST':
        employee.delete()
        messages.success(request, f'Employee {employee.full_name} deleted successfully!')
        return redirect('enrollment:employee_list')
    
    context = {'employee': employee}
    return render(request, 'enrollment/employee_confirm_delete.html', context)


def employee_toggle_status(request, pk):
    """Toggle employee active status"""
    employee = get_object_or_404(Employee, pk=pk)
    employee.is_active = not employee.is_active
    employee.save()
    
    status = "activated" if employee.is_active else "deactivated"
    messages.success(request, f'Employee {employee.full_name} {status}!')
    return redirect('enrollment:employee_detail', pk=employee.pk)


def face_enrollment(request, employee_id):
    """Enroll face for an employee"""
    employee = get_object_or_404(Employee, pk=employee_id)
    
    if request.method == 'POST':
        form = FaceEncodingForm(request.POST, request.FILES)
        if form.is_valid():
            face_encoding_obj = form.save(commit=False)
            face_encoding_obj.employee = employee
            
            # Generate face encoding
            engine = FaceRecognitionEngine()
            encoding, face_location = engine.generate_encoding(face_encoding_obj.image.path)
            
            if encoding is None:
                messages.error(request, 'No face detected in the image. Please try another image.')
                return redirect('enrollment:face_enrollment', employee_id=employee.id)
            
            # Save encoding to database
            import pickle
            face_encoding_obj.encoding = pickle.dumps(encoding)
            face_encoding_obj.save()
            
            messages.success(request, 'Face encoding saved successfully!')
            return redirect('enrollment:employee_detail', pk=employee.pk)
    else:
        form = FaceEncodingForm()
    
    context = {
        'form': form,
        'employee': employee,
    }
    return render(request, 'enrollment/face_enrollment.html', context)


@csrf_exempt
def capture_face_webcam(request, employee_id):
    """Capture face from webcam and save encoding"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image')
            is_primary = data.get('is_primary', False)
            
            # Decode base64 image
            image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to numpy array
            image_array = np.array(image)
            
            # Generate face encoding
            engine = FaceRecognitionEngine()
            encoding, face_location = engine.generate_encoding(image_array)
            
            if encoding is None:
                return JsonResponse({'success': False, 'message': 'No face detected'})
            
            # Get employee
            employee = Employee.objects.get(pk=employee_id)
            
            # Save image
            from django.core.files.base import ContentFile
            import os
            from datetime import datetime
            
            filename = f"face_{employee.employee_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            image_file = ContentFile(image_bytes, name=filename)
            
            # Save to database
            import pickle
            face_encoding = FaceEncoding.objects.create(
                employee=employee,
                encoding=pickle.dumps(encoding),
                image=image_file,
                is_primary=is_primary
            )
            
            if is_primary:
                FaceEncoding.objects.filter(employee=employee).exclude(id=face_encoding.id).update(is_primary=False)
            
            return JsonResponse({
                'success': True,
                'message': 'Face captured and encoded successfully!',
                'encoding_id': face_encoding.id
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


def face_encoding_delete(request, employee_id, encoding_id):
    """Delete a specific face encoding for an employee"""
    employee = get_object_or_404(Employee, pk=employee_id)
    encoding = get_object_or_404(FaceEncoding, pk=encoding_id, employee=employee)

    if request.method == 'POST':
        # Remove stored image file first
        if encoding.image:
            encoding.image.delete(save=False)

        was_primary = encoding.is_primary
        encoding.delete()

        # If we deleted the primary and others exist, promote the latest to primary
        if was_primary:
            new_primary = FaceEncoding.objects.filter(employee=employee).first()
            if new_primary:
                new_primary.is_primary = True
                new_primary.save(update_fields=['is_primary'])

        messages.success(request, 'Face encoding deleted successfully!')
        return redirect('enrollment:face_enrollment', employee_id=employee.id)
    
    messages.error(request, 'Invalid request method for deleting face encoding.')
    return redirect('enrollment:face_enrollment', employee_id=employee.id)


def department_list(request):
    """List all departments"""
    departments = Department.objects.all()
    context = {'departments': departments}
    return render(request, 'enrollment/department_list.html', context)


def department_create(request):
    """Create new department"""
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()
            messages.success(request, f'Department {department.name} created successfully!')
            return redirect('enrollment:department_list')
    else:
        form = DepartmentForm()
    
    context = {'form': form, 'action': 'Create'}
    return render(request, 'enrollment/department_form.html', context)


def department_update(request, pk):
    """Update existing department"""
    department = get_object_or_404(Department, pk=pk)
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            department = form.save()
            messages.success(request, f'Department {department.name} updated successfully!')
            return redirect('enrollment:department_list')
    else:
        form = DepartmentForm(instance=department)
    
    context = {'form': form, 'department': department, 'action': 'Update'}
    return render(request, 'enrollment/department_form.html', context)


def department_delete(request, pk):
    """Delete department"""
    department = get_object_or_404(Department, pk=pk)
    
    if request.method == 'POST':
        department_name = department.name
        department.delete()
        messages.success(request, f'Department {department_name} deleted successfully!')
        return redirect('enrollment:department_list')
    
    context = {'department': department}
    return render(request, 'enrollment/department_confirm_delete.html', context)

