"""
YouTube Upload Video Tool for LiteLLM
Handles video uploads to YouTube channels
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class UploadVideoParams(BaseModel):
    """Parameters for YouTube video upload"""
    channel_id: str = Field(
        description="YouTube channel ID to upload to"
    )
    title: str = Field(
        description="Video title"
    )
    description: str = Field(
        description="Video description"
    )
    tags: Optional[List[str]] = Field(
        default=[],
        description="Video tags"
    )
    category_id: Optional[str] = Field(
        default="22",
        description="YouTube category ID (default: 22 = People & Blogs)"
    )
    privacy_status: Optional[str] = Field(
        default="public",
        description="Video privacy status (private, unlisted, public)"
    )
    made_for_kids: Optional[bool] = Field(
        default=False,
        description="Whether the video is made for kids"
    )
    scheduled_for: Optional[str] = Field(
        default=None,
        description="When to upload the video (e.g., 'tomorrow at 3pm', 'next Monday evening')"
    )
    notify_subscribers: Optional[bool] = Field(
        default=True,
        description="Whether to notify subscribers when video is published"
    )


class UploadVideoTool:
    """
    YouTube video upload tool for LiteLLM
    Uploads videos to YouTube with metadata
    """
    
    name = "youtube_upload_video"
    description = (
        "Upload a video to a specific YouTube channel. "
        "This tool automatically uses the most recent video and thumbnail files you uploaded. "
        "Just provide the channel ID, title and description for the video. "
        "You can schedule the upload for a future time using natural language like 'tomorrow at 3pm' or 'next Monday evening'."
    )
    
    def __init__(self, supabase_client: Any, channels_manager: Any, file_manager: Any):
        """
        Initialize upload tool with dependencies
        
        Args:
            supabase_client: Supabase client
            channels_manager: YouTube channels manager
            file_manager: YouTube file manager
        """
        self.supabase = supabase_client
        self.channels = channels_manager
        self.files = file_manager
    
    async def execute(self, params: UploadVideoParams, user_id: str) -> Dict[str, Any]:
        """
        Execute the video upload
        
        Args:
            params: Upload parameters
            user_id: User identifier
            
        Returns:
            Upload result dictionary
        """
        try:
            # Get latest pending uploads for user
            uploads = await self._get_latest_pending_uploads(user_id)
            
            if not uploads.get("video"):
                return {
                    "type": "error",
                    "error": "no_video",
                    "message": "No video file found. Please upload a video file first."
                }
            
            video_reference = uploads["video"]
            thumbnail_reference = uploads.get("thumbnail")
            
            logger.info(f"Found video reference: {video_reference['id']}")
            if thumbnail_reference:
                logger.info(f"Found thumbnail reference: {thumbnail_reference['id']}")
            
            # Get valid access token for channel
            access_token = await self.channels.get_valid_access_token(
                params.channel_id,
                user_id
            )
            
            # Get channel info for display
            channel = await self.channels.get_channel_by_id(
                params.channel_id,
                user_id
            )
            
            # Get file data
            file_data = await self.files.get_file_data(
                user_id,
                video_reference["id"]
            )
            
            if not file_data:
                return {
                    "type": "error",
                    "error": "file_not_found",
                    "message": f"File reference not found: {video_reference['id']}"
                }
            
            # Check for AI-generated metadata
            file_ref = await self.files.get_file_reference(user_id, video_reference["id"])
            metadata = self._prepare_metadata(params, file_ref)
            
            # Handle scheduled uploads
            scheduled_date = None
            schedule_interpretation = None
            
            if params.scheduled_for:
                # Parse scheduling date
                scheduled_date, schedule_interpretation = await self._parse_schedule_date(
                    params.scheduled_for
                )
                logger.info(f"Scheduling upload for: {schedule_interpretation}")
            
            # Create upload record
            upload_id = await self._create_upload_record(
                user_id=user_id,
                channel_id=params.channel_id,
                metadata=metadata,
                file_reference=video_reference,
                thumbnail_reference=thumbnail_reference,
                scheduled_date=scheduled_date
            )
            
            # If scheduled, don't upload immediately
            if scheduled_date:
                return {
                    "type": "youtube-upload-scheduled",
                    "upload_id": upload_id,
                    "channel_name": channel.name,
                    "scheduled_for": scheduled_date.isoformat(),
                    "interpretation": schedule_interpretation,
                    "message": f"Video '{metadata['title']}' scheduled for upload on {schedule_interpretation}"
                }
            
            # Start immediate upload
            from backend.youtube.upload_stream import YouTubeStreamingUpload
            from backend.youtube.client import YouTubeVideoMetadata
            
            uploader = YouTubeStreamingUpload(access_token)
            
            # Create video metadata object
            video_metadata = YouTubeVideoMetadata(
                title=metadata["title"],
                description=metadata["description"],
                tags=metadata["tags"],
                category_id=metadata["category_id"],
                privacy_status=metadata["privacy_status"],
                made_for_kids=metadata["made_for_kids"],
                notify_subscribers=metadata.get("notify_subscribers", True)
            )
            
            # Start async upload
            video_id = await uploader.upload_video_from_bytes(
                file_data,
                video_metadata,
                session_id=upload_id,
                on_progress=lambda p, u, t: self._update_upload_progress(upload_id, p, u, t)
            )
            
            # Update upload record with video ID
            await self._update_upload_record(upload_id, video_id=video_id, status="completed")
            
            # Upload thumbnail if provided
            if thumbnail_reference:
                await self._upload_thumbnail(
                    access_token,
                    video_id,
                    thumbnail_reference["id"],
                    user_id
                )
            
            # Mark references as used
            await self._mark_references_used([video_reference["id"]])
            if thumbnail_reference:
                await self._mark_references_used([thumbnail_reference["id"]])
            
            # Return success response
            return {
                "type": "youtube-upload",
                "upload_id": upload_id,
                "video_id": video_id,
                "title": metadata["title"],
                "channel_name": channel.name,
                "channel_id": channel.id,
                "file_name": video_reference["file_name"],
                "file_size": self._format_bytes(video_reference["file_size"]),
                "message": f"Upload completed for '{metadata['title']}'",
                "has_thumbnail": bool(thumbnail_reference)
            }
            
        except Exception as e:
            logger.error(f"Failed to upload video: {e}")
            return {
                "type": "error",
                "error": "upload_failed",
                "message": f"Failed to upload video: {str(e)}"
            }
    
    async def _get_latest_pending_uploads(self, user_id: str) -> Dict[str, Any]:
        """Get the latest pending video and thumbnail uploads"""
        try:
            # Get latest video upload
            video_result = self.supabase.table("upload_references").select("*").eq(
                "user_id", user_id
            ).eq("file_type", "video").eq("status", "pending").order(
                "created_at", desc=True
            ).limit(1).execute()
            
            # Get latest thumbnail upload
            thumbnail_result = self.supabase.table("upload_references").select("*").eq(
                "user_id", user_id
            ).eq("file_type", "thumbnail").eq("status", "pending").order(
                "created_at", desc=True
            ).limit(1).execute()
            
            uploads = {}
            if video_result.data:
                uploads["video"] = video_result.data[0]
            if thumbnail_result.data:
                uploads["thumbnail"] = thumbnail_result.data[0]
            
            return uploads
            
        except Exception as e:
            logger.error(f"Failed to get pending uploads: {e}")
            return {}
    
    def _prepare_metadata(self, params: UploadVideoParams, file_ref: Any) -> Dict[str, Any]:
        """Prepare video metadata, using AI-generated if available"""
        metadata = {
            "title": params.title,
            "description": params.description,
            "tags": params.tags or [],
            "category_id": params.category_id or "22",
            "privacy_status": params.privacy_status or "public",
            "made_for_kids": params.made_for_kids or False,
            "notify_subscribers": params.notify_subscribers
        }
        
        # Check for AI-generated metadata
        if file_ref and file_ref.generated_metadata and not params.title and not params.description:
            ai_metadata = file_ref.generated_metadata
            if isinstance(ai_metadata, list) and ai_metadata:
                ai_metadata = ai_metadata[0]
            
            if ai_metadata:
                logger.info("Using AI-generated metadata")
                metadata["title"] = ai_metadata.get("title", params.title)
                metadata["description"] = ai_metadata.get("description", params.description)
                metadata["tags"] = ai_metadata.get("tags", []) or params.tags or []
                if ai_metadata.get("category"):
                    metadata["category_id"] = ai_metadata["category"]
        
        return metadata
    
    async def _parse_schedule_date(self, schedule_text: str) -> tuple[datetime, str]:
        """Parse natural language scheduling date"""
        # This would integrate with a date parsing library
        # For now, return a simple implementation
        from datetime import timedelta
        
        now = datetime.utcnow()
        schedule_text_lower = schedule_text.lower()
        
        if "tomorrow" in schedule_text_lower:
            scheduled = now + timedelta(days=1)
            interpretation = f"tomorrow at {scheduled.strftime('%I:%M %p')}"
        elif "hour" in schedule_text_lower:
            hours = 1
            if "2 hour" in schedule_text_lower or "two hour" in schedule_text_lower:
                hours = 2
            elif "3 hour" in schedule_text_lower or "three hour" in schedule_text_lower:
                hours = 3
            scheduled = now + timedelta(hours=hours)
            interpretation = f"in {hours} hour{'s' if hours > 1 else ''}"
        else:
            # Default to 1 hour from now
            scheduled = now + timedelta(hours=1)
            interpretation = "in 1 hour"
        
        return scheduled, interpretation
    
    async def _create_upload_record(self, **kwargs) -> str:
        """Create an upload record in the database"""
        import uuid
        upload_id = str(uuid.uuid4())
        
        data = {
            "id": upload_id,
            "user_id": kwargs["user_id"],
            "channel_id": kwargs["channel_id"],
            "title": kwargs["metadata"]["title"],
            "description": kwargs["metadata"]["description"],
            "tags": kwargs["metadata"]["tags"],
            "category_id": kwargs["metadata"]["category_id"],
            "privacy_status": kwargs["metadata"]["privacy_status"],
            "made_for_kids": kwargs["metadata"]["made_for_kids"],
            "file_name": kwargs["file_reference"]["file_name"],
            "file_size": kwargs["file_reference"]["file_size"],
            "mime_type": kwargs["file_reference"]["mime_type"],
            "upload_status": "scheduled" if kwargs.get("scheduled_date") else "uploading",
            "upload_progress": 0,
            "created_at": datetime.utcnow().isoformat()
        }
        
        if kwargs.get("scheduled_date"):
            data["scheduled_for"] = kwargs["scheduled_date"].isoformat()
            data["video_reference_id"] = kwargs["file_reference"]["id"]
            if kwargs.get("thumbnail_reference"):
                data["thumbnail_reference_id"] = kwargs["thumbnail_reference"]["id"]
        
        self.supabase.table("youtube_uploads").insert(data).execute()
        return upload_id
    
    async def _update_upload_record(self, upload_id: str, **updates) -> None:
        """Update an upload record"""
        self.supabase.table("youtube_uploads").update(updates).eq(
            "id", upload_id
        ).execute()
    
    def _update_upload_progress(self, upload_id: str, progress: float, uploaded: int, total: int) -> None:
        """Update upload progress (sync callback)"""
        try:
            self.supabase.table("youtube_uploads").update({
                "upload_progress": progress,
                "upload_status": "uploading",
                "status_message": f"Uploaded {self._format_bytes(uploaded)} of {self._format_bytes(total)}"
            }).eq("id", upload_id).execute()
        except Exception as e:
            logger.error(f"Failed to update upload progress: {e}")
    
    async def _upload_thumbnail(self, access_token: str, video_id: str, thumbnail_ref_id: str, user_id: str) -> None:
        """Upload thumbnail for a video"""
        try:
            thumbnail_data = await self.files.get_file_data(user_id, thumbnail_ref_id)
            if thumbnail_data:
                from backend.youtube.client import YouTubeClient
                client = YouTubeClient(access_token)
                await client.upload_thumbnail(video_id, thumbnail_data)
                logger.info(f"Thumbnail uploaded for video {video_id}")
        except Exception as e:
            logger.error(f"Failed to upload thumbnail: {e}")
    
    async def _mark_references_used(self, reference_ids: List[str]) -> None:
        """Mark upload references as used"""
        for ref_id in reference_ids:
            try:
                self.supabase.table("upload_references").update({
                    "status": "used",
                    "used_at": datetime.utcnow().isoformat()
                }).eq("id", ref_id).execute()
            except Exception as e:
                logger.error(f"Failed to mark reference {ref_id} as used: {e}")
    
    @staticmethod
    def _format_bytes(bytes_value: int) -> str:
        """Format bytes as human-readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for this tool"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "YouTube channel ID to upload to"
                    },
                    "title": {
                        "type": "string",
                        "description": "Video title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Video description"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Video tags"
                    },
                    "category_id": {
                        "type": "string",
                        "description": "YouTube category ID"
                    },
                    "privacy_status": {
                        "type": "string",
                        "enum": ["private", "unlisted", "public"],
                        "description": "Video privacy status"
                    },
                    "made_for_kids": {
                        "type": "boolean",
                        "description": "Whether the video is made for kids"
                    },
                    "scheduled_for": {
                        "type": "string",
                        "description": "When to upload the video"
                    },
                    "notify_subscribers": {
                        "type": "boolean",
                        "description": "Whether to notify subscribers"
                    }
                },
                "required": ["channel_id", "title", "description"]
            }
        }