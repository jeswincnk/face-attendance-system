from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import datetime, timedelta, time, date
from .models import AttendanceRecord, LeaveRequest, AttendanceSettings, PresenceTracking
from enrollment.models import Employee


def attendance_dashboard(request):
    """Main attendance dashboard with presence tracking"""
    today = timezone.now().date()
    
    # Get today's attendance stats
    today_records = AttendanceRecord.objects.filter(date=today)
    total_employees = Employee.objects.filter(is_active=True).count()
    present_count = today_records.filter(status__in=['PRESENT', 'LATE']).count()
    absent_count = total_employees - present_count
    late_count = today_records.filter(status='LATE').count()
    
    # Recent check-ins
    recent_checkins = today_records.filter(check_in__isnull=False).order_by('-check_in')[:10]
    
    # Presence tracking data
    presence_data = PresenceTracking.objects.filter(date=today).select_related('employee', 'employee__department')
    
    # Presence stats
    presence_stats = {
        'present': presence_data.filter(not_present_count=0, scan_count__gt=0).count(),
        'warning': presence_data.filter(not_present_count__gt=0, not_present_count__lt=3, auto_marked_absent=False, auto_checked_out=False).count(),
        'absent': presence_data.filter(auto_marked_absent=True).count(),
        'checked_out': presence_data.filter(auto_checked_out=True).count(),
    }
    
    # Get employees with face encodings for presence tracking
    from enrollment.models import FaceEncoding
    enrolled_employee_ids = FaceEncoding.objects.values_list('employee_id', flat=True).distinct()
    enrolled_employees = Employee.objects.filter(id__in=enrolled_employee_ids, is_active=True).select_related('department')
    
    # Build presence list
    presence_list = []
    for employee in enrolled_employees:
        tracking = presence_data.filter(employee=employee).first()
        attendance = today_records.filter(employee=employee).first()
        
        status = 'unknown'
        if tracking:
            if tracking.auto_marked_absent:
                status = 'absent'
            elif tracking.auto_checked_out:
                status = 'checked_out'
            elif tracking.not_present_count > 0:
                status = 'warning'
            elif tracking.not_present_count == 0 and tracking.scan_count > 0:
                status = 'present'
        elif attendance and attendance.check_in:
            status = 'present'
        
        presence_list.append({
            'employee': employee,
            'tracking': tracking,
            'attendance': attendance,
            'status': status,
        })
    
    # Get attendance settings
    settings_obj = AttendanceSettings.objects.first()
    if not settings_obj:
        settings_obj = AttendanceSettings.objects.create()
    
    # Get all employees for custom hours table
    all_employees = Employee.objects.filter(is_active=True).select_related('department').order_by('first_name', 'last_name')
    
    context = {
        'today': today,
        'total_employees': total_employees,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'recent_checkins': recent_checkins,
        'presence_stats': presence_stats,
        'presence_list': presence_list,
        'settings': settings_obj,
        'employees': all_employees,
    }
    return render(request, 'attendance/attendance_dashboard.html', context)


def mark_attendance(request, employee_id, action='checkin'):
    """Manually mark attendance (check-in or check-out)"""
    employee = get_object_or_404(Employee, pk=employee_id)
    today = timezone.now().date()
    now = timezone.now()
    
    # Get or create attendance record
    record, created = AttendanceRecord.objects.get_or_create(
        employee=employee,
        date=today,
        defaults={'status': 'ABSENT'}
    )
    
    settings_obj = AttendanceSettings.objects.first()
    if not settings_obj:
        settings_obj = AttendanceSettings.objects.create()
    
    if action == 'checkin':
        if record.check_in:
            messages.warning(request, f'{employee.full_name} already checked in today.')
        else:
            record.check_in = now
            
            # Determine if late
            standard_time = datetime.combine(today, settings_obj.standard_check_in_time)
            standard_time = timezone.make_aware(standard_time)
            late_threshold = standard_time + timedelta(minutes=settings_obj.late_threshold_minutes)
            
            if now > late_threshold:
                record.status = 'LATE'
            else:
                record.status = 'PRESENT'
            
            record.save()
            messages.success(request, f'{employee.full_name} checked in at {now.strftime("%I:%M %p")}')
    
    elif action == 'checkout':
        if not record.check_in:
            messages.warning(request, f'{employee.full_name} has not checked in yet.')
        elif record.check_out:
            messages.warning(request, f'{employee.full_name} already checked out today.')
        else:
            record.check_out = now
            record.calculate_work_hours()
            record.save()
            messages.success(request, f'{employee.full_name} checked out at {now.strftime("%I:%M %p")}. Work hours: {record.work_hours}')
    
    return redirect('attendance:attendance_dashboard')


def attendance_record_employee(request, employee_id):
    """View attendance records for specific employee"""
    employee = get_object_or_404(Employee, pk=employee_id)
    
    # Filter by date range if provided
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    records = AttendanceRecord.objects.filter(employee=employee).order_by('-date')
    
    if start_date:
        records = records.filter(date__gte=start_date)
    if end_date:
        records = records.filter(date__lte=end_date)
    
    # Calculate statistics
    total_days = records.count()
    present_days = records.filter(status__in=['PRESENT', 'LATE']).count()
    absent_days = records.filter(status='ABSENT').count()
    late_days = records.filter(status='LATE').count()
    
    # Calculate average work hours properly for timedelta
    work_records = records.filter(work_hours__isnull=False)
    avg_work_hours = 0
    total_work_hours = 0
    if work_records.exists():
        total_seconds = 0
        count = 0
        for r in work_records:
            if r.work_hours:
                total_seconds += r.work_hours.total_seconds()
                count += 1
        if count > 0:
            avg_work_hours = (total_seconds / count) / 3600
            total_work_hours = total_seconds / 3600
    
    # Get today's presence tracking
    today = timezone.now().date()
    today_tracking = PresenceTracking.objects.filter(employee=employee, date=today).first()
    today_attendance = AttendanceRecord.objects.filter(employee=employee, date=today).first()
    
    # Calculate presence stats for last 30 days
    last_30_days = today - timedelta(days=30)
    presence_history = PresenceTracking.objects.filter(
        employee=employee,
        date__gte=last_30_days
    ).order_by('-date')
    
    auto_absent_count = presence_history.filter(auto_marked_absent=True).count()
    auto_checkout_count = presence_history.filter(auto_checked_out=True).count()
    
    context = {
        'employee': employee,
        'records': records[:50],  # Limit to last 50 records
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'late_days': late_days,
        'avg_work_hours': round(avg_work_hours, 1),
        'total_work_hours': round(total_work_hours, 1),
        'today_tracking': today_tracking,
        'today_attendance': today_attendance,
        'presence_history': presence_history[:10],
        'auto_absent_count': auto_absent_count,
        'auto_checkout_count': auto_checkout_count,
    }
    return render(request, 'attendance/employee_attendance.html', context)


def attendance_record_date(request):
    """View attendance for specific date"""
    date_str = request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
    date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    records = AttendanceRecord.objects.filter(date=date).select_related('employee')
    
    # Get all active employees and mark absent ones
    active_employees = Employee.objects.filter(is_active=True)
    present_employee_ids = records.values_list('employee_id', flat=True)
    
    # Create records for absent employees
    for employee in active_employees:
        if employee.id not in present_employee_ids:
            AttendanceRecord.objects.get_or_create(
                employee=employee,
                date=date,
                defaults={'status': 'ABSENT'}
            )
    
    # Refresh records
    records = AttendanceRecord.objects.filter(date=date).select_related('employee').order_by('employee__employee_id')
    
    context = {
        'date': date,
        'records': records,
    }
    return render(request, 'attendance/date_attendance.html', context)


def leave_request_list(request):
    """View all leave requests"""
    status_filter = request.GET.get('status', 'all')
    
    leave_requests = LeaveRequest.objects.all().select_related('employee', 'approved_by')
    
    if status_filter != 'all':
        leave_requests = leave_requests.filter(status=status_filter.upper())
    
    leave_requests = leave_requests.order_by('-created_at')
    
    context = {
        'leave_requests': leave_requests,
        'status_filter': status_filter,
    }
    return render(request, 'attendance/leave_requests.html', context)


def settings_view(request):
    """View and update attendance settings"""
    settings_obj, created = AttendanceSettings.objects.get_or_create()
    employees = Employee.objects.filter(is_active=True).order_by('employee_id')
    
    if request.method == 'POST':
        action = request.POST.get('action', 'global_settings')
        
        if action == 'global_settings':
            # Update global settings
            settings_obj.standard_check_in_time = request.POST.get('standard_check_in_time')
            settings_obj.standard_check_out_time = request.POST.get('standard_check_out_time')
            settings_obj.late_threshold_minutes = request.POST.get('late_threshold_minutes')
            settings_obj.early_departure_threshold_minutes = request.POST.get('early_departure_threshold_minutes')
            settings_obj.half_day_hours = request.POST.get('half_day_hours')
            settings_obj.full_day_hours = request.POST.get('full_day_hours')
            settings_obj.save()
            messages.success(request, 'Global attendance settings updated successfully!')
        
        elif action == 'employee_settings':
            # Update individual employee settings
            employee_id = request.POST.get('employee_id')
            employee = Employee.objects.get(id=employee_id)
            
            use_custom = request.POST.get('use_custom_hours') == 'on'
            employee.use_custom_hours = use_custom
            
            if use_custom:
                custom_check_in = request.POST.get('custom_check_in_time')
                custom_check_out = request.POST.get('custom_check_out_time')
                custom_full_day = request.POST.get('custom_full_day_hours')
                custom_half_day = request.POST.get('custom_half_day_hours')
                
                employee.custom_check_in_time = custom_check_in if custom_check_in else None
                employee.custom_check_out_time = custom_check_out if custom_check_out else None
                employee.custom_full_day_hours = custom_full_day if custom_full_day else None
                employee.custom_half_day_hours = custom_half_day if custom_half_day else None
            else:
                # Clear custom settings when disabled
                employee.custom_check_in_time = None
                employee.custom_check_out_time = None
                employee.custom_full_day_hours = None
                employee.custom_half_day_hours = None
            
            employee.save()
            messages.success(request, f'Settings for {employee.full_name} updated successfully!')
        
        elif action == 'bulk_assign':
            # Bulk assign custom hours to multiple employees
            selected_employees = request.POST.get('selected_employees', '')
            bulk_check_in = request.POST.get('bulk_check_in_time')
            bulk_check_out = request.POST.get('bulk_check_out_time')
            bulk_full_day = request.POST.get('bulk_full_day_hours')
            bulk_half_day = request.POST.get('bulk_half_day_hours')
            
            if selected_employees:
                employee_ids = [int(eid) for eid in selected_employees.split(',') if eid]
                updated_count = 0
                
                for emp in Employee.objects.filter(id__in=employee_ids):
                    emp.use_custom_hours = True
                    emp.custom_check_in_time = bulk_check_in if bulk_check_in else None
                    emp.custom_check_out_time = bulk_check_out if bulk_check_out else None
                    emp.custom_full_day_hours = bulk_full_day if bulk_full_day else None
                    emp.custom_half_day_hours = bulk_half_day if bulk_half_day else None
                    emp.save()
                    updated_count += 1
                
                messages.success(request, f'Custom hours applied to {updated_count} employee(s) successfully!')
            else:
                messages.warning(request, 'No employees selected for bulk assignment.')
        
        return redirect('attendance:settings')
    
    context = {
        'settings': settings_obj,
        'employees': employees,
    }
    return render(request, 'attendance/settings.html', context)

