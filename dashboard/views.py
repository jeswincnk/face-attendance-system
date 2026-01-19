from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count, Q, Avg
from datetime import datetime, timedelta
from enrollment.models import Employee, Department
from attendance.models import AttendanceRecord, LeaveRequest


def main_dashboard(request):
    """Main system dashboard with overview"""
    today = timezone.now().date()
    
    # Employee statistics
    total_employees = Employee.objects.count()
    active_employees = Employee.objects.filter(is_active=True).count()
    total_departments = Department.objects.count()
    
    # Today's attendance
    today_records = AttendanceRecord.objects.filter(date=today)
    present_today = today_records.filter(status__in=['PRESENT', 'LATE']).count()
    late_today = today_records.filter(status='LATE').count()
    absent_today = active_employees - present_today
    
    # Weekly statistics (last 7 days)
    week_ago = today - timedelta(days=7)
    weekly_records = AttendanceRecord.objects.filter(date__gte=week_ago, date__lte=today)
    avg_attendance = weekly_records.filter(status__in=['PRESENT', 'LATE']).count() / 7 if weekly_records.exists() else 0
    
    # Monthly statistics
    first_day_month = today.replace(day=1)
    monthly_records = AttendanceRecord.objects.filter(date__gte=first_day_month, date__lte=today)
    present_monthly = monthly_records.filter(status__in=['PRESENT', 'LATE']).count()
    
    # Leave requests
    pending_leaves = LeaveRequest.objects.filter(status='PENDING').count()
    
    # Recent activities (last 10 check-ins)
    recent_checkins = AttendanceRecord.objects.filter(
        check_in__isnull=False
    ).select_related('employee').order_by('-check_in')[:10]
    
    # Department-wise attendance
    departments_stats = []
    for dept in Department.objects.all():
        dept_employees = dept.employees.filter(is_active=True).count()
        dept_present = today_records.filter(
            employee__department=dept,
            status__in=['PRESENT', 'LATE']
        ).count()
        if dept_employees > 0:
            departments_stats.append({
                'name': dept.name,
                'total': dept_employees,
                'present': dept_present,
                'percentage': round((dept_present / dept_employees) * 100, 1)
            })
    
    # Daily attendance trend (last 7 days)
    daily_trend = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        count = AttendanceRecord.objects.filter(
            date=date,
            status__in=['PRESENT', 'LATE']
        ).count()
        daily_trend.append({
            'date': date.strftime('%b %d'),
            'count': count
        })
    
    context = {
        'total_employees': total_employees,
        'active_employees': active_employees,
        'total_departments': total_departments,
        'present_today': present_today,
        'late_today': late_today,
        'absent_today': absent_today,
        'avg_attendance': round(avg_attendance, 1),
        'present_monthly': present_monthly,
        'pending_leaves': pending_leaves,
        'recent_checkins': recent_checkins,
        'departments_stats': departments_stats,
        'daily_trend': daily_trend,
        'today': today,
    }
    
    return render(request, 'dashboard/main_dashboard.html', context)

