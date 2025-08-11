"""
YouTube API Client for Suna
Handles all YouTube Data API v3 interactions
"""

import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTubeChannel(BaseModel):
    """YouTube channel information"""
    id: str
    name: str
    custom_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    subscriber_count: int = 0
    view_count: int = 0
    video_count: int = 0


class YouTubeVideoMetadata(BaseModel):
    """YouTube video metadata for uploads"""
    title: str
    description: str
    tags: List[str] = []
    category_id: str = "22"  # People & Blogs
    privacy_status: str = "private"
    made_for_kids: bool = False
    notify_subscribers: bool = True
    publish_at: Optional[datetime] = None


class YouTubeUploadProgress(BaseModel):
    """Upload progress information"""
    bytes_uploaded: int
    total_bytes: int
    progress_percentage: float
    status: str


class YouTubeClient:
    """
    YouTube API client for interacting with YouTube Data API v3
    """
    
    def __init__(self, access_token: str):
        """
        Initialize YouTube client with access token
        
        Args:
            access_token: Valid YouTube OAuth access token
        """
        self.access_token = access_token
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    def __del__(self):
        """Cleanup HTTP client"""
        if hasattr(self, 'http_client'):
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.http_client.aclose())
            except:
                pass
    
    async def get_my_channels(self) -> List[YouTubeChannel]:
        """
        Get authenticated user's YouTube channels
        
        Returns:
            List of YouTubeChannel objects
            
        Raises:
            ValueError: If API request fails
        """
        try:
            response = await self.http_client.get(
                f"{YOUTUBE_API_BASE_URL}/channels",
                params={
                    "part": "snippet,statistics,contentDetails",
                    "mine": "true"
                },
                headers={
                    "Authorization": f"Bearer {self.access_token}"
                }
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Failed to fetch channels: {error_text}")
                raise ValueError(f"Failed to fetch channels: {error_text}")
            
            data = response.json()
            
            if not data.get("items"):
                logger.warning("No YouTube channels found for this account")
                return []
            
            channels = []
            for item in data["items"]:
                snippet = item.get("snippet", {})
                statistics = item.get("statistics", {})
                
                channel = YouTubeChannel(
                    id=item["id"],
                    name=snippet.get("title", "Unknown Channel"),
                    custom_url=snippet.get("customUrl"),
                    thumbnail_url=snippet.get("thumbnails", {}).get("default", {}).get("url"),
                    subscriber_count=int(statistics.get("subscriberCount", 0)),
                    view_count=int(statistics.get("viewCount", 0)),
                    video_count=int(statistics.get("videoCount", 0))
                )
                channels.append(channel)
            
            return channels
            
        except httpx.RequestError as e:
            logger.error(f"Network error fetching channels: {e}")
            raise ValueError(f"Network error fetching channels: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error fetching channels: {e}")
            raise ValueError(f"Failed to fetch channels: {str(e)}")
    
    async def initiate_resumable_upload(
        self,
        metadata: YouTubeVideoMetadata,
        file_size: int,
        mime_type: str = "video/*"
    ) -> str:
        """
        Initiate a resumable upload session for large video files
        
        Args:
            metadata: Video metadata
            file_size: Size of the video file in bytes
            mime_type: MIME type of the video
            
        Returns:
            Upload URL for resumable upload
            
        Raises:
            ValueError: If upload initiation fails
        """
        # Prepare video resource
        video_resource = {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "categoryId": metadata.category_id
            },
            "status": {
                "privacyStatus": metadata.privacy_status,
                "selfDeclaredMadeForKids": metadata.made_for_kids,
                "notifySubscribers": metadata.notify_subscribers
            }
        }
        
        # Handle scheduled publishing
        if metadata.publish_at:
            video_resource["status"]["privacyStatus"] = "private"
            video_resource["status"]["publishAt"] = metadata.publish_at.isoformat() + "Z"
        
        try:
            response = await self.http_client.post(
                f"{YOUTUBE_UPLOAD_URL}?uploadType=resumable&part=snippet,status",
                json=video_resource,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                    "X-Upload-Content-Length": str(file_size),
                    "X-Upload-Content-Type": mime_type
                }
            )
            
            if response.status_code not in [200, 201]:
                error_text = response.text
                logger.error(f"Failed to initiate upload: {error_text}")
                raise ValueError(f"Failed to initiate upload: {error_text}")
            
            upload_url = response.headers.get("location")
            if not upload_url:
                raise ValueError("No upload URL returned from YouTube")
            
            return upload_url
            
        except httpx.RequestError as e:
            logger.error(f"Network error initiating upload: {e}")
            raise ValueError(f"Network error initiating upload: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error initiating upload: {e}")
            raise ValueError(f"Failed to initiate upload: {str(e)}")
    
    async def upload_video_chunk(
        self,
        upload_url: str,
        chunk_data: bytes,
        start_byte: int,
        end_byte: int,
        total_size: int
    ) -> Dict[str, Any]:
        """
        Upload a chunk of video data
        
        Args:
            upload_url: Resumable upload URL
            chunk_data: Chunk of video data
            start_byte: Starting byte position
            end_byte: Ending byte position
            total_size: Total file size
            
        Returns:
            Upload response including video ID when complete
            
        Raises:
            ValueError: If chunk upload fails
        """
        headers = {
            "Content-Length": str(len(chunk_data)),
            "Content-Range": f"bytes {start_byte}-{end_byte}/{total_size}"
        }
        
        try:
            response = await self.http_client.put(
                upload_url,
                content=chunk_data,
                headers=headers
            )
            
            # 308 Resume Incomplete is expected for non-final chunks
            if response.status_code == 308:
                # Get the range header to know what's been uploaded
                range_header = response.headers.get("range", "")
                return {"status": "incomplete", "range": range_header}
            
            # 200 or 201 means upload complete
            if response.status_code in [200, 201]:
                data = response.json()
                return {
                    "status": "complete",
                    "video_id": data.get("id"),
                    "data": data
                }
            
            # Any other status is an error
            error_text = response.text
            logger.error(f"Chunk upload failed: {error_text}")
            raise ValueError(f"Chunk upload failed: {error_text}")
            
        except httpx.RequestError as e:
            logger.error(f"Network error uploading chunk: {e}")
            raise ValueError(f"Network error uploading chunk: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error uploading chunk: {e}")
            raise ValueError(f"Failed to upload chunk: {str(e)}")
    
    async def upload_thumbnail(self, video_id: str, thumbnail_data: bytes) -> bool:
        """
        Upload a thumbnail for a video
        
        Args:
            video_id: YouTube video ID
            thumbnail_data: Thumbnail image data
            
        Returns:
            True if successful
            
        Raises:
            ValueError: If thumbnail upload fails
        """
        try:
            response = await self.http_client.post(
                f"{YOUTUBE_API_BASE_URL}/thumbnails/set",
                params={"videoId": video_id},
                files={"media": ("thumbnail.jpg", thumbnail_data, "image/jpeg")},
                headers={
                    "Authorization": f"Bearer {self.access_token}"
                }
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Failed to upload thumbnail: {error_text}")
                raise ValueError(f"Failed to upload thumbnail: {error_text}")
            
            return True
            
        except httpx.RequestError as e:
            logger.error(f"Network error uploading thumbnail: {e}")
            raise ValueError(f"Network error uploading thumbnail: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error uploading thumbnail: {e}")
            raise ValueError(f"Failed to upload thumbnail: {str(e)}")
    
    async def get_video_details(self, video_id: str) -> Dict[str, Any]:
        """
        Get details for a specific video
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Video details dictionary
            
        Raises:
            ValueError: If request fails
        """
        try:
            response = await self.http_client.get(
                f"{YOUTUBE_API_BASE_URL}/videos",
                params={
                    "part": "snippet,status,statistics",
                    "id": video_id
                },
                headers={
                    "Authorization": f"Bearer {self.access_token}"
                }
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Failed to get video details: {error_text}")
                raise ValueError(f"Failed to get video details: {error_text}")
            
            data = response.json()
            
            if not data.get("items"):
                raise ValueError(f"Video with ID {video_id} not found")
            
            return data["items"][0]
            
        except httpx.RequestError as e:
            logger.error(f"Network error getting video details: {e}")
            raise ValueError(f"Network error getting video details: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting video details: {e}")
            raise ValueError(f"Failed to get video details: {str(e)}")
    
    async def delete_video(self, video_id: str) -> bool:
        """
        Delete a video from YouTube
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            True if successful
            
        Raises:
            ValueError: If deletion fails
        """
        try:
            response = await self.http_client.delete(
                f"{YOUTUBE_API_BASE_URL}/videos",
                params={"id": video_id},
                headers={
                    "Authorization": f"Bearer {self.access_token}"
                }
            )
            
            if response.status_code != 204:
                error_text = response.text
                logger.error(f"Failed to delete video: {error_text}")
                raise ValueError(f"Failed to delete video: {error_text}")
            
            return True
            
        except httpx.RequestError as e:
            logger.error(f"Network error deleting video: {e}")
            raise ValueError(f"Network error deleting video: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error deleting video: {e}")
            raise ValueError(f"Failed to delete video: {str(e)}")