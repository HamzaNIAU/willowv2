"""
Dramatiq Background Tasks for YouTube Upload Processing
Following Suna's tech stack with Dramatiq for async job processing
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

import dramatiq
from dramatiq import actor
from dramatiq.brokers.redis import RedisBroker
from dramatiq.rate_limits import ConcurrentRateLimiter
from dramatiq.rate_limits.backends import RedisBackend

from .client import YouTubeClient
from .channels import YouTubeMCPChannels
from .file_manager import VideoFileManager
from .upload_stream import ResumableUploadStream
from .types import UploadStatus, YouTubeVideoMetadata

logger = logging.getLogger(__name__)

# Configure Redis broker for Dramatiq
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_broker = RedisBroker(url=redis_url)
dramatiq.set_broker(redis_broker)

# Rate limiter for YouTube API (prevent quota exhaustion)
youtube_rate_limiter = ConcurrentRateLimiter(
    backend=RedisBackend(url=redis_url),
    key="youtube-upload-limiter",
    limit=5,  # Max 5 concurrent uploads
    ttl=60000  # 60 seconds
)


@actor(
    max_retries=3,
    min_backoff=60000,  # 1 minute
    max_backoff=3600000,  # 1 hour
    time_limit=7200000,  # 2 hours max
    rate_limiter=youtube_rate_limiter
)
def process_video_upload(
    upload_id: str,
    user_id: str,
    channel_id: str,
    reference_id: str,
    metadata: Dict[str, Any],
    thumbnail_reference_id: Optional[str] = None
):
    """
    Background task to process video upload to YouTube
    
    This task:
    1. Retrieves the video file from temporary storage
    2. Initiates resumable upload to YouTube
    3. Tracks progress and updates database
    4. Handles retries on failure
    5. Cleans up temporary files on completion
    """
    logger.info(f"[Upload Task] Starting upload {upload_id} for user {user_id}")
    
    try:
        # Run async code in sync context
        asyncio.run(_process_upload_async(
            upload_id=upload_id,
            user_id=user_id,
            channel_id=channel_id,
            reference_id=reference_id,
            metadata=metadata,
            thumbnail_reference_id=thumbnail_reference_id
        ))
    except Exception as e:
        logger.error(f"[Upload Task] Failed for {upload_id}: {e}")
        # Update upload status to failed
        asyncio.run(_update_upload_status(
            upload_id=upload_id,
            status=UploadStatus.FAILED,
            error_message=str(e)
        ))
        raise  # Re-raise for Dramatiq retry


async def _process_upload_async(
    upload_id: str,
    user_id: str,
    channel_id: str,
    reference_id: str,
    metadata: Dict[str, Any],
    thumbnail_reference_id: Optional[str] = None
):
    """Async implementation of upload processing"""
    
    from supabase import create_client
    supabase = create_client(
        os.getenv("SUPABASE_URL", ""),
        os.getenv("SUPABASE_ANON_KEY", "")
    )
    
    # Initialize managers
    file_manager = VideoFileManager()
    channels_manager = YouTubeMCPChannels(supabase)
    
    try:
        # Get channel and token
        channel = await channels_manager.get_channel(channel_id)
        if not channel or not channel.get("access_token"):
            raise ValueError(f"Channel {channel_id} not found or not authenticated")
        
        # Initialize YouTube client
        youtube_client = YouTubeClient(channel["access_token"])
        
        # Get video file reference
        video_ref = await file_manager.get_reference(reference_id)
        if not video_ref:
            raise ValueError(f"Video reference {reference_id} not found")
        
        # Update status to uploading
        await _update_upload_status(
            upload_id=upload_id,
            status=UploadStatus.UPLOADING,
            progress=0
        )
        
        # Create metadata object
        video_metadata = YouTubeVideoMetadata(**metadata)
        
        # Initiate resumable upload
        logger.info(f"[Upload Task] Initiating resumable upload for {video_ref['file_name']}")
        upload_url = await youtube_client.initiate_resumable_upload(
            metadata=video_metadata,
            file_size=video_ref["file_size"],
            mime_type=video_ref["mime_type"]
        )
        
        # Create upload stream
        upload_stream = ResumableUploadStream(
            upload_url=upload_url,
            file_path=video_ref["file_path"],
            file_size=video_ref["file_size"],
            chunk_size=256 * 1024 * 1024  # 256MB chunks
        )
        
        # Progress callback
        async def on_progress(bytes_uploaded: int, total_bytes: int):
            progress = int((bytes_uploaded / total_bytes) * 100)
            await _update_upload_status(
                upload_id=upload_id,
                status=UploadStatus.UPLOADING,
                progress=progress,
                bytes_uploaded=bytes_uploaded,
                total_bytes=total_bytes
            )
        
        # Upload with progress tracking
        video_id = await upload_stream.upload(progress_callback=on_progress)
        
        logger.info(f"[Upload Task] Upload complete! Video ID: {video_id}")
        
        # Upload thumbnail if provided
        if thumbnail_reference_id:
            try:
                await _upload_thumbnail(
                    youtube_client=youtube_client,
                    video_id=video_id,
                    thumbnail_reference_id=thumbnail_reference_id,
                    file_manager=file_manager
                )
            except Exception as e:
                logger.warning(f"[Upload Task] Thumbnail upload failed: {e}")
        
        # Update final status
        await _update_upload_status(
            upload_id=upload_id,
            status=UploadStatus.COMPLETED,
            progress=100,
            video_id=video_id,
            completed_at=datetime.utcnow()
        )
        
        # Schedule cleanup of temporary files
        cleanup_video_files.send_with_options(
            args=(reference_id, thumbnail_reference_id),
            delay=timedelta(hours=1)  # Cleanup after 1 hour
        )
        
    except Exception as e:
        logger.error(f"[Upload Task] Error processing upload {upload_id}: {e}")
        raise


async def _upload_thumbnail(
    youtube_client: YouTubeClient,
    video_id: str,
    thumbnail_reference_id: str,
    file_manager: VideoFileManager
):
    """Upload thumbnail to YouTube video"""
    
    thumbnail_ref = await file_manager.get_reference(thumbnail_reference_id)
    if not thumbnail_ref:
        logger.warning(f"Thumbnail reference {thumbnail_reference_id} not found")
        return
    
    with open(thumbnail_ref["file_path"], "rb") as f:
        thumbnail_data = f.read()
    
    await youtube_client.upload_thumbnail(
        video_id=video_id,
        thumbnail_data=thumbnail_data,
        mime_type=thumbnail_ref["mime_type"]
    )
    
    logger.info(f"Thumbnail uploaded for video {video_id}")


async def _update_upload_status(
    upload_id: str,
    status: UploadStatus,
    progress: Optional[int] = None,
    bytes_uploaded: Optional[int] = None,
    total_bytes: Optional[int] = None,
    video_id: Optional[str] = None,
    error_message: Optional[str] = None,
    completed_at: Optional[datetime] = None
):
    """Update upload status in database"""
    
    from supabase import create_client
    supabase = create_client(
        os.getenv("SUPABASE_URL", ""),
        os.getenv("SUPABASE_ANON_KEY", "")
    )
    
    update_data = {
        "upload_status": status.value,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    if progress is not None:
        update_data["upload_progress"] = progress
    
    if bytes_uploaded is not None:
        update_data["bytes_uploaded"] = bytes_uploaded
    
    if total_bytes is not None:
        update_data["total_bytes"] = total_bytes
    
    if video_id:
        update_data["video_id"] = video_id
    
    if error_message:
        update_data["error_message"] = error_message
    
    if completed_at:
        update_data["completed_at"] = completed_at.isoformat()
    
    # Update in database
    result = supabase.table("youtube_uploads").update(update_data).eq("id", upload_id).execute()
    
    if not result.data:
        logger.error(f"Failed to update upload status for {upload_id}")


@actor(max_retries=1, time_limit=300000)  # 5 minutes
def cleanup_video_files(
    video_reference_id: str,
    thumbnail_reference_id: Optional[str] = None
):
    """
    Clean up temporary video files after successful upload
    
    This task runs after a delay to ensure files are no longer needed
    """
    logger.info(f"[Cleanup Task] Cleaning up files for reference {video_reference_id}")
    
    try:
        asyncio.run(_cleanup_files_async(
            video_reference_id=video_reference_id,
            thumbnail_reference_id=thumbnail_reference_id
        ))
    except Exception as e:
        logger.error(f"[Cleanup Task] Failed: {e}")
        # Don't retry cleanup failures


async def _cleanup_files_async(
    video_reference_id: str,
    thumbnail_reference_id: Optional[str] = None
):
    """Async implementation of file cleanup"""
    
    file_manager = VideoFileManager()
    
    # Clean up video file
    try:
        await file_manager.delete_reference(video_reference_id)
        logger.info(f"[Cleanup Task] Deleted video reference {video_reference_id}")
    except Exception as e:
        logger.warning(f"[Cleanup Task] Failed to delete video reference: {e}")
    
    # Clean up thumbnail if provided
    if thumbnail_reference_id:
        try:
            await file_manager.delete_reference(thumbnail_reference_id)
            logger.info(f"[Cleanup Task] Deleted thumbnail reference {thumbnail_reference_id}")
        except Exception as e:
            logger.warning(f"[Cleanup Task] Failed to delete thumbnail reference: {e}")


@actor(max_retries=2, min_backoff=30000)  # 30 seconds
def refresh_channel_token(channel_id: str):
    """
    Refresh YouTube channel access token
    
    This task runs when a token is expired or about to expire
    """
    logger.info(f"[Token Refresh] Refreshing token for channel {channel_id}")
    
    try:
        asyncio.run(_refresh_token_async(channel_id))
    except Exception as e:
        logger.error(f"[Token Refresh] Failed for channel {channel_id}: {e}")
        raise


async def _refresh_token_async(channel_id: str):
    """Async implementation of token refresh"""
    
    from supabase import create_client
    from .oauth import YouTubeMCPOAuth
    
    supabase = create_client(
        os.getenv("SUPABASE_URL", ""),
        os.getenv("SUPABASE_ANON_KEY", "")
    )
    
    channels_manager = YouTubeMCPChannels(supabase)
    oauth = YouTubeMCPOAuth()
    
    # Get channel with refresh token
    channel = await channels_manager.get_channel(channel_id)
    if not channel or not channel.get("refresh_token"):
        raise ValueError(f"Channel {channel_id} not found or missing refresh token")
    
    # Refresh the token
    new_token = await oauth.refresh_access_token(channel["refresh_token"])
    
    # Update channel with new token
    await channels_manager.update_channel_token(
        channel_id=channel_id,
        access_token=new_token.access_token,
        expiry=new_token.expiry
    )
    
    logger.info(f"[Token Refresh] Successfully refreshed token for channel {channel_id}")


@actor(max_retries=2)
def schedule_video_publish(
    upload_id: str,
    video_id: str,
    channel_id: str,
    publish_at: datetime
):
    """
    Schedule a video to be published at a specific time
    
    This task updates the video's privacy status from private/unlisted to public
    """
    logger.info(f"[Schedule Task] Scheduling video {video_id} for {publish_at}")
    
    # Calculate delay
    delay = publish_at - datetime.utcnow()
    if delay.total_seconds() <= 0:
        # Publish immediately if time has passed
        publish_video.send(upload_id, video_id, channel_id)
    else:
        # Schedule for future
        publish_video.send_with_options(
            args=(upload_id, video_id, channel_id),
            delay=delay
        )


@actor(max_retries=2)
def publish_video(upload_id: str, video_id: str, channel_id: str):
    """
    Publish a video by changing its privacy status to public
    """
    logger.info(f"[Publish Task] Publishing video {video_id}")
    
    try:
        asyncio.run(_publish_video_async(upload_id, video_id, channel_id))
    except Exception as e:
        logger.error(f"[Publish Task] Failed to publish video {video_id}: {e}")
        raise


async def _publish_video_async(upload_id: str, video_id: str, channel_id: str):
    """Async implementation of video publishing"""
    
    from supabase import create_client
    
    supabase = create_client(
        os.getenv("SUPABASE_URL", ""),
        os.getenv("SUPABASE_ANON_KEY", "")
    )
    
    channels_manager = YouTubeMCPChannels(supabase)
    
    # Get channel and token
    channel = await channels_manager.get_channel(channel_id)
    if not channel or not channel.get("access_token"):
        raise ValueError(f"Channel {channel_id} not found or not authenticated")
    
    # Initialize YouTube client
    youtube_client = YouTubeClient(channel["access_token"])
    
    # Update video privacy status
    await youtube_client.update_video_status(
        video_id=video_id,
        privacy_status="public"
    )
    
    # Update upload record
    result = supabase.table("youtube_uploads").update({
        "privacy_status": "public",
        "published_at": datetime.utcnow().isoformat()
    }).eq("id", upload_id).execute()
    
    logger.info(f"[Publish Task] Successfully published video {video_id}")


# Export actors for discovery
__all__ = [
    'process_video_upload',
    'cleanup_video_files', 
    'refresh_channel_token',
    'schedule_video_publish',
    'publish_video'
]