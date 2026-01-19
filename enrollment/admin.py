from django.contrib import admin
from .models import Department, Employee, FaceEncoding


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'full_name', 'email', 'department', 'is_active', 'date_of_joining']
    list_filter = ['is_active', 'department', 'gender']
    search_fields = ['employee_id', 'first_name', 'last_name', 'email']
    list_editable = ['is_active']
    ordering = ['employee_id']


@admin.register(FaceEncoding)
class FaceEncodingAdmin(admin.ModelAdmin):
    list_display = ['employee', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['employee__employee_id', 'employee__first_name', 'employee__last_name']

