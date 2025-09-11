"""
Validation utility functions
"""
import re
from typing import Optional, List, Any
from fastapi import UploadFile, HTTPException, status


def validate_audio_file(
    file: UploadFile,
    max_size_mb: int = 500,
    allowed_types: Optional[List[str]] = None
) -> bool:
    """Validate audio file upload"""
    if allowed_types is None:
        allowed_types = [
            "audio/mpeg",
            "audio/mp3", 
            "audio/wav",
            "audio/x-wav",
            "audio/mp4",
            "audio/x-m4a",
            "audio/ogg",
            "audio/webm",
            "audio/flac"
        ]
    
    # Check file type
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )
    
    # Check file size
    if file.size and file.size > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds {max_size_mb}MB limit"
        )
    
    return True


def validate_phone_number(phone: str) -> bool:
    """Validate phone number format"""
    # Remove common separators
    cleaned = re.sub(r'[\s\-\.\(\)]', '', phone)
    
    # Check if it's a valid format
    # This is a simple check - in production would use phonenumbers library
    patterns = [
        r'^\+?1?\d{10}$',  # US/Canada
        r'^\+\d{1,3}\d{4,14}$',  # International
    ]
    
    for pattern in patterns:
        if re.match(pattern, cleaned):
            return True
    
    return False


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_uuid(uuid_string: str) -> bool:
    """Validate UUID format"""
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    return re.match(uuid_pattern, uuid_string.lower()) is not None


def validate_organization_name(name: str) -> bool:
    """Validate organization name"""
    # Check length
    if len(name) < 2 or len(name) > 255:
        return False
    
    # Check for valid characters
    # Allow letters, numbers, spaces, and common business punctuation
    pattern = r'^[a-zA-Z0-9\s\-\.\,\&\'\"]+$'
    return re.match(pattern, name) is not None


def validate_agent_code(code: str) -> bool:
    """Validate agent code format"""
    # Agent codes should be alphanumeric, 3-20 characters
    pattern = r'^[A-Z0-9]{3,20}$'
    return re.match(pattern, code) is not None


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove path separators and null bytes
    filename = filename.replace('/', '').replace('\\', '').replace('\x00', '')
    
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    
    # Remove non-ASCII characters
    filename = ''.join(c for c in filename if ord(c) < 128)
    
    # Limit length
    name_parts = filename.rsplit('.', 1)
    if len(name_parts) == 2:
        name, ext = name_parts
        if len(name) > 100:
            name = name[:100]
        filename = f"{name}.{ext}"
    elif len(filename) > 100:
        filename = filename[:100]
    
    return filename


def validate_date_range(
    from_date: Optional[str],
    to_date: Optional[str]
) -> bool:
    """Validate date range"""
    if not from_date or not to_date:
        return True
    
    try:
        from datetime import datetime
        from_dt = datetime.fromisoformat(from_date)
        to_dt = datetime.fromisoformat(to_date)
        
        # Check that from_date is before to_date
        return from_dt <= to_dt
    except ValueError:
        return False


def validate_pagination(
    page: int,
    limit: int,
    max_limit: int = 100
) -> tuple:
    """Validate and adjust pagination parameters"""
    # Ensure positive values
    page = max(1, page)
    limit = max(1, min(limit, max_limit))
    
    # Calculate offset
    offset = (page - 1) * limit
    
    return page, limit, offset


def validate_json_field(
    field_value: Any,
    field_name: str,
    required: bool = False,
    max_size_kb: int = 100
) -> bool:
    """Validate JSON field"""
    if not field_value and required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} is required"
        )
    
    if field_value:
        # Check size
        import json
        json_str = json.dumps(field_value)
        if len(json_str) > max_size_kb * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} exceeds {max_size_kb}KB limit"
            )
    
    return True
