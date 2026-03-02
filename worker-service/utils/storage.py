import boto3
from PIL import Image
from io import BytesIO
import os
import logging
import re

from botocore.config import Config
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

try:
    from pdf2image import convert_from_bytes
except Exception:
    convert_from_bytes = None

logger = logging.getLogger(__name__)

s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv('S3_ENDPOINT', 'http://localhost:9000'),
    aws_access_key_id=os.getenv('S3_ACCESS_KEY', 'minioadmin'),
    aws_secret_access_key=os.getenv('S3_SECRET_KEY', 'minioadmin'),
    config=Config(s3={'addressing_style': 'path'})
)

BUCKET_NAME = os.getenv('S3_BUCKET', 'kyc-documents')

def _get_encryption_key_bytes():
    raw = (os.getenv('ENCRYPTION_KEY') or '').strip().lower()
    if not raw:
        raise RuntimeError('ENCRYPTION_KEY is required to decrypt stored documents.')
    if not re.fullmatch(r'[0-9a-f]{64}', raw):
        raise RuntimeError('ENCRYPTION_KEY must be 64 hex characters (32 bytes).')
    return bytes.fromhex(raw)

def _decrypt_bytes(blob: bytes) -> bytes:
    # Matches Node: Buffer.concat([iv(16), authTag(16), encrypted])
    if blob is None or len(blob) < 33:
        raise ValueError('Encrypted blob is too small to be valid.')

    key = _get_encryption_key_bytes()
    iv = blob[0:16]
    tag = blob[16:32]
    ciphertext = blob[32:]

    decryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv, tag),
        backend=default_backend()
    ).decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()

def download_bytes(file_path: str) -> bytes:
    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_path)
    encrypted = response['Body'].read()
    return _decrypt_bytes(encrypted)

def download_file(file_path):
    try:
        data = download_bytes(file_path)

        # If it's a PDF, convert first page to image for downstream OCR/face ops.
        if data[:4] == b'%PDF':
            if convert_from_bytes is None:
                raise RuntimeError('PDF received but pdf2image is not installed in worker.')
            images = convert_from_bytes(data, first_page=1, last_page=1)
            if not images:
                raise RuntimeError('Failed to convert PDF to image.')
            return images[0]

        return Image.open(BytesIO(data))
    except Exception as e:
        logger.error(f"Error downloading file {file_path}: {str(e)}")
        raise

def upload_file(file_path, data, content_type='image/jpeg'):
    try:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=file_path,
            Body=data,
            ContentType=content_type
        )
        return file_path
    except Exception as e:
        logger.error(f"Error uploading file {file_path}: {str(e)}")
        raise