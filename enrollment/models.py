from django.db import models
from django.contrib.auth.models import User
import os


class Department(models.Model):
    """Department/Team within the organization"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']


class Employee(models.Model):
    """Employee profile with personal details"""
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    ROLE_CHOICES = [
        ('employee', 'Employee'),
        ('admin', 'Admin'),
    ]
    
    # Link to Django User for authentication
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='employee_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    
    employee_id = models.CharField(max_length=50, unique=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='employees')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_joining = models.DateField()
    is_active = models.BooleanField(default=True)
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True)
    
    # Individual working hours settings
    use_custom_hours = models.BooleanField(default=False, help_text="Use custom working hours instead of default")
    custom_check_in_time = models.TimeField(null=True, blank=True, help_text="Custom check-in time")
    custom_check_out_time = models.TimeField(null=True, blank=True, help_text="Custom check-out time")
    custom_full_day_hours = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Custom full day hours")
    custom_half_day_hours = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Custom half day hours")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        """Auto-generate employee_id if not provided"""
        if not self.employee_id:
            # Get the last employee and increment
            last_employee = Employee.objects.all().order_by('id').last()
            if last_employee and last_employee.employee_id:
                # Extract number from last employee_id (e.g., EMP001 -> 1)
                try:
                    last_id_num = int(last_employee.employee_id.replace('EMP', ''))
                    new_id_num = last_id_num + 1
                except:
                    new_id_num = 1
            else:
                new_id_num = 1
            
            # Format as EMP001, EMP002, etc.
            self.employee_id = f'EMP{new_id_num:03d}'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.employee_id} - {self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_check_in_time(self):
        """Get the applicable check-in time for this employee"""
        if self.use_custom_hours and self.custom_check_in_time:
            return self.custom_check_in_time
        from attendance.models import AttendanceSettings
        settings = AttendanceSettings.objects.first()
        return settings.standard_check_in_time if settings else None
    
    def get_check_out_time(self):
        """Get the applicable check-out time for this employee"""
        if self.use_custom_hours and self.custom_check_out_time:
            return self.custom_check_out_time
        from attendance.models import AttendanceSettings
        settings = AttendanceSettings.objects.first()
        return settings.standard_check_out_time if settings else None
    
    def get_full_day_hours(self):
        """Get the applicable full day hours for this employee"""
        if self.use_custom_hours and self.custom_full_day_hours:
            return self.custom_full_day_hours
        from attendance.models import AttendanceSettings
        settings = AttendanceSettings.objects.first()
        return settings.full_day_hours if settings else 8
    
    def get_half_day_hours(self):
        """Get the applicable half day hours for this employee"""
        if self.use_custom_hours and self.custom_half_day_hours:
            return self.custom_half_day_hours
        from attendance.models import AttendanceSettings
        settings = AttendanceSettings.objects.first()
        return settings.half_day_hours if settings else 4
    
    class Meta:
        ordering = ['employee_id']


class FaceEncoding(models.Model):
    """Store 128-dimensional face encodings for each employee"""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='face_encodings')
    encoding = models.BinaryField()  # Store numpy array as binary
    image = models.ImageField(upload_to='face_images/')
    created_at = models.DateTimeField(auto_now_add=True)
    is_primary = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Face encoding for {self.employee.full_name}"
    
    class Meta:
        ordering = ['-is_primary', '-created_at']

