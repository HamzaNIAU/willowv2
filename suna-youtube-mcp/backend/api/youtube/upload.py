"""
YouTube Upload API Routes for FastAPI
Handles file preparation, upload initiation, and progress tracking
"""

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import json
import uuid

from backend.auth import get_current_user
from backend.database import get_supabase_client
from backend.youtube.channels import YouTubeMCPChannels
from backend.youtube.file_manager import YouTubeFileManager
from backend.youtube.upload_stream import YouTubeStreamingUpload, format_bytes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/youtube", tags=["YouTube Upload"])


@router.post("/prepare-upload")
async def prepare_upload(
    file: UploadFile = File(...),
    file_type: str = Form(default="video"),
    user = Depends(get_current_user)
):
    """
    Prepare a file for upload by creating a reference
    
    Args:
        file: Video or thumbnail file
        file_type: Type of file ('video' or 'thumbnail')
        
    Returns:
        Reference ID and file information
    """
    try:
        # Validate file type
        if file_type == "video":
            if not file.content_type or not file.content_type.startswith("video/"):
                raise HTTPException(
                    status_code=400,
                    detail="File must be a video"
                )
        elif file_type == "thumbnail":
            if not file.content_type or not file.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=400,
                    detail="Thumbnail must be an image"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Must be 'video' or 'thumbnail'"
            )
        
        # Read file content
        file_data = await file.read()
        
        # Get Supabase client and file manager
        supabase = get_supabase_client()
        file_manager = YouTubeFileManager(supabase)
        
        # Create file reference
        reference = await file_manager.create_file_reference(
            user_id=user.id,
            file_data=file_data,
            file_name=file.filename,
            mime_type=file.content_type
        )
        
        # Store in upload_references for AI tools
        upload_ref_data = {
            "id": str(uuid.uuid4()),
            "user_id": user.id,
            "reference_id": reference.id,
            "file_name": file.filename,
            "file_size": format_bytes(reference.file_size),
            "file_type": file_type,
            "mime_type": file.content_type,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("upload_references").insert(upload_ref_data).execute()
        
        # Check if auto-transcribe is enabled (for videos)
        if file_type == "video":
            preferences = supabase.table("user_preferences").select("*").eq(
                "user_id", user.id
            ).single().execute()
            
            if preferences.data and preferences.data.get("auto_transcribe_videos"):
                logger.info(f"Auto-transcribe enabled for user {user.id}")
                # TODO: Implement transcription service
        
        return {
            "reference_id": reference.id,
            "file_name": reference.file_name,
            "file_size": format_bytes(reference.file_size),
            "mime_type": reference.mime_type,
            "expires_at": reference.expires_at.isoformat(),
            "message": f"{'Video' if file_type == 'video' else 'Thumbnail'} prepared for upload"
        }
        
    except Exception as e:
        logger.error(f"Failed to prepare upload: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to prepare upload: {str(e)}"
        )


@router.get("/prepare-upload")
async def list_prepared_uploads(
    user = Depends(get_current_user)
):
    """
    List all prepared uploads for the user
    
    Returns:
        List of file references
    """
    try:
        supabase = get_supabase_client()
        file_manager = YouTubeFileManager(supabase)
        
        references = await file_manager.list_user_references(user.id)
        
        return {
            "files": [
                {
                    "reference_id": ref.id,
                    "file_name": ref.file_name,
                    "file_size": format_bytes(ref.file_size),
                    "mime_type": ref.mime_type,
                    "uploaded_at": ref.uploaded_at.isoformat(),
                    "expires_at": ref.expires_at.isoformat()
                }
                for ref in references
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to list prepared uploads: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list prepared uploads"
        )


@router.post("/upload")
async def initiate_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    user = Depends(get_current_user)
):
    """
    Initiate video upload to YouTube
    
    Request body:
        channel_id: YouTube channel ID
        reference_id: File reference ID
        metadata: Video metadata (title, description, etc.)
        
    Returns:
        Upload session information
    """
    try:
        body = await request.json()
        
        channel_id = body.get("channel_id")
        reference_id = body.get("reference_id")
        metadata = body.get("metadata", {})
        
        if not channel_id or not reference_id:
            raise HTTPException(
                status_code=400,
                detail="channel_id and reference_id are required"
            )
        
        # Get dependencies
        supabase = get_supabase_client()
        channels_manager = YouTubeMCPChannels(supabase)
        file_manager = YouTubeFileManager(supabase)
        
        # Get valid access token
        access_token = await channels_manager.get_valid_access_token(
            channel_id,
            user.id
        )
        
        # Get file data
        file_data = await file_manager.get_file_data(user.id, reference_id)
        if not file_data:
            raise HTTPException(
                status_code=404,
                detail=f"File reference not found: {reference_id}"
            )
        
        # Get file reference for metadata
        file_ref = await file_manager.get_file_reference(user.id, reference_id)
        
        # Create upload session
        upload_id = str(uuid.uuid4())
        uploader = YouTubeStreamingUpload(access_token)
        
        # Create upload record
        upload_record = {
            "id": upload_id,
            "user_id": user.id,
            "channel_id": channel_id,
            "title": metadata.get("title", "Untitled"),
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags", []),
            "category_id": metadata.get("category_id", "22"),
            "privacy_status": metadata.get("privacy_status", "private"),
            "made_for_kids": metadata.get("made_for_kids", False),
            "file_name": file_ref.file_name,
            "file_size": file_ref.file_size,
            "mime_type": file_ref.mime_type,
            "upload_status": "uploading",
            "upload_progress": 0,
            "created_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("youtube_uploads").insert(upload_record).execute()
        
        # Start upload in background
        from backend.youtube.client import YouTubeVideoMetadata
        
        video_metadata = YouTubeVideoMetadata(
            title=metadata.get("title", "Untitled"),
            description=metadata.get("description", ""),
            tags=metadata.get("tags", []),
            category_id=metadata.get("category_id", "22"),
            privacy_status=metadata.get("privacy_status", "private"),
            made_for_kids=metadata.get("made_for_kids", False)
        )
        
        # Add background task for upload
        background_tasks.add_task(
            _perform_upload,
            uploader,
            file_data,
            video_metadata,
            upload_id,
            supabase
        )
        
        return {
            "upload_id": upload_id,
            "status": "uploading",
            "message": f"Upload started for '{metadata.get('title', 'Untitled')}'",
            "channel_id": channel_id
        }
        
    except Exception as e:
        logger.error(f"Failed to initiate upload: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate upload: {str(e)}"
        )


@router.get("/upload/status/{upload_id}")
async def get_upload_status(
    upload_id: str,
    user = Depends(get_current_user)
):
    """
    Get status of an upload
    
    Args:
        upload_id: Upload session ID
        
    Returns:
        Upload status and progress
    """
    try:
        supabase = get_supabase_client()
        
        # Get upload record
        result = supabase.table("youtube_uploads").select("*").eq(
            "id", upload_id
        ).eq("user_id", user.id).single().execute()
        
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Upload not found"
            )
        
        upload = result.data
        
        return {
            "upload_id": upload_id,
            "status": upload["upload_status"],
            "progress": upload["upload_progress"],
            "video_id": upload.get("video_id"),
            "title": upload["title"],
            "channel_id": upload["channel_id"],
            "created_at": upload["created_at"],
            "completed_at": upload.get("completed_at"),
            "error": upload.get("error_message")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get upload status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get upload status"
        )


@router.post("/upload-thumbnail")
async def upload_thumbnail(
    request: Request,
    user = Depends(get_current_user)
):
    """
    Upload thumbnail for a video
    
    Request body:
        video_id: YouTube video ID
        reference_id: Thumbnail file reference ID
        channel_id: YouTube channel ID (for auth)
        
    Returns:
        Success status
    """
    try:
        body = await request.json()
        
        video_id = body.get("video_id")
        reference_id = body.get("reference_id")
        channel_id = body.get("channel_id")
        
        if not all([video_id, reference_id, channel_id]):
            raise HTTPException(
                status_code=400,
                detail="video_id, reference_id, and channel_id are required"
            )
        
        # Get dependencies
        supabase = get_supabase_client()
        channels_manager = YouTubeMCPChannels(supabase)
        file_manager = YouTubeFileManager(supabase)
        
        # Get valid access token
        access_token = await channels_manager.get_valid_access_token(
            channel_id,
            user.id
        )
        
        # Get thumbnail data
        thumbnail_data = await file_manager.get_file_data(user.id, reference_id)
        if not thumbnail_data:
            raise HTTPException(
                status_code=404,
                detail=f"Thumbnail reference not found: {reference_id}"
            )
        
        # Upload thumbnail
        from backend.youtube.client import YouTubeClient
        client = YouTubeClient(access_token)
        
        success = await client.upload_thumbnail(video_id, thumbnail_data)
        
        if success:
            return {
                "success": True,
                "message": f"Thumbnail uploaded for video {video_id}"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to upload thumbnail"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload thumbnail: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload thumbnail: {str(e)}"
        )


@router.get("/transcription-status/{reference_id}")
async def get_transcription_status(
    reference_id: str,
    user = Depends(get_current_user)
):
    """
    Get transcription status for a video reference
    
    Args:
        reference_id: Video file reference ID
        
    Returns:
        Transcription status and data
    """
    try:
        supabase = get_supabase_client()
        file_manager = YouTubeFileManager(supabase)
        
        # Get file reference
        reference = await file_manager.get_file_reference(user.id, reference_id)
        
        if not reference:
            raise HTTPException(
                status_code=404,
                detail="Reference not found"
            )
        
        has_transcription = bool(reference.transcription)
        has_metadata = bool(reference.generated_metadata)
        
        return {
            "reference_id": reference_id,
            "has_transcription": has_transcription,
            "has_generated_metadata": has_metadata,
            "transcription": reference.transcription,
            "generated_metadata": reference.generated_metadata,
            "status": "completed" if has_transcription else "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get transcription status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get transcription status"
        )


@router.get("/uploads")
async def list_uploads(
    status: Optional[str] = None,
    limit: int = 50,
    user = Depends(get_current_user)
):
    """
    List user's upload history
    
    Args:
        status: Filter by status (uploading, completed, failed, scheduled)
        limit: Maximum results
        
    Returns:
        List of uploads
    """
    try:
        supabase = get_supabase_client()
        
        query = supabase.table("youtube_uploads").select("*").eq(
            "user_id", user.id
        )
        
        if status:
            query = query.eq("upload_status", status)
        
        result = query.order("created_at", desc=True).limit(limit).execute()
        
        uploads = []
        for upload in result.data:
            uploads.append({
                "upload_id": upload["id"],
                "title": upload["title"],
                "channel_id": upload["channel_id"],
                "video_id": upload.get("video_id"),
                "status": upload["upload_status"],
                "progress": upload["upload_progress"],
                "file_size": format_bytes(upload["file_size"]),
                "created_at": upload["created_at"],
                "completed_at": upload.get("completed_at"),
                "scheduled_for": upload.get("scheduled_for")
            })
        
        return {
            "uploads": uploads,
            "count": len(uploads)
        }
        
    except Exception as e:
        logger.error(f"Failed to list uploads: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list uploads"
        )


@router.delete("/upload/{upload_id}")
async def cancel_upload(
    upload_id: str,
    user = Depends(get_current_user)
):
    """
    Cancel an ongoing upload
    
    Args:
        upload_id: Upload session ID
        
    Returns:
        Cancellation status
    """
    try:
        supabase = get_supabase_client()
        
        # Update upload status
        result = supabase.table("youtube_uploads").update({
            "upload_status": "cancelled",
            "status_message": "Upload cancelled by user"
        }).eq("id", upload_id).eq("user_id", user.id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Upload not found"
            )
        
        # TODO: Actually cancel the upload if in progress
        
        return {
            "success": True,
            "message": "Upload cancelled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel upload: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to cancel upload"
        )


# Background task for upload
async def _perform_upload(
    uploader: YouTubeStreamingUpload,
    file_data: bytes,
    metadata: Any,
    upload_id: str,
    supabase: Any
):
    """
    Perform the actual upload in background
    """
    try:
        # Progress callback
        def update_progress(progress: float, uploaded: int, total: int):
            try:
                supabase.table("youtube_uploads").update({
                    "upload_progress": progress,
                    "status_message": f"Uploaded {format_bytes(uploaded)} of {format_bytes(total)}"
                }).eq("id", upload_id).execute()
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")
        
        # Upload video
        video_id = await uploader.upload_video_from_bytes(
            file_data,
            metadata,
            session_id=upload_id,
            on_progress=update_progress
        )
        
        # Update upload record
        supabase.table("youtube_uploads").update({
            "video_id": video_id,
            "upload_status": "completed",
            "upload_progress": 100,
            "completed_at": datetime.utcnow().isoformat()
        }).eq("id", upload_id).execute()
        
        logger.info(f"Upload {upload_id} completed: video_id={video_id}")
        
    except Exception as e:
        logger.error(f"Upload {upload_id} failed: {e}")
        
        # Update upload record with error
        supabase.table("youtube_uploads").update({
            "upload_status": "failed",
            "error_message": str(e)
        }).eq("id", upload_id).execute()