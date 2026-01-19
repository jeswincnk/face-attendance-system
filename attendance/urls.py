from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.attendance_dashboard, name='attendance_dashboard'),
    path('mark/<int:employee_id>/<str:action>/', views.mark_attendance, name='mark_attendance'),
    path('employee/<int:employee_id>/', views.attendance_record_employee, name='attendance_record_employee'),
    path('date/', views.attendance_record_date, name='attendance_record_date'),
    path('leave-requests/', views.leave_request_list, name='leave_request_list'),
    path('settings/', views.settings_view, name='settings'),
]
