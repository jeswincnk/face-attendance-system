from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('portal/', views.employee_portal, name='employee_portal'),
    path('profile/', views.employee_profile, name='employee_profile'),
    path('self-checkin/', views.self_checkin, name='self_checkin'),
    path('self-checkout/', views.self_checkout, name='self_checkout'),
    path('verify-face/', views.verify_face, name='verify_face'),
    path('my-attendance/', views.my_attendance, name='my_attendance'),
    path('beacon-checkout/', views.beacon_checkout, name='beacon_checkout'),
]
