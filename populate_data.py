"""
Populate database with sample data
Run: python manage.py shell < populate_data.py
"""

from enrollment.models import Department, Employee
from django.utils import timezone
from datetime import date

print("Creating departments...")

# Create departments
departments_data = [
    {'name': 'Engineering', 'description': 'Software development and engineering team'},
    {'name': 'Human Resources', 'description': 'HR and recruitment team'},
    {'name': 'Sales', 'description': 'Sales and business development team'},
    {'name': 'Marketing', 'description': 'Marketing and communications team'},
    {'name': 'IT Support', 'description': 'Technical support and infrastructure team'},
]

for dept_data in departments_data:
    dept, created = Department.objects.get_or_create(
        name=dept_data['name'],
        defaults={'description': dept_data['description']}
    )
    if created:
        print(f"✓ Created department: {dept.name}")
    else:
        print(f"- Department already exists: {dept.name}")

print(f"\nTotal departments: {Department.objects.count()}")
print(f"Total employees: {Employee.objects.count()}")
print("\n✅ Database populated successfully!")
print("\nNext steps:")
print("1. Go to http://127.0.0.1:8000/enrollment/employees/")
print("2. Click 'Add New Employee' to register employees")
print("3. Enroll face data for each employee")
print("4. Start using the face recognition system!")
