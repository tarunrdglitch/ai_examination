import os
import glob
import logging

logger = logging.getLogger(__name__)

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
S3_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class CloudStorageManager:
    """Enterprise Cloud Storage Manager supporting AWS S3, MinIO, Wasabi, and Local Storage.
    Ensures safe persistence during exams, and cascade deletion when exams are erased.
    """

    def __init__(self):
        self.enabled = STORAGE_BACKEND in ("s3", "minio") and bool(S3_BUCKET_NAME) and BOTO3_AVAILABLE
        self.client = None
        if self.enabled:
            try:
                session = boto3.session.Session()
                kwargs = {
                    "aws_access_key_id": AWS_ACCESS_KEY,
                    "aws_secret_access_key": AWS_SECRET_KEY,
                    "region_name": S3_REGION
                }
                if S3_ENDPOINT_URL:
                    kwargs["endpoint_url"] = S3_ENDPOINT_URL
                self.client = session.client("s3", **kwargs)
                logger.info(f"CloudStorageManager initialized with bucket: {S3_BUCKET_NAME} on endpoint: {S3_ENDPOINT_URL or 'AWS Default'}")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                self.enabled = False

    def upload_file(self, local_path: str, remote_key: str) -> bool:
        """Uploads a local recording or evidence file to Cloud Storage."""
        if not self.enabled or not os.path.exists(local_path):
            return False
        try:
            self.client.upload_file(local_path, S3_BUCKET_NAME, remote_key)
            logger.info(f"Uploaded {local_path} -> s3://{S3_BUCKET_NAME}/{remote_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to S3: {e}")
            return False

    def sync_exam_folder(self, exam_id: int, base_dir: str = "exam_recordings") -> int:
        """Syncs all student recordings and chunks for an exam to the cloud storage."""
        if not self.enabled:
            return 0
        uploaded_count = 0
        exam_pattern = os.path.join(base_dir, f"{exam_id}_*.*")
        for file_path in glob.glob(exam_pattern):
            fname = os.path.basename(file_path)
            remote_key = f"exams/{exam_id}/recordings/{fname}"
            if self.upload_file(file_path, remote_key):
                uploaded_count += 1
        return uploaded_count

    def delete_exam_data(self, exam_id: int) -> int:
        """Permanently purges all cloud-stored recordings and artifacts for an exam.
        Called on exam deletion to satisfy strict erasure guarantees.
        """
        if not self.enabled:
            return 0
        deleted_count = 0
        try:
            prefix = f"exams/{exam_id}/"
            paginator = self.client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=prefix):
                contents = page.get('Contents', [])
                if not contents:
                    continue
                delete_keys = [{'Key': obj['Key']} for obj in contents]
                self.client.delete_objects(
                    Bucket=S3_BUCKET_NAME,
                    Delete={'Objects': delete_keys}
                )
                deleted_count += len(delete_keys)
            logger.info(f"Cloud Storage: purged {deleted_count} objects for exam {exam_id}")
        except Exception as e:
            logger.error(f"Error purging cloud objects for exam {exam_id}: {e}")
        return deleted_count


# Global singleton instance
cloud_storage = CloudStorageManager()
