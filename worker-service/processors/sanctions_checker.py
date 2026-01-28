import psycopg2
from psycopg2.extras import RealDictCursor
import os
import logging
from fuzzywuzzy import fuzz

logger = logging.getLogger(__name__)

class SanctionsChecker:
    def __init__(self):
        self.db_conn = self.get_db_connection()
        self.match_threshold = 85
    
    def get_db_connection(self):
        return psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 5432)),
            database=os.getenv('DB_NAME', 'unhidentity_db'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
    
    def check(self, first_name, last_name, date_of_birth=None):
        result = {
            'is_match': False,
            'matches': [],
            'lists_checked': ['OFAC', 'UN', 'EU']
        }
        
        try:
            full_name = f"{first_name} {last_name}".strip()
            
            if not full_name:
                return result
            
            cursor = self.db_conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM sanctions_entries 
                WHERE LOWER(name) = LOWER(%s)
                OR %s = ANY(aliases)
            """, (full_name, full_name))
            
            exact_matches = cursor.fetchall()
            
            if exact_matches:
                result['is_match'] = True
                result['matches'] = [dict(match) for match in exact_matches]
                cursor.close()
                return result
            
            cursor.execute("""
                SELECT * FROM sanctions_entries 
                WHERE search_vector @@ plainto_tsquery('english', %s)
                LIMIT 100
            """, (full_name,))
            
            potential_matches = cursor.fetchall()
            
            for match in potential_matches:
                score = fuzz.ratio(full_name.lower(), match['name'].lower())
                
                if match['aliases']:
                    for alias in match['aliases']:
                        alias_score = fuzz.ratio(full_name.lower(), alias.lower())
                        score = max(score, alias_score)
                
                if date_of_birth and match['date_of_birth']:
                    if str(date_of_birth) == str(match['date_of_birth']):
                        score += 10
                
                if score >= self.match_threshold:
                    match_dict = dict(match)
                    match_dict['match_score'] = score
                    result['matches'].append(match_dict)
                    result['is_match'] = True
            
            cursor.close()
            return result
            
        except Exception as e:
            logger.error(f"Error checking sanctions: {str(e)}")
            return result