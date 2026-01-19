from django.urls import path
from . import views

app_name = 'enrollment'

urlpatterns = [
    # Employee URLs
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/create/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/update/', views.employee_update, name='employee_update'),
    path('employees/<int:pk>/delete/', views.employee_delete, name='employee_delete'),
    path('employees/<int:pk>/toggle-status/', views.employee_toggle_status, name='employee_toggle_status'),
    
    # Face enrollment URLs
    path('employees/<int:employee_id>/enroll-face/', views.face_enrollment, name='face_enrollment'),
    path('employees/<int:employee_id>/capture-webcam/', views.capture_face_webcam, name='capture_face_webcam'),
    path(
        'employees/<int:employee_id>/face-encodings/<int:encoding_id>/delete/',
        views.face_encoding_delete,
        name='face_encoding_delete'
    ),
    
    # Department URLs
    path('departments/', views.department_list, name='department_list'),
    path('departments/create/', views.department_create, name='department_create'),
    path('departments/<int:pk>/update/', views.department_update, name='department_update'),
    path('departments/<int:pk>/delete/', views.department_delete, name='department_delete'),
]
