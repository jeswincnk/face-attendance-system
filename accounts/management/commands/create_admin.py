from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from enrollment.models import Department, Employee
import os


class Command(BaseCommand):
    help = 'Create default admin user and sample data if not exists'

    def handle(self, *args, **options):
        # Create superuser
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@faceattendance.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Admin@123')

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created successfully!'))
        else:
            self.stdout.write(self.style.WARNING(f'Superuser "{username}" already exists.'))
        
        # Create default department if not exists
        dept, created = Department.objects.get_or_create(
            name='General',
            defaults={'description': 'General Department'}
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Default department "General" created!'))
        
        # Create sample employee if no employees exist
        if not Employee.objects.exists():
            Employee.objects.create(
                employee_id='EMP001',
                first_name='Demo',
                last_name='User',
                email='demo@faceattendance.com',
                department=dept,
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS('Sample employee "Demo User" created!'))

