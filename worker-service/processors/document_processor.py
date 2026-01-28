import cv2
import numpy as np
import pytesseract
from PIL import Image
import re
import logging
from utils.storage import download_file

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self):
        self.supported_types = ['passport', 'drivers_license', 'national_id']
    
    def process(self, front_path, back_path=None, document_type='passport'):
        result = {
            'is_valid': False,
            'extracted_data': {},
            'quality_checks': {},
            'fraud_indicators': []
        }
        
        try:
            front_image = download_file(front_path)
            result['quality_checks'] = self.check_image_quality(front_image)
            
            if not result['quality_checks']['acceptable']:
                result['fraud_indicators'].append('Poor image quality')
                return result
            
            extracted_text = self.extract_text(front_image)
            
            if document_type == 'passport':
                result['extracted_data'] = self.parse_passport(extracted_text)
            elif document_type == 'drivers_license':
                result['extracted_data'] = self.parse_drivers_license(extracted_text)
            else:
                result['extracted_data'] = self.parse_generic(extracted_text)
            
            fraud_checks = self.detect_fraud(front_image)
            result['fraud_indicators'] = fraud_checks['indicators']
            
            result['is_valid'] = (
                len(result['fraud_indicators']) == 0 and
                result['quality_checks']['acceptable'] and
                bool(result['extracted_data'])
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return result
    
    def check_image_quality(self, image):
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        brightness = np.mean(gray)
        height, width = gray.shape
        resolution = height * width
        
        return {
            'sharpness': float(laplacian_var),
            'brightness': float(brightness),
            'resolution': resolution,
            'acceptable': (
                laplacian_var > 100 and
                50 < brightness < 200 and
                resolution > 500000
            )
        }
    
    def extract_text(self, image):
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text = pytesseract.image_to_string(binary)
        return text
    
    def parse_passport(self, text):
        data = {}
        lines = text.strip().split('\n')
        mrz_lines = [line for line in lines if len(line) > 30 and line.replace('<', '').isalnum()]
        
        if len(mrz_lines) >= 2:
            mrz = ''.join(mrz_lines[-2:])
            data = self.parse_mrz(mrz)
        
        data['document_number'] = self.extract_pattern(text, r'[A-Z]{1,2}\d{7,9}')
        return data
    
    def parse_mrz(self, mrz):
        data = {}
        try:
            if len(mrz) >= 88:
                data['document_type'] = mrz[0]
                data['country_code'] = mrz[2:5].replace('<', '')
                data['document_number'] = mrz[44:53].replace('<', '')
                
                names_section = mrz[5:44].replace('<', ' ').strip()
                names = names_section.split('  ')
                if len(names) >= 2:
                    data['surname'] = names[0]
                    data['given_names'] = names[1]
                
                dob = mrz[57:63]
                if dob.isdigit():
                    data['date_of_birth'] = f"19{dob[0:2]}-{dob[2:4]}-{dob[4:6]}"
                
                data['sex'] = mrz[64]
                
                expiry = mrz[65:71]
                if expiry.isdigit():
                    data['expiry_date'] = f"20{expiry[0:2]}-{expiry[2:4]}-{expiry[4:6]}"
        except Exception as e:
            logger.error(f"Error parsing MRZ: {str(e)}")
        return data
    
    def parse_drivers_license(self, text):
        data = {}
        data['license_number'] = self.extract_pattern(text, r'[A-Z]{1,2}\d{6,8}')
        dates = re.findall(r'\d{2}/\d{2}/\d{4}', text)
        if len(dates) >= 2:
            data['issue_date'] = dates[0]
            data['expiry_date'] = dates[1]
        return data
    
    def parse_generic(self, text):
        return {
            'text': text,
            'document_number': self.extract_pattern(text, r'\d{6,10}')
        }
    
    def extract_pattern(self, text, pattern):
        match = re.search(pattern, text)
        return match.group(0) if match else None
    
    def detect_fraud(self, image):
        indicators = []
        img_array = np.array(image)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        if edge_density > 0.15:
            indicators.append('High edge density - possible image manipulation')
        
        regions = self.split_into_regions(gray, 3, 3)
        brightness_values = [np.mean(region) for region in regions]
        brightness_std = np.std(brightness_values)
        
        if brightness_std > 40:
            indicators.append('Inconsistent lighting across document')
        
        return {
            'indicators': indicators,
            'fraud_score': len(indicators) * 25
        }
    
    def split_into_regions(self, image, rows, cols):
        regions = []
        h, w = image.shape
        region_h = h // rows
        region_w = w // cols
        
        for i in range(rows):
            for j in range(cols):
                region = image[i*region_h:(i+1)*region_h, j*region_w:(j+1)*region_w]
                regions.append(region)
        
        return regions