from django.db import models
from enrollment.models import Employee
from django.utils import timezone


class AttendanceRecord(models.Model):
    """Records check-in and check-out times for employees"""
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('LATE', 'Late'),
        ('ABSENT', 'Absent'),
        ('HALF_DAY', 'Half Day'),
        ('ON_LEAVE', 'On Leave'),
    ]
    
    CHECKIN_METHOD_CHOICES = [
        ('SELF', 'Self Check-in'),
        ('ADMIN', 'Admin Tracking'),
        ('MANUAL', 'Manual Entry'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=timezone.now)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ABSENT')
    checkin_method = models.CharField(max_length=20, choices=CHECKIN_METHOD_CHOICES, default='ADMIN')
    work_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(blank=True)
    is_checked_out = models.BooleanField(default=False)  # Track if employee has checked out
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.date} - {self.status}"
    
    def calculate_work_hours(self):
        """Calculate total work hours between check-in and check-out"""
        if self.check_in and self.check_out:
            delta = self.check_out - self.check_in
            hours = delta.total_seconds() / 3600
            self.work_hours = round(hours, 2)
            return self.work_hours
        return 0
    
    class Meta:
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']


class LeaveRequest(models.Model):
    """Employee leave requests"""
    LEAVE_TYPES = [
        ('SICK', 'Sick Leave'),
        ('CASUAL', 'Casual Leave'),
        ('ANNUAL', 'Annual Leave'),
        ('MATERNITY', 'Maternity Leave'),
        ('PATERNITY', 'Paternity Leave'),
        ('UNPAID', 'Unpaid Leave'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    approved_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.leave_type} ({self.start_date} to {self.end_date})"
    
    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1
    
    class Meta:
        ordering = ['-created_at']


class AttendanceSettings(models.Model):
    """System-wide attendance configuration"""
    standard_check_in_time = models.TimeField(default='09:00')
    standard_check_out_time = models.TimeField(default='18:00')
    late_threshold_minutes = models.IntegerField(default=15)
    early_departure_threshold_minutes = models.IntegerField(default=15)
    half_day_hours = models.DecimalField(max_digits=4, decimal_places=2, default=4.00)
    full_day_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8.00)
    
    class Meta:
        verbose_name = 'Attendance Settings'
        verbose_name_plural = 'Attendance Settings'
    
    def __str__(self):
        return "Attendance Configuration"


class PresenceTracking(models.Model):
    """
    Tracks employee presence during live recognition scans.
    Used for auto-marking absent/checkout based on consecutive non-detections.
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='presence_tracking')
    date = models.DateField(default=timezone.now)
    scan_count = models.IntegerField(default=0)  # Total scans today
    not_present_count = models.IntegerField(default=0)  # Consecutive "not found" count
    last_seen = models.DateTimeField(null=True, blank=True)  # Last time employee was detected
    last_scan = models.DateTimeField(null=True, blank=True)  # Last scan time
    status = models.CharField(max_length=20, default='UNKNOWN', choices=[
        ('PRESENT', 'Present'),
        ('NOT_PRESENT', 'Not Present'),
        ('UNKNOWN', 'Not Scanned'),
    ])
    auto_marked_absent = models.BooleanField(default=False)  # True if auto-marked absent
    auto_checked_out = models.BooleanField(default=False)  # True if auto-checked out
    
    class Meta:
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.date} - {self.status}"
    
    def reset_not_present_count(self):
        """Reset the not present counter when employee is detected"""
        self.not_present_count = 0
        self.status = 'PRESENT'
        self.last_seen = timezone.now()
        self.save()
    
    def increment_not_present(self):
        """Increment not present counter and return current count"""
        self.not_present_count += 1
        self.status = 'NOT_PRESENT'
        self.last_scan = timezone.now()
        self.save()
        return self.not_present_count
