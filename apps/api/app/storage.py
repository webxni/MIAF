from minio import Minio

from app.config import get_settings


def make_minio() -> Minio:
    s = get_settings()
    return Minio(
        endpoint=s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key,
        secure=s.minio_secure,
    )


def ensure_bucket(client: Minio, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


minio_client: Minio = make_minio()
