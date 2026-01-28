import boto3
from PIL import Image
from io import BytesIO
import os
import logging

logger = logging.getLogger(__name__)

s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv('S3_ENDPOINT', 'http://localhost:9000'),
    aws_access_key_id=os.getenv('S3_ACCESS_KEY', 'minioadmin'),
    aws_secret_access_key=os.getenv('S3_SECRET_KEY', 'minioadmin')
)

BUCKET_NAME = os.getenv('S3_BUCKET', 'kyc-documents')

def download_file(file_path):
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_path)
        image_data = response['Body'].read()
        image = Image.open(BytesIO(image_data))
        return image
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