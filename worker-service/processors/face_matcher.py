import cv2
import numpy as np
from PIL import Image
import face_recognition
import logging
from utils.storage import download_file

logger = logging.getLogger(__name__)

class FaceMatcher:
    def __init__(self):
        self.match_threshold = 0.6
    
    def match(self, selfie_path, document_path):
        result = {
            'match_score': 0,
            'liveness_check': False,
            'confidence': 'low'
        }
        
        try:
            selfie_image = download_file(selfie_path)
            document_image = download_file(document_path)
            
            selfie_rgb = cv2.cvtColor(np.array(selfie_image), cv2.COLOR_BGR2RGB)
            document_rgb = cv2.cvtColor(np.array(document_image), cv2.COLOR_BGR2RGB)
            
            selfie_faces = face_recognition.face_locations(selfie_rgb)
            document_faces = face_recognition.face_locations(document_rgb)
            
            if not selfie_faces or not document_faces:
                logger.warning("No faces detected in one or both images")
                return result
            
            selfie_encoding = face_recognition.face_encodings(selfie_rgb, selfie_faces)[0]
            document_encoding = face_recognition.face_encodings(document_rgb, document_faces)[0]
            
            face_distance = face_recognition.face_distance([document_encoding], selfie_encoding)[0]
            match_score = (1 - face_distance) * 100
            result['match_score'] = round(match_score, 2)
            
            if match_score >= 85:
                result['confidence'] = 'high'
            elif match_score >= 70:
                result['confidence'] = 'medium'
            else:
                result['confidence'] = 'low'
            
            result['liveness_check'] = self.check_liveness(selfie_rgb, selfie_faces[0])
            
            return result
            
        except Exception as e:
            logger.error(f"Error in face matching: {str(e)}")
            return result
    
    def check_liveness(self, image, face_location):
        checks_passed = 0
        
        top, right, bottom, left = face_location
        face = image[top:bottom, left:right]
        
        if face.size == 0:
            return False
        
        gray_face = cv2.cvtColor(face, cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(gray_face, cv2.CV_64F).var()
        
        if laplacian_var > 100:
            checks_passed += 1
        
        color_std = np.std(face)
        if color_std > 20:
            checks_passed += 1
        
        edges = cv2.Canny(gray_face, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        if 0.05 < edge_density < 0.15:
            checks_passed += 1
        
        face_height = bottom - top
        face_width = right - left
        face_area = face_height * face_width
        
        if 50000 < face_area < 500000:
            checks_passed += 1
        
        return checks_passed >= 3