"""
Liveness Detection Module using MediaPipe Face Mesh
Provides anti-spoofing capabilities with 3D facial landmarks

Features:
- Blink detection using Eye Aspect Ratio (EAR)
- Head pose estimation (yaw, pitch, roll)
- Face mesh with 468 3D landmarks
- Texture analysis for photo detection
"""

import cv2
import numpy as np
try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    mp = None

try:
    from scipy.spatial import distance
except ImportError:
    distance = None

from collections import deque
import time


class LivenessDetector:
    """
    Advanced liveness detection using MediaPipe Face Mesh
    Detects if a real person is in front of the camera vs a photo/video
    """
    
    def __init__(self):
        if not MEDIAPIPE_AVAILABLE:
            self.enabled = False
            return
        self.enabled = True
    
    # Eye landmark indices for MediaPipe Face Mesh
    # Left eye
    LEFT_EYE = [362, 385, 387, 263, 373, 380]
    # Right eye
    RIGHT_EYE = [33, 160, 158, 133, 153, 144]
    
    # Face outline for head pose
    FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
                 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
                 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    
    # 3D Model points for head pose estimation
    MODEL_POINTS = np.array([
        (0.0, 0.0, 0.0),             # Nose tip
        (0.0, -330.0, -65.0),        # Chin
        (-225.0, 170.0, -135.0),     # Left eye corner
        (225.0, 170.0, -135.0),      # Right eye corner
        (-150.0, -150.0, -125.0),    # Left mouth corner
        (150.0, -150.0, -125.0)      # Right mouth corner
    ], dtype=np.float64)
    
    def __init__(self):
        # Initialize MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,  # Enable iris landmarks
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # Blink detection parameters
        self.EAR_THRESHOLD = 0.21  # Eye Aspect Ratio threshold for blink
        self.CONSEC_FRAMES = 2     # Consecutive frames for blink
        self.blink_counter = 0
        self.total_blinks = 0
        self.ear_history = deque(maxlen=30)  # Store EAR history
        
        # Head movement tracking
        self.head_pose_history = deque(maxlen=30)
        self.movement_detected = False
        
        # Liveness challenge state
        self.challenge_start_time = None
        self.challenge_type = None  # 'blink', 'turn_left', 'turn_right', 'nod'
        self.challenge_completed = False
        self.challenges_passed = 0
        
        # Texture analysis for photo detection
        self.texture_scores = deque(maxlen=10)
        
    def calculate_ear(self, eye_landmarks):
        """
        Calculate Eye Aspect Ratio (EAR)
        EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        Lower EAR = eye more closed
        """
        # Vertical distances
        v1 = distance.euclidean(eye_landmarks[1], eye_landmarks[5])
        v2 = distance.euclidean(eye_landmarks[2], eye_landmarks[4])
        # Horizontal distance
        h = distance.euclidean(eye_landmarks[0], eye_landmarks[3])
        
        if h == 0:
            return 0
        
        ear = (v1 + v2) / (2.0 * h)
        return ear
    
    def get_eye_landmarks(self, landmarks, eye_indices, img_w, img_h):
        """Extract eye landmarks from face mesh"""
        eye_points = []
        for idx in eye_indices:
            lm = landmarks[idx]
            x = int(lm.x * img_w)
            y = int(lm.y * img_h)
            eye_points.append((x, y))
        return np.array(eye_points)
    
    def estimate_head_pose(self, landmarks, img_w, img_h):
        """
        Estimate head pose (yaw, pitch, roll) using 3D-2D point correspondence
        Returns: (yaw, pitch, roll) in degrees
        """
        # 2D image points
        image_points = np.array([
            (landmarks[1].x * img_w, landmarks[1].y * img_h),      # Nose tip
            (landmarks[152].x * img_w, landmarks[152].y * img_h),  # Chin
            (landmarks[263].x * img_w, landmarks[263].y * img_h),  # Left eye corner
            (landmarks[33].x * img_w, landmarks[33].y * img_h),    # Right eye corner
            (landmarks[287].x * img_w, landmarks[287].y * img_h),  # Left mouth corner
            (landmarks[57].x * img_w, landmarks[57].y * img_h)     # Right mouth corner
        ], dtype=np.float64)
        
        # Camera matrix (approximation)
        focal_length = img_w
        center = (img_w / 2, img_h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float64)
        
        dist_coeffs = np.zeros((4, 1))  # Assuming no lens distortion
        
        # Solve PnP
        success, rotation_vector, translation_vector = cv2.solvePnP(
            self.MODEL_POINTS,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        
        if not success:
            return 0, 0, 0
        
        # Convert rotation vector to rotation matrix
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        
        # Get Euler angles
        proj_matrix = np.hstack((rotation_matrix, translation_vector))
        _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(proj_matrix)
        
        pitch = euler_angles[0][0]
        yaw = euler_angles[1][0]
        roll = euler_angles[2][0]
        
        return yaw, pitch, roll
    
    def analyze_texture(self, face_roi):
        """
        Analyze face texture to detect photos/screens
        Real faces have more texture variation than printed photos
        """
        if face_roi is None or face_roi.size == 0:
            return 0
        
        # Convert to grayscale if needed
        if len(face_roi.shape) == 3:
            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_roi
        
        # Calculate Laplacian variance (measure of texture/sharpness)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()
        
        # Local Binary Pattern histogram for texture
        # Higher variance typically indicates real face
        return variance
    
    def detect_blink(self, ear):
        """
        Detect blink based on EAR
        Returns: True if blink detected
        """
        self.ear_history.append(ear)
        
        if ear < self.EAR_THRESHOLD:
            self.blink_counter += 1
        else:
            if self.blink_counter >= self.CONSEC_FRAMES:
                self.total_blinks += 1
                self.blink_counter = 0
                return True
            self.blink_counter = 0
        
        return False
    
    def start_challenge(self, challenge_type='blink'):
        """Start a liveness challenge"""
        self.challenge_type = challenge_type
        self.challenge_start_time = time.time()
        self.challenge_completed = False
        self.total_blinks = 0  # Reset blink counter
        
    def check_challenge(self, result, challenge_type):
        """
        Check if a liveness challenge is completed based on frame result
        This is a stateless check that can be used per-frame
        
        Args:
            result: dict from process_frame()
            challenge_type: 'blink', 'turn_left', 'turn_right', 'nod'
        
        Returns: bool - True if challenge passed
        """
        if not result.get('face_detected'):
            return False
        
        yaw, pitch, roll = result.get('head_pose', (0, 0, 0))
        ear = result.get('ear', 0.3)
        blink_detected = result.get('blink_detected', False)
        
        if challenge_type == 'blink':
            # Check if eyes are closed (low EAR indicates blink in progress)
            # EAR below threshold means eyes are closed
            return ear < self.EAR_THRESHOLD
            
        elif challenge_type == 'turn_left':
            # Head turned left (positive yaw)
            return yaw > 15
            
        elif challenge_type == 'turn_right':
            # Head turned right (negative yaw)
            return yaw < -15
            
        elif challenge_type == 'nod':
            # Head nodded (pitch change)
            return abs(pitch) > 12
        
        return False
    
    def check_challenge_with_state(self, yaw, pitch, roll):
        """
        Check if the current liveness challenge is completed (stateful version)
        Returns: (completed, message)
        """
        if self.challenge_type is None:
            return False, "No challenge active"
        
        elapsed = time.time() - self.challenge_start_time
        
        # Timeout after 10 seconds
        if elapsed > 10:
            return False, "Challenge timeout"
        
        if self.challenge_type == 'blink':
            if self.total_blinks >= 1:
                self.challenge_completed = True
                return True, "Blink detected! ✓"
            return False, "Please blink"
            
        elif self.challenge_type == 'turn_left':
            if yaw > 15:  # Head turned left
                self.challenge_completed = True
                return True, "Left turn detected! ✓"
            return False, "Please turn head LEFT"
            
        elif self.challenge_type == 'turn_right':
            if yaw < -15:  # Head turned right
                self.challenge_completed = True
                return True, "Right turn detected! ✓"
            return False, "Please turn head RIGHT"
            
        elif self.challenge_type == 'nod':
            if abs(pitch) > 12:  # Head nodded
                self.challenge_completed = True
                return True, "Nod detected! ✓"
            return False, "Please nod your head"
        
        return False, "Unknown challenge"
    
    def process_frame(self, frame, draw_landmarks=True):
        """
        Process a video frame for liveness detection
        
        Returns: dict with:
            - is_live: bool - True if likely a real person
            - face_detected: bool
            - blink_count: int
            - ear: float - Eye Aspect Ratio
            - head_pose: (yaw, pitch, roll)
            - texture_score: float
            - landmarks: face mesh landmarks
            - challenge_status: (completed, message)
        """
        result = {
            'is_live': False,
            'face_detected': False,
            'blink_count': self.total_blinks,
            'ear': 0,
            'head_pose': (0, 0, 0),
            'texture_score': 0,
            'landmarks': None,
            'challenge_status': (False, ""),
            'frame': frame.copy()
        }
        
        img_h, img_w = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process with MediaPipe
        mesh_results = self.face_mesh.process(rgb_frame)
        
        if not mesh_results.multi_face_landmarks:
            return result
        
        result['face_detected'] = True
        landmarks = mesh_results.multi_face_landmarks[0].landmark
        result['landmarks'] = landmarks
        
        # Calculate EAR for both eyes
        left_eye = self.get_eye_landmarks(landmarks, self.LEFT_EYE, img_w, img_h)
        right_eye = self.get_eye_landmarks(landmarks, self.RIGHT_EYE, img_w, img_h)
        
        left_ear = self.calculate_ear(left_eye)
        right_ear = self.calculate_ear(right_eye)
        avg_ear = (left_ear + right_ear) / 2.0
        result['ear'] = avg_ear
        
        # Detect blink - also add blink_detected flag for single frame check
        blinked = self.detect_blink(avg_ear)
        result['blink_count'] = self.total_blinks
        result['blink_detected'] = avg_ear < self.EAR_THRESHOLD  # Eyes currently closed
        
        # Estimate head pose
        yaw, pitch, roll = self.estimate_head_pose(landmarks, img_w, img_h)
        result['head_pose'] = (yaw, pitch, roll)
        self.head_pose_history.append((yaw, pitch, roll))
        
        # Analyze texture (extract face ROI first)
        # Get face bounding box from landmarks
        x_coords = [lm.x * img_w for lm in landmarks]
        y_coords = [lm.y * img_h for lm in landmarks]
        x_min, x_max = int(min(x_coords)), int(max(x_coords))
        y_min, y_max = int(min(y_coords)), int(max(y_coords))
        
        # Add padding
        padding = 10
        x_min = max(0, x_min - padding)
        y_min = max(0, y_min - padding)
        x_max = min(img_w, x_max + padding)
        y_max = min(img_h, y_max + padding)
        
        face_roi = frame[y_min:y_max, x_min:x_max]
        texture_score = self.analyze_texture(face_roi)
        self.texture_scores.append(texture_score)
        result['texture_score'] = texture_score
        
        # Check challenge if active (using stateful method)
        if self.challenge_type:
            completed, message = self.check_challenge_with_state(yaw, pitch, roll)
            result['challenge_status'] = (completed, message)
        
        # Determine liveness based on multiple factors
        avg_texture = np.mean(self.texture_scores) if self.texture_scores else 0
        
        # Liveness criteria:
        # 1. Texture score above threshold (not a flat photo)
        # 2. Some head movement variation (not perfectly still like a photo)
        # 3. EAR variation (eyes naturally move)
        
        texture_ok = avg_texture > 50  # Real faces typically have variance > 50
        
        ear_variance = np.var(self.ear_history) if len(self.ear_history) > 5 else 0
        ear_ok = ear_variance > 0.0001  # Eyes naturally have micro-movements
        
        pose_variance = 0
        if len(self.head_pose_history) > 5:
            yaws = [p[0] for p in self.head_pose_history]
            pose_variance = np.var(yaws)
        pose_ok = pose_variance > 0.1  # Head naturally has micro-movements
        
        # Combined liveness score
        liveness_score = sum([texture_ok, ear_ok, pose_ok])
        result['is_live'] = liveness_score >= 2  # At least 2 of 3 criteria
        
        # Draw landmarks if requested
        if draw_landmarks:
            output_frame = result['frame']
            
            # Draw face mesh
            self.mp_drawing.draw_landmarks(
                image=output_frame,
                landmark_list=mesh_results.multi_face_landmarks[0],
                connections=self.mp_face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_tesselation_style()
            )
            
            # Draw eye contours
            self.mp_drawing.draw_landmarks(
                image=output_frame,
                landmark_list=mesh_results.multi_face_landmarks[0],
                connections=self.mp_face_mesh.FACEMESH_LEFT_EYE,
                landmark_drawing_spec=None,
                connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_contours_style()
            )
            self.mp_drawing.draw_landmarks(
                image=output_frame,
                landmark_list=mesh_results.multi_face_landmarks[0],
                connections=self.mp_face_mesh.FACEMESH_RIGHT_EYE,
                landmark_drawing_spec=None,
                connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_contours_style()
            )
            
            # Draw info text
            cv2.putText(output_frame, f"EAR: {avg_ear:.3f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(output_frame, f"Blinks: {self.total_blinks}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(output_frame, f"Yaw: {yaw:.1f} Pitch: {pitch:.1f}", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(output_frame, f"Texture: {texture_score:.1f}", (10, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Liveness indicator
            color = (0, 255, 0) if result['is_live'] else (0, 0, 255)
            status = "LIVE" if result['is_live'] else "CHECK"
            cv2.putText(output_frame, status, (img_w - 100, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            
            result['frame'] = output_frame
        
        return result
    
    def get_face_embedding(self, landmarks, img_w, img_h):
        """
        Generate a 3D face embedding from MediaPipe landmarks
        This can be used for face recognition instead of LBPH
        
        Returns: numpy array of 468*3 = 1404 dimensional embedding
        """
        if landmarks is None:
            return None
        
        # Extract normalized 3D coordinates
        embedding = []
        for lm in landmarks:
            # Normalize to [-1, 1] range
            x = (lm.x - 0.5) * 2
            y = (lm.y - 0.5) * 2
            z = lm.z * 2  # Z is already normalized
            embedding.extend([x, y, z])
        
        return np.array(embedding, dtype=np.float32)
    
    def reset(self):
        """Reset all counters and history"""
        self.blink_counter = 0
        self.total_blinks = 0
        self.ear_history.clear()
        self.head_pose_history.clear()
        self.texture_scores.clear()
        self.challenge_type = None
        self.challenge_completed = False
        self.challenge_start_time = None
        self.challenges_passed = 0


# Singleton instance
_liveness_detector = None

def get_liveness_detector():
    """Get or create singleton liveness detector"""
    global _liveness_detector
    if _liveness_detector is None:
        _liveness_detector = LivenessDetector()
    return _liveness_detector
