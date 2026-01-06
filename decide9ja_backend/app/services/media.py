"""
Media Service for Decide9ja
Handles image uploads, S3 storage, and media processing
"""
import os
import io
import uuid
import hashlib
import logging
import mimetypes
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MediaType(str, Enum):
    """Supported media types."""
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"


class MediaStatus(str, Enum):
    """Media processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class MediaItem(BaseModel):
    """Media item metadata."""
    media_id: str
    original_filename: str
    storage_key: str
    media_type: MediaType
    mime_type: str
    size_bytes: int
    status: MediaStatus
    uploaded_by: str
    uploaded_at: datetime
    public_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    metadata: Dict[str, Any] = {}

    # For images
    width: Optional[int] = None
    height: Optional[int] = None

    # For community issues
    issue_id: Optional[str] = None

    # Content hash for deduplication
    content_hash: Optional[str] = None


class S3Config(BaseModel):
    """S3 configuration."""
    bucket_name: str
    region: str = "us-east-1"
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    endpoint_url: Optional[str] = None  # For S3-compatible services
    public_base_url: Optional[str] = None  # CDN or public bucket URL


class MediaService:
    """
    Service for managing media uploads and storage.
    Supports S3, local storage, and S3-compatible services.
    """

    # In-memory storage for development
    _media: Dict[str, MediaItem] = {}
    _local_storage: Dict[str, bytes] = {}

    # Configuration
    _config: Optional[S3Config] = None
    _s3_client = None

    # Allowed file types and size limits
    ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    ALLOWED_DOCUMENT_TYPES = ["application/pdf", "text/plain"]
    ALLOWED_AUDIO_TYPES = ["audio/mpeg", "audio/ogg", "audio/wav", "audio/mp4"]
    ALLOWED_VIDEO_TYPES = ["video/mp4", "video/webm"]

    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_DOCUMENT_SIZE = 25 * 1024 * 1024  # 25 MB
    MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50 MB
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB

    @classmethod
    def configure(cls, config: S3Config):
        """Configure S3 settings."""
        cls._config = config

        try:
            import boto3

            session_kwargs = {}
            if config.access_key and config.secret_key:
                session_kwargs["aws_access_key_id"] = config.access_key
                session_kwargs["aws_secret_access_key"] = config.secret_key

            client_kwargs = {"region_name": config.region}
            if config.endpoint_url:
                client_kwargs["endpoint_url"] = config.endpoint_url

            cls._s3_client = boto3.client("s3", **client_kwargs, **session_kwargs)
            logger.info(f"S3 configured: bucket={config.bucket_name}, region={config.region}")

        except ImportError:
            logger.warning("boto3 not installed - using local storage")
            cls._s3_client = None

    @classmethod
    def initialize_from_env(cls):
        """Initialize from environment variables."""
        bucket = os.getenv("AWS_S3_BUCKET", os.getenv("S3_BUCKET"))

        if bucket:
            config = S3Config(
                bucket_name=bucket,
                region=os.getenv("AWS_REGION", "us-east-1"),
                access_key=os.getenv("AWS_ACCESS_KEY_ID"),
                secret_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                endpoint_url=os.getenv("S3_ENDPOINT_URL"),
                public_base_url=os.getenv("S3_PUBLIC_URL")
            )
            cls.configure(config)
        else:
            logger.info("No S3 bucket configured - using local storage")

    @classmethod
    def _generate_storage_key(cls, filename: str, user_id: str) -> str:
        """Generate unique storage key for a file."""
        ext = os.path.splitext(filename)[1].lower()
        date_prefix = datetime.utcnow().strftime("%Y/%m/%d")
        unique_id = uuid.uuid4().hex[:12]

        return f"media/{date_prefix}/{user_id}/{unique_id}{ext}"

    @classmethod
    def _hash_content(cls, content: bytes) -> str:
        """Generate SHA-256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    @classmethod
    def _get_media_type(cls, mime_type: str) -> MediaType:
        """Determine media type from MIME type."""
        if mime_type in cls.ALLOWED_IMAGE_TYPES:
            return MediaType.IMAGE
        elif mime_type in cls.ALLOWED_DOCUMENT_TYPES:
            return MediaType.DOCUMENT
        elif mime_type in cls.ALLOWED_AUDIO_TYPES:
            return MediaType.AUDIO
        elif mime_type in cls.ALLOWED_VIDEO_TYPES:
            return MediaType.VIDEO
        else:
            raise ValueError(f"Unsupported media type: {mime_type}")

    @classmethod
    def _get_max_size(cls, media_type: MediaType) -> int:
        """Get maximum file size for media type."""
        return {
            MediaType.IMAGE: cls.MAX_IMAGE_SIZE,
            MediaType.DOCUMENT: cls.MAX_DOCUMENT_SIZE,
            MediaType.AUDIO: cls.MAX_AUDIO_SIZE,
            MediaType.VIDEO: cls.MAX_VIDEO_SIZE
        }.get(media_type, cls.MAX_IMAGE_SIZE)

    @classmethod
    def validate_upload(
        cls,
        filename: str,
        content_type: str,
        size: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate an upload before processing.
        Returns (is_valid, error_message).
        """
        # Check content type
        all_allowed = (
            cls.ALLOWED_IMAGE_TYPES +
            cls.ALLOWED_DOCUMENT_TYPES +
            cls.ALLOWED_AUDIO_TYPES +
            cls.ALLOWED_VIDEO_TYPES
        )

        if content_type not in all_allowed:
            return False, f"Unsupported file type: {content_type}"

        # Check size
        try:
            media_type = cls._get_media_type(content_type)
            max_size = cls._get_max_size(media_type)

            if size > max_size:
                max_mb = max_size / (1024 * 1024)
                return False, f"File too large. Maximum size: {max_mb:.0f} MB"

        except ValueError as e:
            return False, str(e)

        # Check filename
        if not filename or len(filename) > 255:
            return False, "Invalid filename"

        # Check for dangerous extensions
        dangerous_extensions = [".exe", ".bat", ".sh", ".php", ".js", ".html"]
        ext = os.path.splitext(filename)[1].lower()
        if ext in dangerous_extensions:
            return False, "File type not allowed for security reasons"

        return True, None

    @classmethod
    async def upload(
        cls,
        filename: str,
        content: bytes,
        content_type: str,
        user_id: str,
        issue_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MediaItem:
        """
        Upload a media file.
        Stores in S3 if configured, otherwise local storage.
        """
        # Validate
        is_valid, error = cls.validate_upload(filename, content_type, len(content))
        if not is_valid:
            raise ValueError(error)

        # Generate IDs and keys
        media_id = f"media_{uuid.uuid4().hex[:16]}"
        storage_key = cls._generate_storage_key(filename, user_id)
        content_hash = cls._hash_content(content)

        # Check for duplicate content
        existing = cls._find_by_hash(content_hash)
        if existing:
            logger.info(f"Found duplicate content: {existing.media_id}")
            # Return reference to existing media
            return existing

        # Get media type
        media_type = cls._get_media_type(content_type)

        # Extract image dimensions if applicable
        width, height = None, None
        if media_type == MediaType.IMAGE:
            width, height = cls._get_image_dimensions(content)

        # Create media item
        media_item = MediaItem(
            media_id=media_id,
            original_filename=filename,
            storage_key=storage_key,
            media_type=media_type,
            mime_type=content_type,
            size_bytes=len(content),
            status=MediaStatus.PROCESSING,
            uploaded_by=user_id,
            uploaded_at=datetime.utcnow(),
            width=width,
            height=height,
            issue_id=issue_id,
            content_hash=content_hash,
            metadata=metadata or {}
        )

        # Upload to storage
        try:
            if cls._s3_client and cls._config:
                # Upload to S3
                cls._s3_client.upload_fileobj(
                    io.BytesIO(content),
                    cls._config.bucket_name,
                    storage_key,
                    ExtraArgs={
                        "ContentType": content_type,
                        "Metadata": {
                            "original_filename": filename,
                            "uploaded_by": user_id
                        }
                    }
                )

                # Generate public URL
                if cls._config.public_base_url:
                    media_item.public_url = f"{cls._config.public_base_url}/{storage_key}"
                else:
                    # Generate presigned URL (valid for 7 days)
                    media_item.public_url = cls._s3_client.generate_presigned_url(
                        "get_object",
                        Params={
                            "Bucket": cls._config.bucket_name,
                            "Key": storage_key
                        },
                        ExpiresIn=7 * 24 * 60 * 60
                    )

                logger.info(f"Uploaded to S3: {storage_key}")

            else:
                # Store locally (development mode)
                cls._local_storage[storage_key] = content
                media_item.public_url = f"/media/{media_id}"
                logger.info(f"Stored locally: {storage_key}")

            media_item.status = MediaStatus.READY

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            media_item.status = MediaStatus.FAILED
            media_item.metadata["error"] = str(e)

        # Store metadata
        cls._media[media_id] = media_item

        return media_item

    @classmethod
    def _find_by_hash(cls, content_hash: str) -> Optional[MediaItem]:
        """Find existing media by content hash."""
        for media in cls._media.values():
            if media.content_hash == content_hash and media.status == MediaStatus.READY:
                return media
        return None

    @classmethod
    def _get_image_dimensions(cls, content: bytes) -> Tuple[Optional[int], Optional[int]]:
        """Extract image dimensions from content."""
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(content))
            return img.size
        except Exception:
            return None, None

    @classmethod
    def get(cls, media_id: str) -> Optional[MediaItem]:
        """Get media item by ID."""
        return cls._media.get(media_id)

    @classmethod
    def get_content(cls, media_id: str) -> Optional[bytes]:
        """Get media content."""
        media_item = cls._media.get(media_id)
        if not media_item:
            return None

        if cls._s3_client and cls._config:
            try:
                response = cls._s3_client.get_object(
                    Bucket=cls._config.bucket_name,
                    Key=media_item.storage_key
                )
                return response["Body"].read()
            except Exception as e:
                logger.error(f"Failed to get content from S3: {e}")
                return None
        else:
            return cls._local_storage.get(media_item.storage_key)

    @classmethod
    def delete(cls, media_id: str, user_id: str) -> bool:
        """
        Delete a media item.
        Only the uploader or admin can delete.
        """
        media_item = cls._media.get(media_id)
        if not media_item:
            return False

        # Check ownership (should also check for admin role in real implementation)
        if media_item.uploaded_by != user_id:
            logger.warning(f"Unauthorized delete attempt: {user_id} for {media_id}")
            return False

        try:
            if cls._s3_client and cls._config:
                cls._s3_client.delete_object(
                    Bucket=cls._config.bucket_name,
                    Key=media_item.storage_key
                )
            else:
                if media_item.storage_key in cls._local_storage:
                    del cls._local_storage[media_item.storage_key]

            media_item.status = MediaStatus.DELETED
            logger.info(f"Deleted media: {media_id}")
            return True

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    @classmethod
    def list_by_user(cls, user_id: str, limit: int = 50) -> List[MediaItem]:
        """List media items uploaded by a user."""
        user_media = [
            m for m in cls._media.values()
            if m.uploaded_by == user_id and m.status != MediaStatus.DELETED
        ]
        return sorted(user_media, key=lambda x: x.uploaded_at, reverse=True)[:limit]

    @classmethod
    def list_by_issue(cls, issue_id: str) -> List[MediaItem]:
        """List media items attached to an issue."""
        return [
            m for m in cls._media.values()
            if m.issue_id == issue_id and m.status != MediaStatus.DELETED
        ]

    @classmethod
    def get_presigned_upload_url(
        cls,
        filename: str,
        content_type: str,
        user_id: str
    ) -> Optional[Dict[str, str]]:
        """
        Generate presigned URL for direct client upload to S3.
        Returns upload URL and fields for form-based upload.
        """
        if not cls._s3_client or not cls._config:
            return None

        storage_key = cls._generate_storage_key(filename, user_id)

        try:
            response = cls._s3_client.generate_presigned_post(
                cls._config.bucket_name,
                storage_key,
                Fields={
                    "Content-Type": content_type
                },
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, cls.MAX_IMAGE_SIZE]
                ],
                ExpiresIn=3600  # 1 hour
            )

            return {
                "url": response["url"],
                "fields": response["fields"],
                "storage_key": storage_key
            }

        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None

    @classmethod
    async def process_whatsapp_media(
        cls,
        media_url: str,
        media_type: str,
        user_id: str
    ) -> Optional[MediaItem]:
        """
        Process media received from WhatsApp.
        Downloads from Twilio URL and stores.
        """
        import httpx

        try:
            # Download from WhatsApp/Twilio
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    media_url,
                    auth=(
                        os.getenv("TWILIO_ACCOUNT_SID", ""),
                        os.getenv("TWILIO_AUTH_TOKEN", "")
                    ),
                    timeout=30.0
                )

                if response.status_code != 200:
                    logger.error(f"Failed to download WhatsApp media: {response.status_code}")
                    return None

                content = response.content
                content_type = response.headers.get("Content-Type", media_type)

                # Generate filename from URL
                filename = f"whatsapp_{uuid.uuid4().hex[:8]}"
                ext = mimetypes.guess_extension(content_type) or ".bin"
                filename += ext

                # Upload
                return await cls.upload(
                    filename=filename,
                    content=content,
                    content_type=content_type,
                    user_id=user_id,
                    metadata={"source": "whatsapp", "original_url": media_url}
                )

        except Exception as e:
            logger.error(f"Failed to process WhatsApp media: {e}")
            return None

    @classmethod
    def generate_thumbnail(
        cls,
        media_id: str,
        width: int = 200,
        height: int = 200
    ) -> Optional[str]:
        """
        Generate thumbnail for an image.
        Returns URL of thumbnail.
        """
        media_item = cls._media.get(media_id)
        if not media_item or media_item.media_type != MediaType.IMAGE:
            return None

        try:
            from PIL import Image

            content = cls.get_content(media_id)
            if not content:
                return None

            # Create thumbnail
            img = Image.open(io.BytesIO(content))
            img.thumbnail((width, height), Image.Resampling.LANCZOS)

            # Save to bytes
            thumb_io = io.BytesIO()
            img.save(thumb_io, format=img.format or "JPEG")
            thumb_content = thumb_io.getvalue()

            # Store thumbnail
            thumb_key = f"thumbnails/{media_item.storage_key}"

            if cls._s3_client and cls._config:
                cls._s3_client.upload_fileobj(
                    io.BytesIO(thumb_content),
                    cls._config.bucket_name,
                    thumb_key,
                    ExtraArgs={"ContentType": media_item.mime_type}
                )

                if cls._config.public_base_url:
                    thumb_url = f"{cls._config.public_base_url}/{thumb_key}"
                else:
                    thumb_url = cls._s3_client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": cls._config.bucket_name, "Key": thumb_key},
                        ExpiresIn=7 * 24 * 60 * 60
                    )
            else:
                cls._local_storage[thumb_key] = thumb_content
                thumb_url = f"/media/thumb/{media_id}"

            media_item.thumbnail_url = thumb_url
            return thumb_url

        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}")
            return None

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Get media storage statistics."""
        total_items = len(cls._media)
        total_bytes = sum(m.size_bytes for m in cls._media.values())

        by_type = {}
        for media in cls._media.values():
            media_type = media.media_type.value
            if media_type not in by_type:
                by_type[media_type] = {"count": 0, "bytes": 0}
            by_type[media_type]["count"] += 1
            by_type[media_type]["bytes"] += media.size_bytes

        by_status = {}
        for media in cls._media.values():
            status = media.status.value
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total_items": total_items,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "by_type": by_type,
            "by_status": by_status,
            "storage_backend": "s3" if cls._s3_client else "local"
        }


# Initialize from environment on import
MediaService.initialize_from_env()
