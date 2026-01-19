from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from enrollment.models import Employee


class Command(BaseCommand):
    help = 'Create Django user accounts for existing employees'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default='employee123',
            help='Default password for all created users (default: employee123)'
        )

    def handle(self, *args, **options):
        default_password = options['password']
        
        employees = Employee.objects.filter(user__isnull=True)
        
        if not employees.exists():
            self.stdout.write(self.style.WARNING('No employees without user accounts found.'))
            return
        
        created_count = 0
        
        for employee in employees:
            # Create username from employee_id or email
            username = employee.employee_id.lower()
            
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(f'User {username} already exists, skipping...')
                continue
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=employee.email,
                password=default_password,
                first_name=employee.first_name,
                last_name=employee.last_name
            )
            
            # Link employee to user
            employee.user = user
            employee.save()
            
            created_count += 1
            self.stdout.write(f'Created user: {username} for {employee.full_name}')
        
        self.stdout.write(self.style.SUCCESS(
            f'\nSuccessfully created {created_count} user accounts.'
            f'\nDefault password: {default_password}'
            f'\nUsers can login with their employee ID (e.g., emp001) as username.'
        ))
