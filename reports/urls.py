from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_home, name='home'),
    path('attendance/', views.attendance_report, name='attendance_report'),
    path('employee-summary/', views.employee_summary_report, name='employee_summary'),
    path('export/', views.export_report, name='export_report'),
]
