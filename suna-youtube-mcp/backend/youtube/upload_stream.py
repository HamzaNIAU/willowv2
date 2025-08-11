"""
YouTube Streaming Upload for Suna
Handles chunked uploads, resume capability, and progress tracking
"""

import logging
import asyncio
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import aiofiles

from .client import YouTubeClient, YouTubeVideoMetadata

logger = logging.getLogger(__name__)

# Upload configuration
CHUNK_SIZE = 256 * 1024 * 1024  # 256MB chunks (YouTube recommends at least 256KB)
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes as human-readable string
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


class UploadSession:
    """YouTube upload session information"""
    
    def __init__(self, upload_url: str, total_bytes: int):
        self.upload_url = upload_url
        self.total_bytes = total_bytes
        self.bytes_uploaded = 0
        self.video_id: Optional[str] = None
        self.start_time = datetime.utcnow()
        self.last_update = datetime.utcnow()
        self.status = "initializing"
        self.error: Optional[str] = None
        self.retries = 0
    
    @property
    def progress_percentage(self) -> float:
        """Calculate upload progress percentage"""
        if self.total_bytes == 0:
            return 0.0
        return (self.bytes_uploaded / self.total_bytes) * 100
    
    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time in seconds"""
        return (datetime.utcnow() - self.start_time).total_seconds()
    
    @property
    def upload_speed(self) -> float:
        """Calculate average upload speed in bytes per second"""
        if self.elapsed_seconds == 0:
            return 0.0
        return self.bytes_uploaded / self.elapsed_seconds
    
    @property
    def estimated_time_remaining(self) -> float:
        """Estimate remaining time in seconds"""
        if self.upload_speed == 0:
            return 0.0
        remaining_bytes = self.total_bytes - self.bytes_uploaded
        return remaining_bytes / self.upload_speed


class YouTubeStreamingUpload:
    """
    Handles streaming uploads to YouTube with progress tracking
    """
    
    def __init__(self, access_token: str):
        """
        Initialize streaming upload handler
        
        Args:
            access_token: Valid YouTube OAuth access token
        """
        self.client = YouTubeClient(access_token)
        self.access_token = access_token
        self.sessions: Dict[str, UploadSession] = {}
        self._cancelled_uploads = set()
    
    async def upload_video_from_file(
        self,
        file_path: str,
        metadata: YouTubeVideoMetadata,
        session_id: Optional[str] = None,
        on_progress: Optional[Callable[[float, int, int], None]] = None
    ) -> str:
        """
        Upload a video from a file path
        
        Args:
            file_path: Path to the video file
            metadata: Video metadata
            session_id: Optional session ID for tracking
            on_progress: Optional progress callback
            
        Returns:
            YouTube video ID
            
        Raises:
            ValueError: If upload fails
        """
        try:
            # Get file size
            async with aiofiles.open(file_path, 'rb') as f:
                await f.seek(0, 2)  # Seek to end
                file_size = await f.tell()
                await f.seek(0)  # Reset to beginning
            
            # Initialize upload session
            upload_url = await self.client.initiate_resumable_upload(
                metadata,
                file_size,
                "video/*"
            )
            
            # Create session
            session = UploadSession(upload_url, file_size)
            if session_id:
                self.sessions[session_id] = session
            
            # Upload file in chunks
            video_id = await self._upload_file_chunks(
                file_path,
                session,
                on_progress
            )
            
            return video_id
            
        except Exception as e:
            logger.error(f"Failed to upload video from file: {e}")
            raise ValueError(f"Failed to upload video: {str(e)}")
    
    async def upload_video_from_bytes(
        self,
        file_data: bytes,
        metadata: YouTubeVideoMetadata,
        session_id: Optional[str] = None,
        on_progress: Optional[Callable[[float, int, int], None]] = None
    ) -> str:
        """
        Upload a video from bytes data
        
        Args:
            file_data: Video data as bytes
            metadata: Video metadata
            session_id: Optional session ID for tracking
            on_progress: Optional progress callback
            
        Returns:
            YouTube video ID
            
        Raises:
            ValueError: If upload fails
        """
        try:
            file_size = len(file_data)
            
            # Initialize upload session
            upload_url = await self.client.initiate_resumable_upload(
                metadata,
                file_size,
                "video/*"
            )
            
            # Create session
            session = UploadSession(upload_url, file_size)
            if session_id:
                self.sessions[session_id] = session
            
            # Upload data in chunks
            video_id = await self._upload_bytes_chunks(
                file_data,
                session,
                on_progress
            )
            
            return video_id
            
        except Exception as e:
            logger.error(f"Failed to upload video from bytes: {e}")
            raise ValueError(f"Failed to upload video: {str(e)}")
    
    async def _upload_file_chunks(
        self,
        file_path: str,
        session: UploadSession,
        on_progress: Optional[Callable[[float, int, int], None]] = None
    ) -> str:
        """
        Upload a file in chunks
        
        Args:
            file_path: Path to the file
            session: Upload session
            on_progress: Optional progress callback
            
        Returns:
            Video ID when complete
            
        Raises:
            ValueError: If upload fails
        """
        session.status = "uploading"
        
        async with aiofiles.open(file_path, 'rb') as f:
            while session.bytes_uploaded < session.total_bytes:
                # Check if upload was cancelled
                if session_id := self._get_session_id(session):
                    if session_id in self._cancelled_uploads:
                        session.status = "cancelled"
                        raise ValueError("Upload cancelled by user")
                
                # Read chunk
                chunk_size = min(CHUNK_SIZE, session.total_bytes - session.bytes_uploaded)
                chunk_data = await f.read(chunk_size)
                
                if not chunk_data:
                    break
                
                # Upload chunk with retry logic
                for retry in range(MAX_RETRIES):
                    try:
                        result = await self._upload_chunk(
                            session,
                            chunk_data,
                            session.bytes_uploaded,
                            session.bytes_uploaded + len(chunk_data) - 1
                        )
                        
                        if result.get("status") == "complete":
                            session.video_id = result.get("video_id")
                            session.bytes_uploaded = session.total_bytes
                            session.status = "completed"
                            
                            if on_progress:
                                await self._call_progress_async(
                                    on_progress,
                                    100.0,
                                    session.total_bytes,
                                    session.total_bytes
                                )
                            
                            return session.video_id
                        
                        # Update progress
                        session.bytes_uploaded += len(chunk_data)
                        session.last_update = datetime.utcnow()
                        
                        if on_progress:
                            await self._call_progress_async(
                                on_progress,
                                session.progress_percentage,
                                session.bytes_uploaded,
                                session.total_bytes
                            )
                        
                        break  # Success, exit retry loop
                        
                    except Exception as e:
                        session.retries += 1
                        if retry == MAX_RETRIES - 1:
                            session.status = "failed"
                            session.error = str(e)
                            raise ValueError(f"Failed to upload chunk after {MAX_RETRIES} retries: {e}")
                        
                        logger.warning(f"Chunk upload failed (retry {retry + 1}/{MAX_RETRIES}): {e}")
                        await asyncio.sleep(RETRY_DELAY)
        
        # Should not reach here unless file is empty
        raise ValueError("No data to upload")
    
    async def _upload_bytes_chunks(
        self,
        file_data: bytes,
        session: UploadSession,
        on_progress: Optional[Callable[[float, int, int], None]] = None
    ) -> str:
        """
        Upload bytes data in chunks
        
        Args:
            file_data: Data to upload
            session: Upload session
            on_progress: Optional progress callback
            
        Returns:
            Video ID when complete
            
        Raises:
            ValueError: If upload fails
        """
        session.status = "uploading"
        
        while session.bytes_uploaded < session.total_bytes:
            # Check if upload was cancelled
            if session_id := self._get_session_id(session):
                if session_id in self._cancelled_uploads:
                    session.status = "cancelled"
                    raise ValueError("Upload cancelled by user")
            
            # Get chunk
            start = session.bytes_uploaded
            end = min(start + CHUNK_SIZE, session.total_bytes)
            chunk_data = file_data[start:end]
            
            if not chunk_data:
                break
            
            # Upload chunk with retry logic
            for retry in range(MAX_RETRIES):
                try:
                    result = await self._upload_chunk(
                        session,
                        chunk_data,
                        start,
                        end - 1
                    )
                    
                    if result.get("status") == "complete":
                        session.video_id = result.get("video_id")
                        session.bytes_uploaded = session.total_bytes
                        session.status = "completed"
                        
                        if on_progress:
                            await self._call_progress_async(
                                on_progress,
                                100.0,
                                session.total_bytes,
                                session.total_bytes
                            )
                        
                        return session.video_id
                    
                    # Update progress
                    session.bytes_uploaded = end
                    session.last_update = datetime.utcnow()
                    
                    if on_progress:
                        await self._call_progress_async(
                            on_progress,
                            session.progress_percentage,
                            session.bytes_uploaded,
                            session.total_bytes
                        )
                    
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    session.retries += 1
                    if retry == MAX_RETRIES - 1:
                        session.status = "failed"
                        session.error = str(e)
                        raise ValueError(f"Failed to upload chunk after {MAX_RETRIES} retries: {e}")
                    
                    logger.warning(f"Chunk upload failed (retry {retry + 1}/{MAX_RETRIES}): {e}")
                    await asyncio.sleep(RETRY_DELAY)
        
        # Should not reach here unless data is empty
        raise ValueError("No data to upload")
    
    async def _upload_chunk(
        self,
        session: UploadSession,
        chunk_data: bytes,
        start_byte: int,
        end_byte: int
    ) -> Dict[str, Any]:
        """
        Upload a single chunk
        
        Args:
            session: Upload session
            chunk_data: Chunk data
            start_byte: Starting byte position
            end_byte: Ending byte position
            
        Returns:
            Upload result
        """
        return await self.client.upload_video_chunk(
            session.upload_url,
            chunk_data,
            start_byte,
            end_byte,
            session.total_bytes
        )
    
    def cancel_upload(self, session_id: str) -> bool:
        """
        Cancel an ongoing upload
        
        Args:
            session_id: Session ID to cancel
            
        Returns:
            True if cancelled, False if not found
        """
        if session_id in self.sessions:
            self._cancelled_uploads.add(session_id)
            session = self.sessions[session_id]
            session.status = "cancelled"
            logger.info(f"Cancelled upload session {session_id}")
            return True
        return False
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of an upload session
        
        Args:
            session_id: Session ID
            
        Returns:
            Session status dictionary or None
        """
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        return {
            "session_id": session_id,
            "status": session.status,
            "video_id": session.video_id,
            "progress": {
                "bytes_uploaded": session.bytes_uploaded,
                "total_bytes": session.total_bytes,
                "percentage": session.progress_percentage,
                "formatted_uploaded": format_bytes(session.bytes_uploaded),
                "formatted_total": format_bytes(session.total_bytes)
            },
            "timing": {
                "elapsed_seconds": session.elapsed_seconds,
                "upload_speed_bps": session.upload_speed,
                "upload_speed_formatted": format_bytes(int(session.upload_speed)) + "/s",
                "estimated_time_remaining": session.estimated_time_remaining
            },
            "error": session.error,
            "retries": session.retries
        }
    
    def _get_session_id(self, session: UploadSession) -> Optional[str]:
        """Get session ID for a session object"""
        for sid, sess in self.sessions.items():
            if sess == session:
                return sid
        return None
    
    async def _call_progress_async(
        self,
        callback: Callable,
        progress: float,
        bytes_uploaded: int,
        total_bytes: int
    ) -> None:
        """Call progress callback, handling both sync and async callbacks"""
        if asyncio.iscoroutinefunction(callback):
            await callback(progress, bytes_uploaded, total_bytes)
        else:
            callback(progress, bytes_uploaded, total_bytes)