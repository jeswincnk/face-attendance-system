from django.contrib import admin
from .models import AttendanceRecord, LeaveRequest, AttendanceSettings


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'check_in', 'check_out', 'work_hours', 'status']
    list_filter = ['status', 'date']
    search_fields = ['employee__employee_id', 'employee__first_name', 'employee__last_name']
    date_hierarchy = 'date'
    ordering = ['-date', 'employee']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'status', 'duration_days']
    list_filter = ['status', 'leave_type', 'start_date']
    search_fields = ['employee__employee_id', 'employee__first_name', 'employee__last_name']
    date_hierarchy = 'start_date'


@admin.register(AttendanceSettings)
class AttendanceSettingsAdmin(admin.ModelAdmin):
    list_display = ['standard_check_in_time', 'standard_check_out_time', 'late_threshold_minutes', 'full_day_hours']
    
    def has_add_permission(self, request):
        # Only allow one settings instance
        return not AttendanceSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False

