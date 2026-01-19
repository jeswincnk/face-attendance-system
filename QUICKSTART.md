# 🚀 Quick Start Guide

## Getting Started in 5 Minutes

### 1. Create Superuser (Admin Account)
```powershell
python manage.py createsuperuser
```
Enter your desired username, email, and password.

### 2. Start the Development Server
```powershell
python manage.py runserver
```

### 3. Access the Application
Open your browser and navigate to:
- **Main App:** http://127.0.0.1:8000/
- **Admin Panel:** http://127.0.0.1:8000/admin/

Login with the superuser credentials you just created.

### 4. Initial Setup Steps

#### Step 1: Create Departments
1. Go to Admin Panel → Departments → Add Department
2. Create departments like: "Engineering", "HR", "Sales", etc.

#### Step 2: Add Employees
1. Navigate to: http://127.0.0.1:8000/enrollment/employees/
2. Click "Add New Employee"
3. Fill in employee details:
   - Employee ID (e.g., EMP001)
   - First Name & Last Name
   - Email & Phone
   - Department
   - Date of Joining
   - Upload profile photo (optional)
4. Click Save

#### Step 3: Enroll Face Data
For each employee:
1. Go to their employee detail page
2. Click "Enroll Face"
3. Choose one of two options:
   - **Upload Image:** Browse and upload a clear face photo
   - **Capture from Webcam:** Click capture button to take photo from camera
4. System will detect face and save encoding
5. Repeat 2-3 times per employee for better accuracy

#### Step 4: Configure Attendance Settings
1. Go to Admin Panel → Attendance Settings
2. Set:
   - Standard check-in time (e.g., 09:00 AM)
   - Standard check-out time (e.g., 06:00 PM)
   - Late arrival threshold (e.g., 15 minutes)
   - Full day hours (e.g., 8 hours)
3. Save changes

### 5. Start Using the System

#### Live Recognition
1. Go to: http://127.0.0.1:8000/recognition/live/
2. Allow browser access to camera
3. Face the camera
4. System will automatically:
   - Detect your face
   - Recognize you
   - Log your attendance
   - Show your name and confidence score

#### View Attendance
- **Dashboard:** Real-time overview of today's attendance
- **Attendance Page:** View detailed records by date or employee
- **Reports:** Generate exportable reports (CSV, Excel, PDF)

### 6. Common Tasks

#### Manual Check-in/out
If automatic recognition isn't available:
1. Go to Attendance Dashboard
2. Find employee in list
3. Click "Check In" or "Check Out" button

#### Generate Monthly Report
1. Navigate to Reports section
2. Select date range (e.g., current month)
3. Choose filters (department, employee)
4. Click "Export as PDF" or "Export as Excel"

#### Add More Face Encodings
To improve recognition accuracy:
1. Go to employee detail page
2. Click "Enroll Face" again
3. Capture face from different angles or lighting conditions
4. Save each encoding

### 7. Test the System

#### Test Scenario:
1. Add a test employee with your own details
2. Enroll your face (take 2-3 photos)
3. Go to Live Recognition page
4. Face the camera
5. Verify:
   - Green box appears around your face
   - Your name displays correctly
   - Check-in is logged in attendance records
6. Check Dashboard to see your attendance

### 8. Troubleshooting

**Camera not working?**
- Check browser permissions
- Ensure no other app is using the camera
- Try refreshing the page

**Face not recognized?**
- Ensure good lighting
- Face camera directly
- Add more face encodings
- Check confidence threshold in settings.py

**No employees showing?**
- Verify employees are marked as "Active"
- Check if face encodings are saved
- Click "Reload Face Database" button

### 9. System Requirements

- Windows 10/11 (or Linux/macOS)
- Python 3.8+ installed
- Webcam/camera access
- Modern browser (Chrome, Firefox, Edge)

### 10. Next Steps

Once basic setup is complete:
- Add all your employees
- Enroll multiple face images per person
- Test recognition with different lighting
- Set up regular report generation
- Configure leave management
- Customize attendance rules

## Need Help?

Refer to the main [README.md](README.md) for detailed documentation.

## Happy Tracking! 🎉
