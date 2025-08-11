"""
YouTube File Manager for Suna
Handles file references, temporary storage, and cleanup
"""

import os
import logging
import hashlib
import mimetypes
from typing import Optional, List, Dict, Any, BinaryIO
from datetime import datetime, timedelta
from pathlib import Path
import aiofiles
import aiofiles.os
from pydantic import BaseModel
import uuid

logger = logging.getLogger(__name__)

# Default file storage configuration
FILE_STORAGE_PATH = os.getenv("YOUTUBE_FILE_STORAGE_PATH", "/tmp/suna-youtube-uploads")
FILE_EXPIRY_HOURS = int(os.getenv("YOUTUBE_FILE_EXPIRY_HOURS", "24"))
MAX_FILE_SIZE = int(os.getenv("YOUTUBE_MAX_FILE_SIZE", str(128 * 1024 * 1024 * 1024)))  # 128GB default
ALLOW_FILESYSTEM_UPLOADS = os.getenv("ALLOW_FILESYSTEM_UPLOADS", "false").lower() == "true"
ALLOWED_UPLOAD_PATHS = os.getenv("ALLOWED_UPLOAD_PATHS", "").split(",") if os.getenv("ALLOWED_UPLOAD_PATHS") else []


class VideoFileReference(BaseModel):
    """Video file reference model"""
    id: str
    user_id: str
    file_name: str
    file_path: Optional[str] = None
    file_size: int
    mime_type: str
    checksum: Optional[str] = None
    uploaded_at: datetime
    expires_at: datetime
    transcription: Optional[Dict[str, Any]] = None
    generated_metadata: Optional[List[Dict[str, Any]]] = None
    is_temporary: bool = True


class YouTubeFileManager:
    """
    Manages temporary file storage for YouTube uploads
    """
    
    def __init__(self, supabase_client: Any):
        """
        Initialize file manager with Supabase client
        
        Args:
            supabase_client: Initialized Supabase client
        """
        self.supabase = supabase_client
        self.storage_path = Path(FILE_STORAGE_PATH)
        
        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def generate_reference_id() -> str:
        """
        Generate a unique reference ID for a file
        
        Returns:
            32-character hexadecimal reference ID
        """
        # Generate a UUID and convert to hex (removing hyphens)
        # This ensures we get exactly 32 characters
        return uuid.uuid4().hex
    
    async def create_file_reference(
        self,
        user_id: str,
        file_data: bytes,
        file_name: str,
        mime_type: Optional[str] = None
    ) -> VideoFileReference:
        """
        Create a file reference and store the file temporarily
        
        Args:
            user_id: User identifier
            file_data: File content as bytes
            file_name: Original file name
            mime_type: MIME type of the file
            
        Returns:
            VideoFileReference object
            
        Raises:
            ValueError: If file is too large or invalid
        """
        # Check file size
        file_size = len(file_data)
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})")
        
        # Detect MIME type if not provided
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(file_name)
            if not mime_type:
                mime_type = "video/mp4"  # Default for videos
        
        # Validate video file
        if not mime_type.startswith("video/") and not mime_type.startswith("image/"):
            raise ValueError(f"Invalid file type: {mime_type}")
        
        # Generate reference ID and file path
        reference_id = self.generate_reference_id()
        file_extension = Path(file_name).suffix or ".mp4"
        stored_file_name = f"{reference_id}{file_extension}"
        file_path = self.storage_path / user_id / stored_file_name
        
        # Ensure user directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Calculate checksum
        checksum = hashlib.sha256(file_data).hexdigest()
        
        # Save file to disk
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_data)
        
        # Create reference object
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=FILE_EXPIRY_HOURS)
        
        reference = VideoFileReference(
            id=reference_id,
            user_id=user_id,
            file_name=file_name,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=mime_type,
            checksum=checksum,
            uploaded_at=now,
            expires_at=expires_at,
            is_temporary=True
        )
        
        # Store reference in database
        await self._save_reference_to_db(reference)
        
        logger.info(f"Created file reference {reference_id} for user {user_id}")
        return reference
    
    async def create_file_reference_from_path(
        self,
        user_id: str,
        file_path: str
    ) -> VideoFileReference:
        """
        Create a file reference from a file system path (for dev environments)
        
        Args:
            user_id: User identifier
            file_path: Path to the file on the file system
            
        Returns:
            VideoFileReference object
            
        Raises:
            ValueError: If filesystem uploads are disabled or path is not allowed
        """
        if not ALLOW_FILESYSTEM_UPLOADS:
            raise ValueError(
                "File system uploads are not enabled. "
                "Use the file upload endpoint to upload files."
            )
        
        # Resolve and validate path
        resolved_path = Path(file_path).resolve()
        
        # Check if path is in allowed directories
        if ALLOWED_UPLOAD_PATHS:
            path_allowed = False
            for allowed_path in ALLOWED_UPLOAD_PATHS:
                if allowed_path and resolved_path.is_relative_to(Path(allowed_path).resolve()):
                    path_allowed = True
                    break
            
            if not path_allowed:
                raise ValueError(f"File path not in allowed directories: {file_path}")
        
        # Check if file exists and is accessible
        if not resolved_path.exists():
            raise ValueError(f"File not found: {file_path}")
        
        if not resolved_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        # Get file info
        file_stat = resolved_path.stat()
        file_size = file_stat.st_size
        
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})")
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(str(resolved_path))
        if not mime_type:
            mime_type = "video/mp4"
        
        # Generate reference ID
        reference_id = self.generate_reference_id()
        
        # Create reference object (pointing to original file, not copying)
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=FILE_EXPIRY_HOURS)
        
        reference = VideoFileReference(
            id=reference_id,
            user_id=user_id,
            file_name=resolved_path.name,
            file_path=str(resolved_path),
            file_size=file_size,
            mime_type=mime_type,
            checksum=None,  # Skip checksum for filesystem references
            uploaded_at=now,
            expires_at=expires_at,
            is_temporary=False  # Don't delete filesystem references
        )
        
        # Store reference in database
        await self._save_reference_to_db(reference)
        
        logger.info(f"Created filesystem reference {reference_id} for {file_path}")
        return reference
    
    async def get_file_reference(
        self,
        user_id: str,
        reference_id: str
    ) -> Optional[VideoFileReference]:
        """
        Get a file reference by ID
        
        Args:
            user_id: User identifier
            reference_id: Reference ID
            
        Returns:
            VideoFileReference if found, None otherwise
        """
        try:
            # Fetch from database
            result = self.supabase.table("video_file_references").select("*").eq(
                "id", reference_id
            ).eq("user_id", user_id).single().execute()
            
            if not result.data:
                return None
            
            # Convert to VideoFileReference
            data = result.data
            reference = VideoFileReference(
                id=data["id"],
                user_id=data["user_id"],
                file_name=data["file_name"],
                file_path=data.get("file_path"),
                file_size=data["file_size"],
                mime_type=data["mime_type"],
                checksum=data.get("checksum"),
                uploaded_at=datetime.fromisoformat(data["uploaded_at"]),
                expires_at=datetime.fromisoformat(data["expires_at"]),
                transcription=data.get("transcription"),
                generated_metadata=data.get("generated_metadata"),
                is_temporary=data.get("is_temporary", True)
            )
            
            # Check if reference has expired
            if reference.expires_at < datetime.utcnow():
                logger.warning(f"Reference {reference_id} has expired")
                await self.delete_file_reference(user_id, reference_id)
                return None
            
            return reference
            
        except Exception as e:
            logger.error(f"Failed to get file reference: {e}")
            return None
    
    async def get_file_data(
        self,
        user_id: str,
        reference_id: str
    ) -> Optional[bytes]:
        """
        Get file data for a reference
        
        Args:
            user_id: User identifier
            reference_id: Reference ID
            
        Returns:
            File data as bytes if found, None otherwise
        """
        reference = await self.get_file_reference(user_id, reference_id)
        
        if not reference or not reference.file_path:
            return None
        
        file_path = Path(reference.file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                data = await f.read()
            return data
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            return None
    
    async def delete_file_reference(
        self,
        user_id: str,
        reference_id: str
    ) -> bool:
        """
        Delete a file reference and its associated file
        
        Args:
            user_id: User identifier
            reference_id: Reference ID
            
        Returns:
            True if successful
        """
        try:
            # Get reference first
            reference = await self.get_file_reference(user_id, reference_id)
            
            if reference and reference.file_path and reference.is_temporary:
                # Delete the actual file if it's temporary
                file_path = Path(reference.file_path)
                if file_path.exists():
                    await aiofiles.os.remove(file_path)
                    logger.info(f"Deleted file: {file_path}")
            
            # Delete from database
            self.supabase.table("video_file_references").delete().eq(
                "id", reference_id
            ).eq("user_id", user_id).execute()
            
            logger.info(f"Deleted reference {reference_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file reference: {e}")
            return False
    
    async def cleanup_expired_references(self) -> int:
        """
        Clean up expired file references and their files
        
        Returns:
            Number of references cleaned up
        """
        try:
            now = datetime.utcnow()
            
            # Find expired references
            result = self.supabase.table("video_file_references").select("*").lt(
                "expires_at", now.isoformat()
            ).execute()
            
            cleaned = 0
            for data in result.data:
                try:
                    # Delete file if temporary
                    if data.get("is_temporary") and data.get("file_path"):
                        file_path = Path(data["file_path"])
                        if file_path.exists():
                            await aiofiles.os.remove(file_path)
                    
                    # Delete from database
                    self.supabase.table("video_file_references").delete().eq(
                        "id", data["id"]
                    ).execute()
                    
                    cleaned += 1
                    
                except Exception as e:
                    logger.error(f"Failed to cleanup reference {data['id']}: {e}")
            
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} expired file references")
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired references: {e}")
            return 0
    
    async def list_user_references(
        self,
        user_id: str
    ) -> List[VideoFileReference]:
        """
        List all active file references for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            List of VideoFileReference objects
        """
        try:
            now = datetime.utcnow()
            
            # Fetch active references
            result = self.supabase.table("video_file_references").select("*").eq(
                "user_id", user_id
            ).gt("expires_at", now.isoformat()).execute()
            
            references = []
            for data in result.data:
                reference = VideoFileReference(
                    id=data["id"],
                    user_id=data["user_id"],
                    file_name=data["file_name"],
                    file_path=data.get("file_path"),
                    file_size=data["file_size"],
                    mime_type=data["mime_type"],
                    checksum=data.get("checksum"),
                    uploaded_at=datetime.fromisoformat(data["uploaded_at"]),
                    expires_at=datetime.fromisoformat(data["expires_at"]),
                    transcription=data.get("transcription"),
                    generated_metadata=data.get("generated_metadata"),
                    is_temporary=data.get("is_temporary", True)
                )
                references.append(reference)
            
            return references
            
        except Exception as e:
            logger.error(f"Failed to list user references: {e}")
            return []
    
    async def _save_reference_to_db(self, reference: VideoFileReference) -> None:
        """
        Save a file reference to the database
        
        Args:
            reference: VideoFileReference to save
            
        Raises:
            ValueError: If save fails
        """
        try:
            data = {
                "id": reference.id,
                "user_id": reference.user_id,
                "file_name": reference.file_name,
                "file_path": reference.file_path,
                "file_size": reference.file_size,
                "mime_type": reference.mime_type,
                "checksum": reference.checksum,
                "uploaded_at": reference.uploaded_at.isoformat(),
                "expires_at": reference.expires_at.isoformat(),
                "transcription": reference.transcription,
                "generated_metadata": reference.generated_metadata,
                "is_temporary": reference.is_temporary
            }
            
            self.supabase.table("video_file_references").insert(data).execute()
            
        except Exception as e:
            logger.error(f"Failed to save reference to database: {e}")
            raise ValueError(f"Failed to save file reference: {str(e)}")