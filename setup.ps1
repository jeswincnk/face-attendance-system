# Face Recognition Attendance System - Setup Script
# Run this script to set up the project automatically

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Face Recognition Attendance System" -ForegroundColor Cyan
Write-Host "Automated Setup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-Not (Test-Path ".\.venv")) {
    Write-Host "[1/6] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "[1/6] Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "[2/6] Activating virtual environment..." -ForegroundColor Yellow
.\.venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "[3/6] Installing dependencies..." -ForegroundColor Yellow
.\.venv\Scripts\pip.exe install -r requirements.txt
Write-Host "✓ Dependencies installed" -ForegroundColor Green

# Create migrations
Write-Host "[4/6] Creating database migrations..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe manage.py makemigrations
Write-Host "✓ Migrations created" -ForegroundColor Green

# Apply migrations
Write-Host "[5/6] Applying migrations to database..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe manage.py migrate
Write-Host "✓ Database initialized" -ForegroundColor Green

# Check system
Write-Host "[6/6] Running system check..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe manage.py check
Write-Host "✓ System check passed" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Create superuser:" -ForegroundColor White
Write-Host "   python manage.py createsuperuser" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Run development server:" -ForegroundColor White
Write-Host "   python manage.py runserver" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Access application:" -ForegroundColor White
Write-Host "   http://127.0.0.1:8000/" -ForegroundColor Gray
Write-Host ""
Write-Host "For detailed instructions, see QUICKSTART.md" -ForegroundColor Cyan
Write-Host ""
