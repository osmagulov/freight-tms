import io
import logging
from functools import partial
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from src.core.config import settings

logger = logging.getLogger(__name__)


def _get_r2_client():
    """Create a synchronous boto3 S3 client configured for Cloudflare R2."""
    return boto3.client(
        service_name="s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",  # Required by SDK, ignored by R2
        config=Config(signature_version="s3v4"),
    )


def _upload_sync(file_bytes: bytes, key: str, content_type: str = "image/jpeg") -> str:
    """Synchronous upload — runs in thread executor to avoid blocking asyncio."""
    client = _get_r2_client()
    client.upload_fileobj(
        io.BytesIO(file_bytes),
        settings.R2_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return f"https://{settings.R2_BUCKET_NAME}.{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{key}"


async def upload_to_r2(file_bytes: bytes, key: str, content_type: str = "image/jpeg") -> Optional[str]:
    """Upload bytes to R2 with specified content type. Returns public URL or None if R2 not configured.

    Supports both images (image/jpeg, image/png) and documents (application/pdf).

    IMPORTANT: boto3 is synchronous. This function uses run_in_executor to avoid
    blocking the asyncio event loop during upload.
    """
    if not settings.R2_ACCOUNT_ID or not settings.R2_ACCESS_KEY_ID or not settings.R2_SECRET_ACCESS_KEY:
        logger.warning("R2 credentials not configured — skipping upload, storing None.")
        return None

    import asyncio
    loop = asyncio.get_event_loop()
    try:
        url = await loop.run_in_executor(None, partial(_upload_sync, file_bytes, key, content_type))
        logger.info(f"File uploaded to R2: {url}")
        return url
    except (BotoCoreError, ClientError) as e:
        logger.error(f"R2 upload failed for key {key}: {e}")
        return None


async def upload_photo_to_r2(file_bytes: bytes, key: str) -> Optional[str]:
    """Upload photo bytes to R2. Returns public URL or None if R2 not configured.

    Backward-compatible alias for upload_to_r2 with default image/jpeg content type.

    IMPORTANT: boto3 is synchronous. This function uses run_in_executor to avoid
    blocking the asyncio event loop during upload.
    """
    return await upload_to_r2(file_bytes, key, content_type="image/jpeg")


# --- Local fallback storage ---
PHOTO_DIR = Path("/data/photos")
PHOTO_DIR.mkdir(parents=True, exist_ok=True)


def _save_local(file_bytes: bytes, key: str) -> str:
    """Save file to local filesystem, return URL path."""
    file_path = PHOTO_DIR / key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(file_bytes)
    logger.info(f"File saved locally: {file_path}")
    return f"/app/photos/{key}"


async def save_uploaded_file(file_bytes: bytes, key: str, content_type: str = "image/jpeg") -> Optional[str]:
    """Upload file to R2 or save locally as fallback. Always returns a URL."""
    url = await upload_to_r2(file_bytes, key, content_type)
    if url:
        return url
    # Fallback to local storage
    return _save_local(file_bytes, key)

