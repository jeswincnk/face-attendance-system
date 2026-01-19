from django.urls import path
from . import views

app_name = 'recognition'

urlpatterns = [
    path('live/', views.live_recognition, name='live_recognition'),
    path('video-feed/', views.video_feed, name='video_feed'),
    path('reload-encodings/', views.reload_encodings, name='reload_encodings'),
    path('stop-camera/', views.stop_camera, name='stop_camera'),
    path('get-status/', views.get_recognition_status, name='get_recognition_status'),
    path('test-camera/', views.test_camera, name='test_camera'),
    path('settings/', views.recognition_settings, name='recognition_settings'),
    path('settings/update/', views.update_settings, name='update_settings'),
    path('settings/employee-hours/', views.update_employee_hours, name='update_employee_hours'),
    
    # Presence tracking / auto-attendance
    path('presence-scan/', views.run_presence_scan, name='run_presence_scan'),
    path('presence-status/', views.get_presence_status, name='get_presence_status'),
    path('presence-reset/', views.reset_presence_tracking, name='reset_presence_tracking'),
    path('attendance-stats/', views.get_attendance_statistics, name='attendance_statistics'),
]
