# AI-Based Face Recognition Attendance System

An automated attendance tracking system using real-time face detection and recognition technology built with Django and OpenCV.

## Features

### 1. **Employee Enrollment Module**
- Register new employees with personal details (ID, name, email, department, etc.)
- Capture and store multiple face encodings per employee
- Upload profile photos
- Manage departments and employee status

### 2. **Live Face Recognition Module**
- Real-time camera feed with face detection
- Automatic face recognition using OpenCV LBPH (Local Binary Pattern Histogram)
- Instant attendance logging upon recognition
- Confidence threshold-based identification
- Duplicate check-in prevention (5-minute cooldown)
- MediaPipe Face Mesh integration for advanced detection

### 3. **Automated Presence Tracking** ⭐ NEW
- Real-time employee presence monitoring during admin scans
- Warning system after 1-2 consecutive non-detections (X/3 counter)
- Auto-mark ABSENT after 3 consecutive non-detections (if no check-in)
- Auto CHECK-OUT after 3 consecutive non-detections (if already checked in)
- Presence tracking dashboard with status indicators
- Per-employee presence history and statistics

### 4. **Attendance Logging Module**
- Automatic check-in/check-out timestamping
- Smart status determination (Present, Late, Absent, Half-Day)
- Configurable attendance rules and thresholds
- Work hours calculation
- Manual and Self check-in methods

### 5. **Admin Dashboard**
- Real-time attendance overview
- Presence tracking table with all employees
- Department-wise attendance breakdown
- Daily attendance trends (7-day history)
- Recent check-in activity feed
- Status badges (Present/Warning/Auto-Absent/Auto-Checkout)

### 6. **Employee Portal**
- Self check-in via face recognition
- Personal attendance history
- Profile management
- Today's status view

### 7. **Reports Generation Module**
- Daily, weekly, and monthly attendance reports
- Employee-wise attendance summary with presence tracking stats
- Auto-absent and auto-checkout statistics
- Export functionality:
  - CSV format
  - Excel (XLSX) format
  - PDF format
- Customizable date ranges and filters

## Technology Stack

- **Backend:** Python 3.10+ / Django 5.0+
- **Computer Vision:** OpenCV with contrib modules (LBPH Face Recognizer)
- **Face Detection:** MediaPipe Face Mesh (468 3D landmarks)
- **Frontend:** HTML5, CSS3, Bootstrap 5, Bootstrap Icons
- **Database:** SQLite (default) - MySQL/PostgreSQL supported
- **Real-time Communication:** Django Channels + Daphne
- **Reporting:** ReportLab (PDF), OpenPyXL (Excel)

## Installation & Setup

### Prerequisites
- **Python 3.10+** (3.11 or 3.12 recommended)
- **Webcam/Camera** for live recognition
- **Windows 10/11**, Linux, or macOS
- **Visual Studio Build Tools** (Windows only - for C++ compilation if needed)

### Step 1: Clone/Copy Project
```powershell
# Copy project folder to your machine
cd C:\path\to\your\project
```

### Step 2: Create Virtual Environment
```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Database Setup
```powershell
python manage.py makemigrations
python manage.py migrate
```

### Step 5: Create Admin User
```powershell
python manage.py createsuperuser
```
Follow prompts to create admin credentials.

### Step 6: (Optional) Create Employee User Accounts
```powershell
python manage.py create_employee_users
```
Creates login accounts for all employees (password: `employee123`).

### Step 7: Run Development Server
```powershell
python manage.py runserver
```

Access the application at: **http://127.0.0.1:8000/**

## Project Structure

```
AI/
├── face_attendance_system/     # Main project settings
│   ├── settings.py            # Configuration
│   ├── urls.py                # URL routing
│   ├── asgi.py                # ASGI config for Channels
│   └── wsgi.py                # WSGI config
├── accounts/                  # User authentication & employee portal
│   ├── models.py              # User profiles
│   ├── views.py               # Login, portal, self check-in
│   └── urls.py                # Auth URLs
├── enrollment/                # Employee management
│   ├── models.py              # Employee, Department, FaceEncoding
│   ├── views.py               # Enrollment logic
│   ├── forms.py               # Employee & face enrollment forms
│   └── urls.py                # Enrollment URLs
├── attendance/                # Attendance tracking
│   ├── models.py              # AttendanceRecord, LeaveRequest, PresenceTracking
│   ├── views.py               # Check-in/out, presence tracking logic
│   └── urls.py                # Attendance URLs
├── recognition/               # Face recognition engine
│   ├── face_utils.py          # LBPH recognition algorithms
│   ├── liveness_detection.py  # MediaPipe liveness detection
│   ├── views.py               # Live video feed & recognition
│   └── urls.py                # Recognition URLs
├── dashboard/                 # Main dashboard
│   └── views.py               # Dashboard statistics
├── reports/                   # Reporting module
│   ├── views.py               # Report generation & export
│   └── urls.py                # Report URLs
├── templates/                 # HTML templates
│   ├── accounts/              # Login, portal templates
│   ├── attendance/            # Attendance dashboard templates
│   ├── enrollment/            # Employee management templates
│   ├── recognition/           # Live recognition templates
│   └── reports/               # Report templates
├── static/                    # CSS, JS, images
├── media/                     # User uploads (photos, face images)
├── face_encodings/            # Trained face models (.pkl, .yml)
├── manage.py                  # Django management script
└── requirements.txt           # Python dependencies
```

## Configuration

### Attendance Settings (Admin Panel)
Navigate to `/admin/attendance/attendancesettings/` to configure:

- **Standard Check-in Time:** Default 09:00 AM
- **Standard Check-out Time:** Default 06:00 PM
- **Late Threshold:** 15 minutes
- **Early Departure Threshold:** 15 minutes
- **Half Day Hours:** 4 hours
- **Full Day Hours:** 8 hours

### Face Recognition Settings (settings.py)
```python
FACE_ENCODINGS_DIR = BASE_DIR / 'face_encodings'
CONFIDENCE_THRESHOLD = 0.6  # Adjust for stricter/looser matching
TIME_ZONE = 'Asia/Kolkata'  # Set your timezone
```

## Usage Guide

### 1. Register Employees
1. Go to `/enrollment/employees/create/`
2. Fill in employee details
3. Upload profile photo
4. Save employee

### 2. Enroll Face Data
1. Navigate to employee detail page
2. Click "Enroll Face"
3. **Option A:** Upload face image
4. **Option B:** Capture via webcam
5. System generates and stores face encoding

### 3. Start Live Recognition
1. Go to `/recognition/live/`
2. Allow browser camera access
3. Face detection starts automatically
4. Recognized employees are auto-checked-in
5. **Presence Scan**: Run periodic scans to track who's present
   - Employees detected → Present (counter resets)
   - Employees NOT detected → Warning counter increments (X/3)
   - 3 consecutive non-detections → Auto-ABSENT or Auto-CHECKOUT

### 4. View Attendance
- **Dashboard:** `/attendance/` - Overview with presence tracking table
- **Date View:** `/attendance/date/` - Attendance for specific date
- **Employee View:** `/attendance/employee/<id>/` - Individual history with presence stats
- **Employee Profile:** `/enrollment/employees/<id>/` - Full profile with 30-day stats

### 5. Employee Self-Service
1. Employees log in at `/accounts/login/`
2. Access portal at `/accounts/portal/`
3. Self check-in via face recognition
4. View personal attendance history

### 6. Generate Reports
1. Go to `/reports/attendance/`
2. Select date range and filters
3. Click "Export as CSV/Excel/PDF"

## Face Recognition Algorithm

This system uses **OpenCV's LBPH (Local Binary Pattern Histogram) Face Recognizer** instead of deep learning models like dlib/face_recognition. 

**Advantages:**
- No external dependencies (cmake, dlib)
- Fast training and recognition
- Works on CPU without GPU
- Lightweight and portable

**How it works:**
1. Face detection using Haar Cascades
2. Face ROI extracted and resized to 200x200
3. LBPH creates histogram-based encoding
4. Recognition by comparing histograms
5. Confidence score < 70 indicates good match

## API Endpoints

- `GET /enrollment/employees/` - List all employees
- `POST /enrollment/employees/create/` - Create employee
- `POST /enrollment/employees/<id>/enroll-face/` - Upload face image
- `POST /enrollment/employees/<id>/capture-webcam/` - Capture from webcam
- `GET /recognition/video-feed/` - Live camera stream
- `POST /recognition/reload-encodings/` - Reload face database
- `GET /attendance/` - Attendance dashboard
- `POST /attendance/mark/<id>/<action>/` - Manual check-in/out
- `GET /reports/attendance/` - Generate reports

## Troubleshooting

### Camera not detected
- Ensure webcam is properly connected
- Check browser permissions for camera access
- Try different camera index in recognition views

### Face not recognized
- Ensure good lighting conditions
- Face should be clearly visible and frontal
- Add multiple face encodings for better accuracy
- Lower CONFIDENCE_THRESHOLD in settings

### Slow recognition
- Reduce camera resolution in views.py
- Increase `process_every_n_frames` value
- Use LBPH instead of deep learning models

## Default Credentials

| User Type | Username | Password |
|-----------|----------|----------|
| Admin | (your superuser) | (your password) |
| Employees | employee_<id>@company.com | employee123 |

## Troubleshooting

### Camera not detected
- Ensure webcam is properly connected
- Check browser permissions for camera access
- Try different browser (Chrome recommended)

### Face not recognized
- Ensure good lighting conditions
- Face should be clearly visible and frontal
- Add multiple face encodings (3-5 recommended)
- Adjust confidence threshold in recognition settings

### MediaPipe errors
```powershell
pip install --upgrade mediapipe
```

### OpenCV build errors (Windows)
```powershell
pip install opencv-contrib-python --no-cache-dir
```

## Files to Keep When Transferring

| Item | Keep? | Description |
|------|-------|-------------|
| `db.sqlite3` | ✅ Yes | Database with all data |
| `media/` | ✅ Yes | Employee photos |
| `face_encodings/` | ✅ Yes | Trained face models |
| `.venv/` | ❌ No | Recreate on new PC |
| `__pycache__/` | ❌ No | Auto-generated |

## License

This project is for educational and internal use.

## Credits

Developed using:
- Django - Web Framework
- OpenCV - Computer Vision
- MediaPipe - Face Detection
- Bootstrap 5 - UI Framework

## Documentation Links

- Django: https://docs.djangoproject.com/
- OpenCV: https://docs.opencv.org/
- MediaPipe: https://developers.google.com/mediapipe
