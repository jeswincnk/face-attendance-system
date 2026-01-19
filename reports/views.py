from django.shortcuts import render
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Q
from enrollment.models import Employee, Department
from attendance.models import AttendanceRecord
import csv
import json
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO


def reports_home(request):
    """Reports dashboard with analytics"""
    period = request.GET.get('period', 'today')
    today = timezone.now().date()
    
    # Calculate date range based on period
    if period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == 'month':
        start_date = today.replace(day=1)
        end_date = today
    else:  # today
        start_date = today
        end_date = today
    
    # Get attendance records for the period
    records = AttendanceRecord.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee', 'employee__department')
    
    # Calculate stats
    total_employees = Employee.objects.filter(is_active=True).count()
    present_count = records.filter(status__in=['PRESENT', 'LATE']).values('employee').distinct().count() if period == 'today' else records.filter(status__in=['PRESENT', 'LATE']).count()
    absent_count = records.filter(status='ABSENT').count() if period != 'today' else total_employees - present_count
    late_count = records.filter(status='LATE').count()
    
    total_records = present_count + absent_count
    attendance_rate = round((present_count / total_records * 100), 1) if total_records > 0 else 0
    
    stats = {
        'present': present_count,
        'absent': max(0, absent_count),
        'late': late_count,
        'attendance_rate': attendance_rate
    }
    
    # Employee summary
    employee_stats = []
    for emp in Employee.objects.filter(is_active=True).select_related('department')[:10]:
        emp_records = records.filter(employee=emp)
        emp_present = emp_records.filter(status__in=['PRESENT', 'LATE']).count()
        emp_absent = emp_records.filter(status='ABSENT').count()
        emp_late = emp_records.filter(status='LATE').count()
        emp_total = emp_present + emp_absent
        
        employee_stats.append({
            'name': emp.full_name,
            'department': emp.department.name if emp.department else 'N/A',
            'present': emp_present,
            'absent': emp_absent,
            'late': emp_late,
            'rate': round((emp_present / emp_total * 100), 0) if emp_total > 0 else 0
        })
    
    # Chart data - daily breakdown
    chart_labels = []
    chart_present = []
    chart_late = []
    chart_absent = []
    
    days_range = (end_date - start_date).days + 1
    for i in range(min(days_range, 14)):  # Max 14 days
        day = start_date + timedelta(days=i)
        day_records = records.filter(date=day)
        chart_labels.append(day.strftime('%b %d'))
        chart_present.append(day_records.filter(status='PRESENT').count())
        chart_late.append(day_records.filter(status='LATE').count())
        chart_absent.append(day_records.filter(status='ABSENT').count())
    
    # Department breakdown
    dept_labels = []
    dept_data = []
    for dept in Department.objects.all()[:5]:
        dept_present = records.filter(employee__department=dept, status__in=['PRESENT', 'LATE']).count()
        if dept_present > 0:
            dept_labels.append(dept.name)
            dept_data.append(dept_present)
    
    if not dept_labels:
        dept_labels = ['No Data']
        dept_data = [1]
    
    # Recent check-ins
    recent_records = AttendanceRecord.objects.filter(
        check_in__isnull=False
    ).select_related('employee').order_by('-check_in')[:10]
    
    context = {
        'period': period,
        'stats': stats,
        'employee_stats': employee_stats,
        'chart_labels': json.dumps(chart_labels),
        'chart_present': json.dumps(chart_present),
        'chart_late': json.dumps(chart_late),
        'chart_absent': json.dumps(chart_absent),
        'dept_labels': json.dumps(dept_labels),
        'dept_data': json.dumps(dept_data),
        'recent_records': recent_records,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'reports/dashboard_report.html', context)


def attendance_report(request):
    """Generate attendance report"""
    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    employee_id = request.GET.get('employee')
    department_id = request.GET.get('department')
    export_format = request.GET.get('export', None)
    
    # Default to current month
    if not start_date:
        start_date = timezone.now().date().replace(day=1)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        end_date = timezone.now().date()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Build query
    records = AttendanceRecord.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee', 'employee__department')
    
    if employee_id:
        records = records.filter(employee_id=employee_id)
    
    if department_id:
        records = records.filter(employee__department_id=department_id)
    
    records = records.order_by('employee__employee_id', 'date')
    
    # Export functionality
    if export_format == 'csv':
        return export_csv(records, start_date, end_date)
    elif export_format == 'excel':
        return export_excel(records, start_date, end_date)
    elif export_format == 'pdf':
        return export_pdf(records, start_date, end_date)
    
    # Calculate statistics
    total_days = (end_date - start_date).days + 1
    present_count = records.filter(status__in=['PRESENT', 'LATE']).count()
    absent_count = records.filter(status='ABSENT').count()
    late_count = records.filter(status='LATE').count()
    
    employees = Employee.objects.filter(is_active=True).order_by('employee_id')
    departments = Department.objects.all()
    
    context = {
        'records': records[:100],  # Limit display
        'start_date': start_date,
        'end_date': end_date,
        'total_days': total_days,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'employees': employees,
        'departments': departments,
        'selected_employee': employee_id,
        'selected_department': department_id,
    }
    
    return render(request, 'reports/attendance_report.html', context)


def export_csv(records, start_date, end_date):
    """Export attendance report as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{start_date}_to_{end_date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Employee ID', 'Employee Name', 'Department', 'Date', 'Check In', 'Check Out', 'Work Hours', 'Status', 'Remarks'])
    
    for record in records:
        writer.writerow([
            record.employee.employee_id,
            record.employee.full_name,
            record.employee.department.name if record.employee.department else 'N/A',
            record.date,
            record.check_in.strftime('%I:%M %p') if record.check_in else 'N/A',
            record.check_out.strftime('%I:%M %p') if record.check_out else 'N/A',
            record.work_hours if record.work_hours else 0,
            record.status,
            record.remarks
        ])
    
    return response


def export_excel(records, start_date, end_date):
    """Export attendance report as Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance Report"
    
    # Headers
    headers = ['Employee ID', 'Employee Name', 'Department', 'Date', 'Check In', 'Check Out', 'Work Hours', 'Status', 'Remarks']
    ws.append(headers)
    
    # Style headers
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)
    
    # Data
    for record in records:
        ws.append([
            record.employee.employee_id,
            record.employee.full_name,
            record.employee.department.name if record.employee.department else 'N/A',
            record.date.strftime('%Y-%m-%d'),
            record.check_in.strftime('%I:%M %p') if record.check_in else 'N/A',
            record.check_out.strftime('%I:%M %p') if record.check_out else 'N/A',
            float(record.work_hours) if record.work_hours else 0,
            record.status,
            record.remarks
        ])
    
    # Create response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{start_date}_to_{end_date}.xlsx"'
    
    wb.save(response)
    return response


def export_pdf(records, start_date, end_date):
    """Export attendance report as PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    
    # Title
    title = Paragraph(f"Attendance Report: {start_date} to {end_date}", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Table data
    data = [['Emp ID', 'Name', 'Dept', 'Date', 'Check In', 'Check Out', 'Hours', 'Status']]
    
    for record in records:
        data.append([
            record.employee.employee_id,
            record.employee.full_name[:20],  # Truncate name
            record.employee.department.name[:10] if record.employee.department else 'N/A',
            record.date.strftime('%m/%d'),
            record.check_in.strftime('%I:%M%p') if record.check_in else 'N/A',
            record.check_out.strftime('%I:%M%p') if record.check_out else 'N/A',
            f"{record.work_hours:.1f}" if record.work_hours else '0',
            record.status[:4]
        ])
    
    # Create table
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{start_date}_to_{end_date}.pdf"'
    
    return response


def employee_summary_report(request):
    """Generate employee-wise attendance summary"""
    month = request.GET.get('month', timezone.now().strftime('%Y-%m'))
    year, month_num = map(int, month.split('-'))
    
    # Calculate date range for the month
    start_date = datetime(year, month_num, 1).date()
    if month_num == 12:
        end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(year, month_num + 1, 1).date() - timedelta(days=1)
    
    # Get all active employees
    employees = Employee.objects.filter(is_active=True).select_related('department')
    
    summary_data = []
    for employee in employees:
        records = AttendanceRecord.objects.filter(
            employee=employee,
            date__gte=start_date,
            date__lte=end_date
        )
        
        total_days = records.count()
        present_days = records.filter(status__in=['PRESENT', 'LATE']).count()
        absent_days = records.filter(status='ABSENT').count()
        late_days = records.filter(status='LATE').count()
        avg_work_hours = records.filter(work_hours__isnull=False).aggregate(Avg('work_hours'))['work_hours__avg'] or 0
        
        summary_data.append({
            'employee': employee,
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'late_days': late_days,
            'avg_work_hours': round(avg_work_hours, 2),
            'attendance_rate': round((present_days / total_days * 100), 1) if total_days > 0 else 0
        })
    
    context = {
        'summary_data': summary_data,
        'selected_month': month,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'reports/employee_summary.html', context)


def export_report(request):
    """Export report based on period and format"""
    period = request.GET.get('period', 'today')
    export_format = request.GET.get('format', 'csv')
    
    today = timezone.now().date()
    
    # Calculate date range based on period
    if period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == 'month':
        start_date = today.replace(day=1)
        end_date = today
    else:  # today
        start_date = today
        end_date = today
    
    # Get records
    records = AttendanceRecord.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee', 'employee__department').order_by('employee__employee_id', 'date')
    
    if export_format == 'csv':
        return export_csv(records, start_date, end_date)
    elif export_format == 'excel':
        return export_excel(records, start_date, end_date)
    elif export_format == 'pdf':
        return export_pdf(records, start_date, end_date)
    else:
        return export_csv(records, start_date, end_date)
