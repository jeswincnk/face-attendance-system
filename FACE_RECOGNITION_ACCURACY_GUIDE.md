"""
Face Recognition Accuracy Tips and Troubleshooting Guide
========================================================

## Current Settings (Updated for Better Accuracy):
- LBPH Confidence Threshold: 50 (lower is better, stricter matching)
- Face Detection: More neighbors required (6 vs 5)
- Minimum Face Size: 100x100 pixels (larger for better quality)
- Histogram Equalization: Applied for consistent lighting

## To Improve Face Recognition Accuracy:

### 1. During Face Enrollment:
   - Ensure good, even lighting (no shadows on face)
   - Face the camera directly (frontal view)
   - Keep face at least 50cm from camera
   - Remove glasses if possible
   - Avoid extreme facial expressions
   - Ensure clear, high-resolution images
   - Capture multiple angles (3-5 images per person)

### 2. During Recognition:
   - Same lighting conditions as enrollment
   - Same distance from camera
   - Look directly at camera
   - Keep face still for 2-3 seconds

### 3. If Still Getting Wrong Matches:

   Option A: Re-enroll faces with better quality
   - Go to: http://127.0.0.1:8000/enrollment/employees/
   - Click on employee
   - Click "Enroll New Face"
   - Capture 3-5 clear images in good lighting

   Option B: Adjust threshold (in settings.py):
   - Lower FACE_RECOGNITION_CONFIDENCE_THRESHOLD (e.g., 40 for stricter)
   - Higher value = more lenient matching
   - Lower value = stricter matching

   Option C: Delete incorrect face encodings:
   - Go to employee details
   - Review enrolled faces
   - Delete poor quality or incorrect images

### 4. Testing Recognition:
   - After re-enrollment, reload encodings on live page
   - Test with one person at a time
   - Ensure "Unknown" appears for non-enrolled faces

### 5. Current Threshold Explanation:
   - Confidence < 50: Recognized (high confidence match)
   - Confidence 50-70: Uncertain (not recognized, but similar)
   - Confidence > 70: Different person (not recognized)

### 6. Quick Fix Commands:
   ```python
   # In Django shell (python manage.py shell):
   from enrollment.models import FaceEncoding
   
   # See all face encodings:
   FaceEncoding.objects.all()
   
   # Delete specific encoding:
   FaceEncoding.objects.filter(employee__employee_id='EMP001').delete()
   
   # Count faces per employee:
   from django.db.models import Count
   from enrollment.models import Employee
   Employee.objects.annotate(face_count=Count('face_encodings')).values('employee_id', 'full_name', 'face_count')
   ```

### 7. Recommended Face Count:
   - Minimum: 2-3 faces per person
   - Optimal: 5-7 faces (different angles/lighting)
   - Maximum: 10 faces (diminishing returns)

## Changes Made:
1. ✅ Stricter confidence threshold (50 instead of 70)
2. ✅ Better face detection (more neighbors, larger min size)
3. ✅ Histogram equalization for consistent lighting
4. ✅ Enhanced LBPH parameters
5. ✅ Debug logging for confidence scores
6. ✅ Smaller scale factor for better detection

## Next Steps:
1. Clear browser cache and reload recognition page
2. Click "Reload Encodings" button
3. Test with one enrolled person
4. If wrong person shows, reduce threshold to 40-45
5. Re-enroll faces if needed
