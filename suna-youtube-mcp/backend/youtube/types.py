"""
Shared Type Definitions for YouTube MCP
Pydantic models and type definitions used across the YouTube integration
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


# Enums
class PrivacyStatus(str, Enum):
    """YouTube video privacy status"""
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"


class UploadStatus(str, Enum):
    """Upload status tracking"""
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SCHEDULED = "scheduled"


class FileType(str, Enum):
    """File type for uploads"""
    VIDEO = "video"
    THUMBNAIL = "thumbnail"


# YouTube Data Models
class YouTubeChannel(BaseModel):
    """YouTube channel information"""
    id: str
    name: str
    custom_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    subscriber_count: int = 0
    view_count: int = 0
    video_count: int = 0
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class YouTubeVideoMetadata(BaseModel):
    """Video metadata for uploads"""
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: List[str] = Field(default_factory=list, max_items=500)
    category_id: str = Field(default="22")  # People & Blogs
    privacy_status: PrivacyStatus = Field(default=PrivacyStatus.PRIVATE)
    made_for_kids: bool = Field(default=False)
    notify_subscribers: bool = Field(default=True)
    publish_at: Optional[datetime] = None
    
    @validator('tags')
    def validate_tags(cls, v):
        # YouTube tag requirements
        total_chars = sum(len(tag) for tag in v)
        if total_chars > 500:
            raise ValueError("Total character count of all tags cannot exceed 500")
        return v
    
    @validator('category_id')
    def validate_category(cls, v):
        # Valid YouTube categories (subset)
        valid_categories = [
            "1",   # Film & Animation
            "2",   # Cars & Vehicles
            "10",  # Music
            "15",  # Pets & Animals
            "17",  # Sports
            "19",  # Travel & Events
            "20",  # Gaming
            "22",  # People & Blogs
            "23",  # Comedy
            "24",  # Entertainment
            "25",  # News & Politics
            "26",  # How-to & Style
            "27",  # Education
            "28",  # Science & Technology
        ]
        if v not in valid_categories:
            return "22"  # Default to People & Blogs
        return v


class YouTubeVideo(BaseModel):
    """YouTube video information"""
    id: str
    channel_id: str
    title: str
    description: str
    thumbnail_url: Optional[str] = None
    published_at: datetime
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    duration: Optional[str] = None  # ISO 8601 duration
    privacy_status: PrivacyStatus
    tags: List[str] = Field(default_factory=list)


# Upload Models
class VideoFileReference(BaseModel):
    """Video file reference for temporary storage"""
    id: str = Field(..., regex="^[a-f0-9]{32}$")  # 32-char hex
    user_id: str
    file_name: str
    file_path: Optional[str] = None
    file_size: int = Field(..., gt=0)
    mime_type: str
    checksum: Optional[str] = None
    uploaded_at: datetime
    expires_at: datetime
    transcription: Optional[Dict[str, Any]] = None
    generated_metadata: Optional[List[Dict[str, Any]]] = None
    is_temporary: bool = True
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class UploadReference(BaseModel):
    """Upload reference for AI tools"""
    id: str
    user_id: str
    reference_id: str
    file_name: str
    file_size: str  # Human-readable size
    file_type: FileType
    mime_type: str
    status: Literal["pending", "used", "expired"] = "pending"
    created_at: datetime
    used_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class YouTubeUpload(BaseModel):
    """YouTube upload tracking"""
    id: str
    user_id: str
    channel_id: str
    video_id: Optional[str] = None
    title: str
    description: str
    tags: List[str] = Field(default_factory=list)
    category_id: str = "22"
    privacy_status: PrivacyStatus
    made_for_kids: bool = False
    file_name: str
    file_size: int
    mime_type: str
    upload_status: UploadStatus
    upload_progress: float = Field(default=0, ge=0, le=100)
    status_message: Optional[str] = None
    error_message: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    video_reference_id: Optional[str] = None
    thumbnail_reference_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Analytics Models
class VideoAnalytics(BaseModel):
    """Video analytics data"""
    video_id: str
    channel_id: str
    period_start: datetime
    period_end: datetime
    views: int = 0
    watch_time_minutes: float = 0
    average_view_duration_seconds: float = 0
    likes: int = 0
    dislikes: int = 0
    comments: int = 0
    shares: int = 0
    subscribers_gained: int = 0
    subscribers_lost: int = 0
    estimated_revenue: Optional[float] = None
    impressions: int = 0
    click_through_rate: float = 0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ChannelAnalytics(BaseModel):
    """Channel analytics data"""
    channel_id: str
    period_start: datetime
    period_end: datetime
    total_views: int = 0
    total_watch_time_minutes: float = 0
    total_subscribers: int = 0
    subscribers_gained: int = 0
    subscribers_lost: int = 0
    estimated_revenue: Optional[float] = None
    videos_published: int = 0
    average_view_duration_seconds: float = 0
    top_videos: List[Dict[str, Any]] = Field(default_factory=list)
    demographics: Optional[Dict[str, Any]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Transcription Models
class TranscriptionSegment(BaseModel):
    """Transcription segment with timing"""
    text: str
    start: float
    end: float
    confidence: Optional[float] = None


class VideoTranscription(BaseModel):
    """Video transcription data"""
    text: str
    language: str
    duration: float
    segments: List[TranscriptionSegment] = Field(default_factory=list)
    processed_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class GeneratedMetadata(BaseModel):
    """AI-generated video metadata"""
    title: str
    description: str
    tags: List[str]
    category: Optional[str] = None
    thumbnail_suggestions: Optional[List[str]] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# Request/Response Models
class UploadRequest(BaseModel):
    """Video upload request"""
    channel_id: str
    reference_id: str
    metadata: YouTubeVideoMetadata
    thumbnail_reference_id: Optional[str] = None
    scheduled_for: Optional[str] = None  # Natural language date


class UploadResponse(BaseModel):
    """Video upload response"""
    upload_id: str
    video_id: Optional[str] = None
    status: UploadStatus
    message: str
    channel_id: str
    channel_name: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ChannelListResponse(BaseModel):
    """Channel list response"""
    channels: List[YouTubeChannel]
    count: int
    message: Optional[str] = None


class UploadProgressResponse(BaseModel):
    """Upload progress response"""
    upload_id: str
    status: UploadStatus
    progress: float
    bytes_uploaded: int
    total_bytes: int
    formatted_uploaded: str
    formatted_total: str
    elapsed_seconds: Optional[float] = None
    upload_speed_bps: Optional[float] = None
    estimated_time_remaining: Optional[float] = None
    video_id: Optional[str] = None
    error: Optional[str] = None


# OAuth Models
class OAuthToken(BaseModel):
    """OAuth token information"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expiry: datetime
    scopes: List[str] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    def is_expired(self, buffer_minutes: int = 5) -> bool:
        """Check if token is expired or about to expire"""
        from datetime import timedelta
        buffer = timedelta(minutes=buffer_minutes)
        return datetime.utcnow() + buffer >= self.expiry


class OAuthConfig(BaseModel):
    """OAuth configuration"""
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: List[str]
    auth_url: str = "https://accounts.google.com/o/oauth2/auth"
    token_url: str = "https://oauth2.googleapis.com/token"


# Error Models
class YouTubeError(BaseModel):
    """YouTube API error"""
    code: int
    message: str
    status: str
    details: Optional[List[Dict[str, Any]]] = None


class UploadError(BaseModel):
    """Upload error details"""
    upload_id: str
    error_type: str
    error_message: str
    timestamp: datetime
    retry_count: int = 0
    can_retry: bool = True
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Utility Functions
def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def parse_iso_duration(duration: str) -> float:
    """Parse ISO 8601 duration to seconds"""
    # Simple parser for YouTube durations like "PT4M33S"
    import re
    
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration)
    
    if not match:
        return 0.0
    
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    
    return hours * 3600 + minutes * 60 + seconds