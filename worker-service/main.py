import os
import json
import logging
from datetime import datetime
from redis import Redis
import psycopg2
from psycopg2.extras import RealDictCursor
from processors.document_processor import DocumentProcessor
from processors.face_matcher import FaceMatcher
from processors.sanctions_checker import SanctionsChecker
from dotenv import load_dotenv
import requests
import hmac
import hashlib

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

redis_conn = Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0
)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 5432)),
        database=os.getenv('DB_NAME', 'unhidentity_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres')
    )

document_processor = DocumentProcessor()
face_matcher = FaceMatcher()
sanctions_checker = SanctionsChecker()

def process_verification(job_data):
    verification_id = job_data['verification_id']
    logger.info(f"Processing verification: {verification_id}")
    
    try:
        results = {
            'verification_id': verification_id,
            'document_verified': False,
            'face_match_score': 0,
            'liveness_verified': False,
            'sanctions_check_passed': False,
            'risk_score': 0,
            'risk_level': 'high'
        }
        
        logger.info(f"Processing document for {verification_id}")
        doc_result = document_processor.process(
            job_data['document_front_path'],
            job_data.get('document_back_path'),
            job_data['document_type', 'passport']
        )
        results['document_verified'] = doc_result['is_valid']
        
        logger.info(f"Matching face for {verification_id}")
        face_result = face_matcher.match(
            job_data['selfie_path'],
            job_data['document_front_path']
        )
        results['face_match_score'] = face_result['match_score']
        results['liveness_verified'] = face_result['liveness_check']
        
        logger.info(f"Checking sanctions for {verification_id}")
        sanctions_result = sanctions_checker.check(
            job_data['first_name', ''],
            job_data['last_name', ''],
            job_data.get('date_of_birth')
        )
        results['sanctions_check_passed'] = not sanctions_result['is_match']
        
        risk_score = calculate_risk_score(results)
        results['risk_score'] = risk_score
        results['risk_level'] = get_risk_level(risk_score)
        
        update_verification_results(verification_id, results)

        # Trigger webhook after successful verification
        trigger_webhook(job_data['customer_id'], verification_id)
        
        logger.info(f"✅ Verification {verification_id} completed successfully")
        return results
        
    except Exception as e:
        logger.error(f"❌ Error processing verification {verification_id}: {str(e)}")
        mark_verification_failed(verification_id, str(e))
        raise

def calculate_risk_score(results):
    score = 0
    if not results['document_verified']:
        score += 40
    if results['face_match_score'] < 70:
        score += 30
    elif results['face_match_score'] < 85:
        score += 15
    if not results['liveness_verified']:
        score += 20
    if not results['sanctions_check_passed']:
        score += 100
    return min(score, 100)

def get_risk_level(risk_score):
    if risk_score >= 70:
        return 'high'
    elif risk_score >= 40:
        return 'medium'
    else:
        return 'low'

def update_verification_results(verification_id, results):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        status = 'completed' if results['risk_score'] < 70 else 'manual_review'
        
        cursor.execute("""
            UPDATE verifications 
            SET status = %s,
                document_verified = %s,
                face_match_score = %s,
                liveness_verified = %s,
                sanctions_check_passed = %s,
                risk_score = %s,
                risk_level = %s,
                completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            status,
            results['document_verified'],
            results['face_match_score'],
            results['liveness_verified'],
            results['sanctions_check_passed'],
            results['risk_score'],
            results['risk_level'],
            verification_id
        ))
        
        conn.commit()
        logger.info(f"Updated verification {verification_id} with status: {status}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update verification: {str(e)}")
        raise    
    finally:
        cursor.close()
        conn.close()

def mark_verification_failed(verification_id, error_message):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE verifications 
            SET status = 'failed',
                metadata = metadata || %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (json.dumps({'error': error_message}), verification_id))
        
        conn.commit()
    finally:
        cursor.close()
        conn.close()
def trigger_webhook(customer_id, verification_id):
    """Trigger webhook for verification completion"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get customer and verification data
        cursor.execute("""
            SELECT c.webhook_url, c.api_secret, v.*
            FROM customers c
            JOIN verifications v ON v.customer_id = c.id
            WHERE c.id = %s AND v.id = %s
        """, (customer_id, verification_id))
        
        row = cursor.fetchone()
        
        if not row or not row['webhook_url']:
            logger.info(f"No webhook URL for customer {customer_id}")
            cursor.close()
            conn.close()
            return
        
        webhook_url = row['webhook_url']
        api_secret = row['api_secret']
        
        # Prepare payload
        payload = {
            'event': 'verification.completed',
            'verification_id': str(verification_id),
            'external_id': row['external_id'],
            'status': row['status'],
            'risk_level': row['risk_level'],
            'risk_score': row['risk_score'],
            'results': {
                'document_verified': row['document_verified'],
                'face_match_score': float(row['face_match_score']) if row['face_match_score'] else 0,
                'liveness_verified': row['liveness_verified'],
                'sanctions_check_passed': row['sanctions_check_passed']
            },
            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
            'completed_at': row['completed_at'].isoformat() if row['completed_at'] else None,
            'timestamp': datetime.now().isoformat()
        }
        
        # Generate signature
        signature = generate_signature(payload, api_secret)
        
        # Store webhook delivery attempt
        cursor.execute("""
            INSERT INTO webhook_deliveries (verification_id, customer_id, url, payload, attempt_count)
            VALUES (%s, %s, %s, %s, 1)
            RETURNING id
        """, (verification_id, customer_id, webhook_url, json.dumps(payload)))
        
        delivery_id = cursor.fetchone()['id']
        conn.commit()
        
        # Send webhook
        response = requests.post(
            webhook_url,
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Webhook-Event': 'verification.completed',
                'X-Webhook-ID': str(delivery_id),
                'X-Webhook-Signature': signature,
                'X-Webhook-Timestamp': payload['timestamp'],
                'User-Agent': 'UnhIdentity-Webhook/1.0'
            },
            timeout=15
        )
        
        # Update delivery status
        cursor.execute("""
            UPDATE webhook_deliveries
            SET response_status = %s,
                response_body = %s,
                delivered_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (response.status_code, response.text[:2000], delivery_id))
        
        conn.commit()
        
        logger.info(f"✅ Webhook sent to {webhook_url}, status: {response.status_code}")
        
        cursor.close()
        conn.close()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Webhook delivery failed: {str(e)}")
        # Update with failure (retry will be handled by webhook service)
        try:
            cursor.execute("""
                UPDATE webhook_deliveries
                SET response_status = 0,
                    response_body = %s,
                    next_retry_at = CURRENT_TIMESTAMP + INTERVAL '5 minutes'
                WHERE id = %s
            """, (str(e)[:2000], delivery_id))
            conn.commit()
        except:
            pass
    except Exception as e:
        logger.error(f"❌ Webhook error: {str(e)}")

import os
import json
import logging
from datetime import datetime
from redis import Redis
from rq import Worker, Queue, Connection
import psycopg2
from psycopg2.extras import RealDictCursor
from processors.document_processor import DocumentProcessor
from processors.face_matcher import FaceMatcher
from processors.sanctions_checker import SanctionsChecker
from dotenv import load_dotenv
import requests
import hmac
import hashlib

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

redis_conn = Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0
)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 5432)),
        database=os.getenv('DB_NAME', 'unhidentity_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres')
    )

document_processor = DocumentProcessor()
face_matcher = FaceMatcher()
sanctions_checker = SanctionsChecker()

def process_verification(job_data):
    verification_id = job_data['verification_id']
    logger.info(f"Processing verification: {verification_id}")
    
    try:
        results = {
            'verification_id': verification_id,
            'document_verified': False,
            'face_match_score': 0,
            'liveness_verified': False,
            'sanctions_check_passed': False,
            'risk_score': 0,
            'risk_level': 'high'
        }
        
        logger.info(f"Processing document for {verification_id}")
        doc_result = document_processor.process(
            job_data['document_front_path'],
            job_data.get('document_back_path'),
            job_data.get('document_type', 'passport')
        )
        results['document_verified'] = doc_result['is_valid']
        
        logger.info(f"Matching face for {verification_id}")
        face_result = face_matcher.match(
            job_data['selfie_path'],
            job_data['document_front_path']
        )
        results['face_match_score'] = face_result['match_score']
        results['liveness_verified'] = face_result['liveness_check']
        
        logger.info(f"Checking sanctions for {verification_id}")
        sanctions_result = sanctions_checker.check(
            job_data.get('first_name', ''),
            job_data.get('last_name', ''),
            job_data.get('date_of_birth')
        )
        results['sanctions_check_passed'] = not sanctions_result['is_match']
        
        risk_score = calculate_risk_score(results)
        results['risk_score'] = risk_score
        results['risk_level'] = get_risk_level(risk_score)
        
        update_verification_results(verification_id, results)
        
        # Trigger webhook after successful verification
        trigger_webhook(job_data['customer_id'], verification_id)
        
        logger.info(f"✅ Verification {verification_id} completed successfully")
        return results
        
    except Exception as e:
        logger.error(f"❌ Error processing verification {verification_id}: {str(e)}")
        mark_verification_failed(verification_id, str(e))
        raise

def calculate_risk_score(results):
    score = 0
    if not results['document_verified']:
        score += 40
    if results['face_match_score'] < 70:
        score += 30
    elif results['face_match_score'] < 85:
        score += 15
    if not results['liveness_verified']:
        score += 20
    if not results['sanctions_check_passed']:
        score += 100
    return min(score, 100)

def get_risk_level(risk_score):
    if risk_score >= 70:
        return 'high'
    elif risk_score >= 40:
        return 'medium'
    else:
        return 'low'

def update_verification_results(verification_id, results):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        status = 'completed' if results['risk_score'] < 70 else 'manual_review'
        
        cursor.execute("""
            UPDATE verifications 
            SET status = %s,
                document_verified = %s,
                face_match_score = %s,
                liveness_verified = %s,
                sanctions_check_passed = %s,
                risk_score = %s,
                risk_level = %s,
                completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            status,
            results['document_verified'],
            results['face_match_score'],
            results['liveness_verified'],
            results['sanctions_check_passed'],
            results['risk_score'],
            results['risk_level'],
            verification_id
        ))
        
        conn.commit()
        logger.info(f"Updated verification {verification_id} with status: {status}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update verification: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()

def mark_verification_failed(verification_id, error_message):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE verifications 
            SET status = 'failed',
                metadata = metadata || %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (json.dumps({'error': error_message}), verification_id))
        
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def trigger_webhook(customer_id, verification_id):
    """Trigger webhook for verification completion"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get customer and verification data
        cursor.execute("""
            SELECT c.webhook_url, c.api_secret, v.*
            FROM customers c
            JOIN verifications v ON v.customer_id = c.id
            WHERE c.id = %s AND v.id = %s
        """, (customer_id, verification_id))
        
        row = cursor.fetchone()
        
        if not row or not row['webhook_url']:
            logger.info(f"No webhook URL for customer {customer_id}")
            cursor.close()
            conn.close()
            return
        
        webhook_url = row['webhook_url']
        api_secret = row['api_secret']
        
        # Prepare payload
        payload = {
            'event': 'verification.completed',
            'verification_id': str(verification_id),
            'external_id': row['external_id'],
            'status': row['status'],
            'risk_level': row['risk_level'],
            'risk_score': row['risk_score'],
            'results': {
                'document_verified': row['document_verified'],
                'face_match_score': float(row['face_match_score']) if row['face_match_score'] else 0,
                'liveness_verified': row['liveness_verified'],
                'sanctions_check_passed': row['sanctions_check_passed']
            },
            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
            'completed_at': row['completed_at'].isoformat() if row['completed_at'] else None,
            'timestamp': datetime.now().isoformat()
        }
        
        # Generate signature
        signature = generate_signature(payload, api_secret)
        
        # Store webhook delivery attempt
        cursor.execute("""
            INSERT INTO webhook_deliveries (verification_id, customer_id, url, payload, attempt_count)
            VALUES (%s, %s, %s, %s, 1)
            RETURNING id
        """, (verification_id, customer_id, webhook_url, json.dumps(payload)))
        
        delivery_id = cursor.fetchone()['id']
        conn.commit()
        
        # Send webhook
        response = requests.post(
            webhook_url,
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Webhook-Event': 'verification.completed',
                'X-Webhook-ID': str(delivery_id),
                'X-Webhook-Signature': signature,
                'X-Webhook-Timestamp': payload['timestamp'],
                'User-Agent': 'UnhIdentity-Webhook/1.0'
            },
            timeout=15
        )
        
        # Update delivery status
        cursor.execute("""
            UPDATE webhook_deliveries
            SET response_status = %s,
                response_body = %s,
                delivered_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (response.status_code, response.text[:2000], delivery_id))
        
        conn.commit()
        
        logger.info(f"✅ Webhook sent to {webhook_url}, status: {response.status_code}")
        
        cursor.close()
        conn.close()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Webhook delivery failed: {str(e)}")
        # Update with failure (retry will be handled by webhook service)
        try:
            cursor.execute("""
                UPDATE webhook_deliveries
                SET response_status = 0,
                    response_body = %s,
                    next_retry_at = CURRENT_TIMESTAMP + INTERVAL '5 minutes'
                WHERE id = %s
            """, (str(e)[:2000], delivery_id))
            conn.commit()
        except:
            pass
    except Exception as e:
        logger.error(f"❌ Webhook error: {str(e)}")

def generate_signature(payload, secret):
    """Generate HMAC signature for webhook verification"""
    message = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

if __name__ == '__main__':
    logger.info("🚀 Starting UnhIdentity Worker Service...")
    
    with Connection(redis_conn):
        worker = Worker(['verification-processing'])
        logger.info("✅ Worker ready, waiting for jobs...")
        worker.work()
        
def ensure_stream_group(conn, stream, group):
    try:
        conn.xgroup_create(stream, group, id='$', mkstream=True)
    except Exception as e:
        msg = str(e)
        if 'BUSYGROUP' not in msg:
            logger.error(f"Stream group error: {msg}")

def consume_stream(conn, stream, group, consumer):
    ensure_stream_group(conn, stream, group)
    while True:
        messages = conn.xreadgroup(group, consumer, {stream: '>'}, count=1, block=5000)
        if not messages:
            continue
        for _, entries in messages:
            for entry_id, fields in entries:
                try:
                    entry_type = fields.get(b'type') or fields.get('type')
                    data = fields.get(b'data') or fields.get('data')
                    if not data:
                        conn.xack(stream, group, entry_id)
                        continue
                    job_data = json.loads(data.decode() if isinstance(data, bytes) else data)
                    process_verification(job_data)
                except Exception as e:
                    logger.error(f"Processing error: {str(e)}")
                finally:
                    try:
                        conn.xack(stream, group, entry_id)
                    except Exception as ack_err:
                        logger.error(f"Ack error: {str(ack_err)}")

if __name__ == '__main__':
    logger.info("🚀 Starting UnhIdentity Worker Service...")
    consume_stream(redis_conn, 'verification-processing', 'verification_group', 'worker-1')
