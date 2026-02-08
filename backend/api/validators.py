"""
Input validation utilities for API endpoints.
"""
import os

from fastapi import HTTPException

from config.settings import settings

# Magic bytes for supported image formats
IMAGE_MAGIC_BYTES = {
    b'\x89PNG': 'png',
    b'\xff\xd8\xff': 'jpeg',
    b'BM': 'bmp',
    b'GIF8': 'gif',
    b'RIFF': 'webp',  # WebP starts with RIFF....WEBP
}


def validate_image_upload(filename: str, file_bytes: bytes) -> None:
    """
    Validate an uploaded image file.

    Checks:
    1. File is not empty
    2. File extension is allowed
    3. File size is within limits
    4. Magic bytes match a supported image format

    Args:
        filename: Original filename from the upload
        file_bytes: Raw file content

    Raises:
        HTTPException: 400 for invalid files, 413 for oversized files
    """
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    ext = os.path.splitext(filename or '')[1].lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(settings.allowed_extensions)}"
        )

    if len(file_bytes) > settings.max_upload_size:
        max_mb = settings.max_upload_size / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {max_mb:.0f}MB"
        )

    if not _has_valid_magic_bytes(file_bytes):
        raise HTTPException(
            status_code=400,
            detail="File content does not match a supported image format"
        )


def _has_valid_magic_bytes(file_bytes: bytes) -> bool:
    """Check if file content starts with valid image magic bytes."""
    for magic, format_name in IMAGE_MAGIC_BYTES.items():
        if file_bytes[:len(magic)] == magic:
            # Special check for WebP: must have 'WEBP' at bytes 8-11
            if format_name == 'webp':
                if len(file_bytes) < 12:
                    return False
                # WebP format: RIFF + size (4 bytes) + WEBP
                if file_bytes[8:12] != b'WEBP':
                    return False
            return True
    return False
