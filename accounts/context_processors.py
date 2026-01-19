"""
Context processor to add user role information to all templates
"""

def user_role(request):
    """Add is_admin flag to template context"""
    is_admin = False
    has_employee_profile = False
    
    if request.user.is_authenticated:
        if request.user.is_superuser:
            is_admin = True
        else:
            try:
                employee = request.user.employee_profile
                has_employee_profile = True
                if employee.role == 'admin':
                    is_admin = True
            except:
                pass
    
    return {
        'is_admin': is_admin,
        'has_employee_profile': has_employee_profile
    }
