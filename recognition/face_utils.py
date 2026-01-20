"""
Face recognition utilities using OpenCV DNN and face detection
Simplified approach without face_recognition library dependency
"""

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    cv2 = None
    np = None

import pickle
from pathlib import Path
from django.conf import settings
import os


class FaceRecognitionEngine:
    """Core face recognition engine using OpenCV"""
    
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_employee_ids = []
        self.tolerance = getattr(settings, 'CONFIDENCE_THRESHOLD', 0.7)
        self.lbph_threshold = getattr(settings, 'FACE_RECOGNITION_CONFIDENCE_THRESHOLD', 50)
        self.is_trained = False
        self.recognition_threshold = 65
        
        if not OPENCV_AVAILABLE:
            self.face_cascade = None
            self.face_recognizer = None
            return
        
        # Load face detector with better accuracy
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Initialize face recognizer with optimized parameters for accuracy
        self.face_recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=2,
            neighbors=8,
            grid_x=8,
            grid_y=8,
            threshold=150
        )
    
    def load_encodings_from_db(self):
        """Load all face encodings from database"""
        if not OPENCV_AVAILABLE:
            return
        from enrollment.models import Employee, FaceEncoding
        
        self.known_face_encodings = []
        self.known_face_names = []
        self.known_employee_ids = []
        
        active_employees = Employee.objects.filter(is_active=True)
        print(f"Found {active_employees.count()} active employees")
        
        faces = []
        labels = []
        label_to_employee = {}
        
        for idx, employee in enumerate(active_employees):
            encodings = employee.face_encodings.all()
            print(f"Employee {employee.full_name}: {encodings.count()} face encodings")
            
            for face_enc in encodings:
                try:
                    # Deserialize face image
                    face_data = pickle.loads(face_enc.encoding)
                    
                    # Validate face data
                    if not isinstance(face_data, np.ndarray):
                        print(f"WARNING: Invalid face data for {employee.full_name}")
                        continue
                    
                    # Ensure correct dimensions
                    if face_data.ndim != 2:
                        print(f"WARNING: Face data has wrong dimensions for {employee.full_name}: {face_data.shape}")
                        continue
                    
                    # Apply CLAHE for better contrast consistency
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    face_data = clahe.apply(face_data)
                    # Apply slight blur to reduce noise
                    face_data = cv2.GaussianBlur(face_data, (3, 3), 0)
                    # Normalize pixel values (consistent with recognition)
                    face_data = cv2.normalize(face_data, None, 0, 255, cv2.NORM_MINMAX)
                    faces.append(face_data)
                    labels.append(idx)
                    label_to_employee[idx] = {
                        'name': employee.full_name,
                        'id': employee.id
                    }
                    print(f"Loaded face encoding for {employee.full_name}, shape: {face_data.shape}")
                except Exception as e:
                    print(f"ERROR loading face encoding for {employee.full_name}: {e}")
                    continue
        
        # Train recognizer if we have faces
        if len(faces) > 0 and len(labels) > 0:
            try:
                print(f"Training recognizer with {len(faces)} faces...")
                self.face_recognizer.train(faces, np.array(labels))
                self.is_trained = True
                self.label_to_employee = label_to_employee
                print(f"✓ Recognizer trained successfully with {len(faces)} face encodings")
                return len(faces)
            except Exception as e:
                print(f"ERROR training recognizer: {e}")
                self.is_trained = False
                return 0
        else:
            print("No valid face encodings found to train recognizer")
            self.is_trained = False
        
        return 0
    
    def generate_encoding(self, image_path_or_array):
        """
        Generate face encoding from image
        Returns: (face_data, face_location) or (None, None) if no face found
        """
        # Load image
        if isinstance(image_path_or_array, str):
            image = cv2.imread(image_path_or_array)
        else:
            image = image_path_or_array
        
        if image is None:
            return None, None
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply histogram equalization for better detection
        gray = cv2.equalizeHist(gray)
        
        # Detect faces
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
        )
        
        if len(faces) == 0:
            return None, None
        
        # Get largest face (most likely the main subject)
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest_face
        
        # Add padding
        padding = int(0.1 * w)
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(gray.shape[1], x + w + padding)
        y2 = min(gray.shape[0], y + h + padding)
        
        face_roi = gray[y1:y2, x1:x2]
        
        # Resize to standard size
        face_roi = cv2.resize(face_roi, (200, 200))
        
        # Apply CLAHE for consistent preprocessing (same as recognition)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        face_roi = clahe.apply(face_roi)
        
        # Apply slight blur to reduce noise
        face_roi = cv2.GaussianBlur(face_roi, (3, 3), 0)
        
        # Normalize pixel values (same as recognition)
        face_roi = cv2.normalize(face_roi, None, 0, 255, cv2.NORM_MINMAX)
        
        return face_roi, (x, y, w, h)
    
    def recognize_faces(self, frame):
        """
        Recognize faces in a video frame
        Returns: List of dictionaries with recognition results
        """
        if not self.is_trained:
            print("WARNING: Face recognizer not trained. Please reload encodings.")
            # Still detect faces but mark as unknown
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1,
                minNeighbors=5,    # Higher = only real faces
                minSize=(80, 80),  # Reasonable face size
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            # Return detected faces as unknown
            results = []
            for (x, y, w, h) in faces:
                results.append({
                    'name': 'Unknown - Not Trained',
                    'employee_id': None,
                    'location': (y, x+w, y+h, x),
                    'confidence': 0.0,
                    'raw_confidence': 999.0
                })
            return results
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply histogram equalization to full image for better detection
        gray = cv2.equalizeHist(gray)
        
        # Detect faces - balanced to avoid false positives
        faces = self.face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.1,
            minNeighbors=5,     # Higher = only real faces, fewer false positives
            minSize=(80, 80),   # Reasonable minimum face size
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        results = []
        
        for (x, y, w, h) in faces:
            # Add padding around face for better recognition
            padding = int(0.1 * w)
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(gray.shape[1], x + w + padding)
            y2 = min(gray.shape[0], y + h + padding)
            
            face_roi = gray[y1:y2, x1:x2]
            face_roi = cv2.resize(face_roi, (200, 200))
            
            # Apply CLAHE for better contrast (consistent with training)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            face_roi = clahe.apply(face_roi)
            
            # Apply Gaussian blur to reduce noise
            face_roi = cv2.GaussianBlur(face_roi, (3, 3), 0)
            
            # Normalize pixel values for consistent recognition
            face_roi = cv2.normalize(face_roi, None, 0, 255, cv2.NORM_MINMAX)
            
            # Predict with error handling
            try:
                label, confidence = self.face_recognizer.predict(face_roi)
                
                # Check for invalid confidence values (infinity/nan)
                if not np.isfinite(confidence) or confidence > 10000:
                    print(f"WARNING: Invalid confidence value: {confidence}. Recognizer may not be properly trained.")
                    confidence = 999.0  # Set to high value to mark as unknown
                
            except Exception as e:
                print(f"ERROR during face prediction: {e}")
                label = -1
                confidence = 999.0
            
            # OpenCV's LBPH confidence: lower is better, 0-100+
            # Use stricter threshold for better accuracy
            confidence_score = max(0, (100 - confidence) / 100)
            
            name = "Unknown"
            employee_id = None
            
            # Only accept if confidence is good (< threshold)
            # Lower LBPH confidence = better match (0 is perfect)
            # Threshold 65: Good balance - strict enough to avoid false positives
            # but flexible enough to recognize faces with slight variations
            
            if confidence < self.recognition_threshold and label in self.label_to_employee:
                employee_info = self.label_to_employee[label]
                name = employee_info['name']
                employee_id = employee_info['id']
                print(f"✓ Recognized: {name} (confidence: {confidence:.1f})")
            else:
                if confidence < 100:
                    print(f"? Uncertain face (confidence: {confidence:.1f}, need < {self.recognition_threshold})")
                else:
                    print(f"✗ Unknown face (confidence: {confidence:.1f})")
            
            results.append({
                'name': name,
                'employee_id': employee_id,
                'location': (y, x+w, y+h, x),  # top, right, bottom, left
                'confidence': confidence_score,
                'raw_confidence': min(confidence, 999.0)  # Cap at 999 for display
            })
        
        return results
    
    def recognize_face(self, face_roi, lenient=False):
        """
        Recognize a single face ROI (grayscale)
        Used for self-checkin verification
        Args:
            face_roi: Grayscale face image
            lenient: If True, use more lenient threshold (for self-checkin where user is already logged in)
        Returns: (employee_id, confidence) or (None, None) if not recognized
        """
        if not self.is_trained:
            print("WARNING: Face recognizer not trained")
            return None, None
        
        try:
            # Ensure proper size
            if face_roi.shape[0] != 200 or face_roi.shape[1] != 200:
                face_roi = cv2.resize(face_roi, (200, 200))
            
            # Apply same preprocessing as training
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            face_roi = clahe.apply(face_roi)
            face_roi = cv2.GaussianBlur(face_roi, (3, 3), 0)
            face_roi = cv2.normalize(face_roi, None, 0, 255, cv2.NORM_MINMAX)
            
            # Predict
            label, confidence = self.face_recognizer.predict(face_roi)
            
            print(f"Face prediction: label={label}, confidence={confidence:.1f}")
            
            # Validate confidence
            if not np.isfinite(confidence) or confidence > 10000:
                return None, None
            
            # Use more lenient threshold for self-checkin (user is already authenticated)
            threshold = 85 if lenient else self.recognition_threshold
            
            # Check if recognized
            if confidence < threshold and label in self.label_to_employee:
                employee_info = self.label_to_employee[label]
                print(f"✓ Recognized: {employee_info['name']} (confidence: {confidence:.1f}, threshold: {threshold})")
                return employee_info['id'], confidence
            else:
                print(f"✗ Face not recognized (confidence: {confidence:.1f}, threshold: {threshold})")
                return None, confidence
                
        except Exception as e:
            print(f"ERROR in recognize_face: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    
    def draw_results(self, frame, results):
        """Draw bounding boxes and names on frame with enhanced visuals"""
        # Add info overlay
        frame_height, frame_width = frame.shape[:2]
        
        # Draw semi-transparent overlay at top for info
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame_width, 50), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        
        # Add status text
        status_text = f"Faces Detected: {len(results)}"
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        for result in results:
            top, right, bottom, left = result['location']
            name = result['name']
            confidence = result['confidence']
            
            # Choose colors based on recognition status
            if name != "Unknown":
                # Green for recognized faces
                box_color = (0, 255, 0)
                label_bg_color = (0, 200, 0)
            else:
                # Red for unknown faces
                box_color = (0, 0, 255)
                label_bg_color = (0, 0, 200)
            
            # Draw thicker box with rounded corners effect
            thickness = 3
            cv2.rectangle(frame, (left, top), (right, bottom), box_color, thickness)
            
            # Draw corner markers for modern look
            corner_length = 20
            # Top-left corner
            cv2.line(frame, (left, top), (left + corner_length, top), box_color, thickness)
            cv2.line(frame, (left, top), (left, top + corner_length), box_color, thickness)
            # Top-right corner
            cv2.line(frame, (right, top), (right - corner_length, top), box_color, thickness)
            cv2.line(frame, (right, top), (right, top + corner_length), box_color, thickness)
            # Bottom-left corner
            cv2.line(frame, (left, bottom), (left + corner_length, bottom), box_color, thickness)
            cv2.line(frame, (left, bottom), (left, bottom - corner_length), box_color, thickness)
            # Bottom-right corner
            cv2.line(frame, (right, bottom), (right - corner_length, bottom), box_color, thickness)
            cv2.line(frame, (right, bottom), (right, bottom - corner_length), box_color, thickness)
            
            # Draw label background with padding
            label = f"{name}" if name != "Unknown" else "Unknown Person"
            raw_conf = result.get('raw_confidence', 0)
            
            # Show both percentage and raw LBPH score
            if name != "Unknown":
                confidence_text = f"Score: {raw_conf:.1f}"  # Show raw LBPH score
            else:
                confidence_text = "---"
            
            # Calculate text size
            font = cv2.FONT_HERSHEY_DUPLEX
            font_scale = 0.7
            font_thickness = 1
            
            (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, font_thickness)
            (conf_width, conf_height), _ = cv2.getTextSize(confidence_text, font, 0.5, 1)
            
            # Draw name label at top
            label_height = text_height + 20
            cv2.rectangle(frame, (left, top - label_height), (right, top), label_bg_color, cv2.FILLED)
            cv2.rectangle(frame, (left, top - label_height), (right, top), box_color, 2)
            
            # Draw text with shadow effect
            text_x = left + 10
            text_y = top - 8
            cv2.putText(frame, label, (text_x + 1, text_y + 1), font, font_scale, (0, 0, 0), font_thickness + 1)
            cv2.putText(frame, label, (text_x, text_y), font, font_scale, (255, 255, 255), font_thickness)
            
            # Draw confidence badge at bottom if recognized
            if name != "Unknown":
                badge_height = 25
                badge_y = bottom
                cv2.rectangle(frame, (left, badge_y), (left + 80, badge_y + badge_height), label_bg_color, cv2.FILLED)
                cv2.rectangle(frame, (left, badge_y), (left + 80, badge_y + badge_height), box_color, 2)
                cv2.putText(frame, confidence_text, (left + 10, badge_y + 18), font, 0.5, (255, 255, 255), 1)
        
        return frame


def save_face_encoding_to_db(employee, image_path, face_data, is_primary=False):
    """Save face encoding to database"""
    from enrollment.models import FaceEncoding
    
    # Serialize face data
    encoding_binary = pickle.dumps(face_data)
    
    # If setting as primary, unset other primary encodings
    if is_primary:
        FaceEncoding.objects.filter(employee=employee, is_primary=True).update(is_primary=False)
    
    # Create face encoding record
    face_encoding = FaceEncoding.objects.create(
        employee=employee,
        encoding=encoding_binary,
        image=image_path,
        is_primary=is_primary
    )
    
    return face_encoding


def verify_face_match(encoding1, encoding2, tolerance=0.6):
    """Verify if two face encodings match"""
    # For OpenCV LBPH, we can't directly compare encodings like this
    # This function is kept for compatibility but returns basic comparison
    distance = np.linalg.norm(encoding1.flatten() - encoding2.flatten())
    return distance <= tolerance * 100, distance
