"""
Media Upload & Management Router
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth.api_keys import APIKey, require_api_key, get_api_key
from app.auth.rbac import Permission, check_permission
from app.services.media import MediaService, MediaItem, MediaType, MediaStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/media", tags=["media"])


# =====================
# Pydantic Models
# =====================

class MediaUploadResponse(BaseModel):
    """Response after successful upload."""
    success: bool
    media_id: str
    public_url: Optional[str]
    thumbnail_url: Optional[str]
    media_type: str
    size_bytes: int
    message: str


class MediaListResponse(BaseModel):
    """Response for listing media."""
    total: int
    items: List[dict]


class PresignedUrlResponse(BaseModel):
    """Response with presigned upload URL."""
    success: bool
    upload_url: str
    fields: dict
    storage_key: str
    expires_in: int


# =====================
# Upload Endpoints
# =====================

@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(
    file: UploadFile = File(...),
    issue_id: Optional[str] = Query(None, description="Attach to community issue"),
    api_key: APIKey = Depends(require_api_key)
):
    """
    Upload a media file (image, document, audio, or video).

    Supported formats:
    - Images: JPEG, PNG, GIF, WebP (max 10 MB)
    - Documents: PDF, TXT (max 25 MB)
    - Audio: MP3, OGG, WAV, M4A (max 50 MB)
    - Video: MP4, WebM (max 100 MB)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Read content
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # Validate before upload
    is_valid, error = MediaService.validate_upload(
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        size=len(content)
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    try:
        media_item = await MediaService.upload(
            filename=file.filename,
            content=content,
            content_type=file.content_type or "application/octet-stream",
            user_id=api_key.key_id,
            issue_id=issue_id
        )

        # Generate thumbnail for images
        if media_item.media_type == MediaType.IMAGE:
            MediaService.generate_thumbnail(media_item.media_id)

        return MediaUploadResponse(
            success=True,
            media_id=media_item.media_id,
            public_url=media_item.public_url,
            thumbnail_url=media_item.thumbnail_url,
            media_type=media_item.media_type.value,
            size_bytes=media_item.size_bytes,
            message="File uploaded successfully"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")


@router.post("/upload/presigned", response_model=PresignedUrlResponse)
async def get_presigned_upload_url(
    filename: str = Query(..., description="Filename to upload"),
    content_type: str = Query(..., description="MIME type of file"),
    api_key: APIKey = Depends(require_api_key)
):
    """
    Get a presigned URL for direct upload to S3.

    Use this for large files to upload directly from client
    without going through the API server.
    """
    # Validate content type
    is_valid, error = MediaService.validate_upload(
        filename=filename,
        content_type=content_type,
        size=1  # Size validated during actual upload
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    result = MediaService.get_presigned_upload_url(
        filename=filename,
        content_type=content_type,
        user_id=api_key.key_id
    )

    if not result:
        raise HTTPException(
            status_code=503,
            detail="Presigned URLs not available. Use direct upload instead."
        )

    return PresignedUrlResponse(
        success=True,
        upload_url=result["url"],
        fields=result["fields"],
        storage_key=result["storage_key"],
        expires_in=3600
    )


# =====================
# Read Endpoints
# =====================

@router.get("/{media_id}")
async def get_media_info(
    media_id: str,
    api_key: Optional[APIKey] = Depends(get_api_key)
):
    """Get media item metadata."""
    media_item = MediaService.get(media_id)

    if not media_item:
        raise HTTPException(status_code=404, detail="Media not found")

    if media_item.status == MediaStatus.DELETED:
        raise HTTPException(status_code=404, detail="Media has been deleted")

    return {
        "media_id": media_item.media_id,
        "filename": media_item.original_filename,
        "media_type": media_item.media_type.value,
        "mime_type": media_item.mime_type,
        "size_bytes": media_item.size_bytes,
        "status": media_item.status.value,
        "public_url": media_item.public_url,
        "thumbnail_url": media_item.thumbnail_url,
        "uploaded_at": media_item.uploaded_at.isoformat(),
        "width": media_item.width,
        "height": media_item.height,
        "issue_id": media_item.issue_id
    }


@router.get("/{media_id}/download")
async def download_media(
    media_id: str,
    api_key: Optional[APIKey] = Depends(get_api_key)
):
    """Download media file content."""
    media_item = MediaService.get(media_id)

    if not media_item:
        raise HTTPException(status_code=404, detail="Media not found")

    if media_item.status != MediaStatus.READY:
        raise HTTPException(status_code=404, detail="Media not available")

    content = MediaService.get_content(media_id)

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    return StreamingResponse(
        iter([content]),
        media_type=media_item.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{media_item.original_filename}"'
        }
    )


@router.get("/user/me", response_model=MediaListResponse)
async def list_my_media(
    limit: int = Query(50, ge=1, le=100),
    api_key: APIKey = Depends(require_api_key)
):
    """List media uploaded by current user."""
    items = MediaService.list_by_user(api_key.key_id, limit=limit)

    return MediaListResponse(
        total=len(items),
        items=[
            {
                "media_id": m.media_id,
                "filename": m.original_filename,
                "media_type": m.media_type.value,
                "size_bytes": m.size_bytes,
                "public_url": m.public_url,
                "thumbnail_url": m.thumbnail_url,
                "uploaded_at": m.uploaded_at.isoformat()
            }
            for m in items
        ]
    )


@router.get("/issue/{issue_id}", response_model=MediaListResponse)
async def list_issue_media(
    issue_id: str,
    api_key: Optional[APIKey] = Depends(get_api_key)
):
    """List media attached to a community issue."""
    items = MediaService.list_by_issue(issue_id)

    return MediaListResponse(
        total=len(items),
        items=[
            {
                "media_id": m.media_id,
                "filename": m.original_filename,
                "media_type": m.media_type.value,
                "public_url": m.public_url,
                "thumbnail_url": m.thumbnail_url,
                "uploaded_at": m.uploaded_at.isoformat()
            }
            for m in items
        ]
    )


# =====================
# Delete Endpoint
# =====================

@router.delete("/{media_id}")
async def delete_media(
    media_id: str,
    api_key: APIKey = Depends(require_api_key)
):
    """
    Delete a media item.
    Users can only delete their own uploads.
    Admins can delete any media.
    """
    media_item = MediaService.get(media_id)

    if not media_item:
        raise HTTPException(status_code=404, detail="Media not found")

    # Check ownership or admin permission
    is_owner = media_item.uploaded_by == api_key.key_id
    is_admin = check_permission(api_key.role, Permission.ISSUE_DELETE)

    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own uploads"
        )

    # Admin bypass for deletion
    if is_admin and not is_owner:
        MediaService._media[media_id].status = MediaStatus.DELETED
        success = True
    else:
        success = MediaService.delete(media_id, api_key.key_id)

    if not success:
        raise HTTPException(status_code=500, detail="Delete failed")

    return {
        "success": True,
        "message": f"Media {media_id} deleted"
    }


# =====================
# Admin Endpoints
# =====================

@router.get("/admin/stats")
async def get_media_stats(
    api_key: APIKey = Depends(require_api_key)
):
    """Get media storage statistics. Requires admin role."""
    if not check_permission(api_key.role, Permission.ANALYTICS_READ):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )

    return MediaService.get_stats()


@router.get("/admin/list")
async def admin_list_media(
    media_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    api_key: APIKey = Depends(require_api_key)
):
    """List all media. Requires admin role."""
    if not check_permission(api_key.role, Permission.ANALYTICS_READ):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )

    all_media = list(MediaService._media.values())

    # Filter by type
    if media_type:
        try:
            type_enum = MediaType(media_type)
            all_media = [m for m in all_media if m.media_type == type_enum]
        except ValueError:
            pass

    # Filter by status
    if status:
        try:
            status_enum = MediaStatus(status)
            all_media = [m for m in all_media if m.status == status_enum]
        except ValueError:
            pass

    # Sort by upload date
    all_media.sort(key=lambda x: x.uploaded_at, reverse=True)

    # Paginate
    paginated = all_media[offset:offset + limit]

    return {
        "total": len(all_media),
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "media_id": m.media_id,
                "filename": m.original_filename,
                "media_type": m.media_type.value,
                "size_bytes": m.size_bytes,
                "status": m.status.value,
                "uploaded_by": m.uploaded_by,
                "uploaded_at": m.uploaded_at.isoformat(),
                "public_url": m.public_url
            }
            for m in paginated
        ]
    }
