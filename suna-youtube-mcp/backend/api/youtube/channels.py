"""
YouTube Channel API Routes for FastAPI
Handles channel listing, management, and updates
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
import logging

from backend.auth import get_current_user
from backend.database import get_supabase_client
from backend.youtube.channels import YouTubeMCPChannels
from backend.youtube.client import YouTubeClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/youtube/channels", tags=["YouTube Channels"])


@router.get("")
async def list_channels(
    user = Depends(get_current_user)
):
    """
    List all YouTube channels for the authenticated user
    
    Returns:
        List of connected YouTube channels
    """
    try:
        supabase = get_supabase_client()
        channels_manager = YouTubeMCPChannels(supabase)
        
        # Get user's channels
        channels = await channels_manager.get_channels_list(user.id)
        
        if not channels:
            return {
                "channels": [],
                "count": 0,
                "message": "No YouTube channels connected. Use the authenticate endpoint to connect a channel."
            }
        
        # Format channels for response
        formatted_channels = []
        for channel in channels:
            channel_data = {
                "id": channel.id,
                "name": channel.name,
                "custom_url": channel.custom_url,
                "thumbnail_url": channel.thumbnail_url,
                "statistics": {
                    "subscribers": channel.subscriber_count,
                    "views": channel.view_count,
                    "videos": channel.video_count,
                    "formatted": {
                        "subscribers": _format_count(channel.subscriber_count),
                        "views": _format_count(channel.view_count),
                        "videos": str(channel.video_count)
                    }
                },
                "capabilities": channel.capabilities,
                "has_token": channel.has_token
            }
            formatted_channels.append(channel_data)
        
        return {
            "channels": formatted_channels,
            "count": len(formatted_channels),
            "message": f"Found {len(formatted_channels)} YouTube channel{'s' if len(formatted_channels) != 1 else ''}"
        }
        
    except Exception as e:
        logger.error(f"Failed to list channels: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list channels: {str(e)}"
        )


@router.get("/{channel_id}")
async def get_channel(
    channel_id: str,
    user = Depends(get_current_user)
):
    """
    Get details for a specific YouTube channel
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        Channel details
    """
    try:
        supabase = get_supabase_client()
        channels_manager = YouTubeMCPChannels(supabase)
        
        # Get channel
        channel = await channels_manager.get_channel_by_id(channel_id, user.id)
        
        # Mask sensitive data
        masked_channel = channels_manager.mask_channel(channel)
        
        return {
            "channel": {
                "id": masked_channel.id,
                "name": masked_channel.name,
                "custom_url": masked_channel.custom_url,
                "thumbnail_url": masked_channel.thumbnail_url,
                "statistics": {
                    "subscribers": masked_channel.subscriber_count,
                    "views": masked_channel.view_count,
                    "videos": masked_channel.video_count,
                    "formatted": {
                        "subscribers": _format_count(masked_channel.subscriber_count),
                        "views": _format_count(masked_channel.view_count),
                        "videos": str(masked_channel.video_count)
                    }
                },
                "capabilities": masked_channel.capabilities,
                "has_token": masked_channel.has_token
            }
        }
        
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get channel: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get channel: {str(e)}"
        )


@router.post("/{channel_id}/refresh")
async def refresh_channel_data(
    channel_id: str,
    user = Depends(get_current_user)
):
    """
    Refresh channel data from YouTube API
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        Updated channel data
    """
    try:
        supabase = get_supabase_client()
        channels_manager = YouTubeMCPChannels(supabase)
        
        # Get channel with token
        channel = await channels_manager.get_channel_by_id(channel_id, user.id)
        
        # Get valid access token
        access_token = await channels_manager.get_valid_access_token(
            channel_id,
            user.id
        )
        
        # Fetch fresh data from YouTube
        client = YouTubeClient(access_token)
        youtube_channels = await client.get_my_channels()
        
        if not youtube_channels:
            raise HTTPException(
                status_code=404,
                detail="Channel not found on YouTube"
            )
        
        # Find matching channel
        youtube_channel = None
        for ch in youtube_channels:
            if ch.id == channel_id:
                youtube_channel = ch
                break
        
        if not youtube_channel:
            raise HTTPException(
                status_code=404,
                detail=f"Channel {channel_id} not found in user's YouTube account"
            )
        
        # Update channel data
        channel.name = youtube_channel.name
        channel.custom_url = youtube_channel.custom_url
        channel.thumbnail_url = youtube_channel.thumbnail_url
        channel.subscriber_count = youtube_channel.subscriber_count
        channel.view_count = youtube_channel.view_count
        channel.video_count = youtube_channel.video_count
        
        # Save updated channel
        await channels_manager.save_channel(channel)
        
        # Return masked channel
        masked_channel = channels_manager.mask_channel(channel)
        
        return {
            "channel": {
                "id": masked_channel.id,
                "name": masked_channel.name,
                "custom_url": masked_channel.custom_url,
                "thumbnail_url": masked_channel.thumbnail_url,
                "statistics": {
                    "subscribers": masked_channel.subscriber_count,
                    "views": masked_channel.view_count,
                    "videos": masked_channel.video_count,
                    "formatted": {
                        "subscribers": _format_count(masked_channel.subscriber_count),
                        "views": _format_count(masked_channel.view_count),
                        "videos": str(masked_channel.video_count)
                    }
                },
                "updated": True
            },
            "message": "Channel data refreshed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh channel: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh channel: {str(e)}"
        )


@router.delete("/{channel_id}")
async def disconnect_channel(
    channel_id: str,
    user = Depends(get_current_user)
):
    """
    Disconnect a YouTube channel
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        Disconnection status
    """
    try:
        supabase = get_supabase_client()
        channels_manager = YouTubeMCPChannels(supabase)
        
        # Delete channel
        success = await channels_manager.delete_channel(channel_id, user.id)
        
        if success:
            return {
                "success": True,
                "message": f"Channel {channel_id} disconnected successfully"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to disconnect channel"
            )
        
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disconnect channel: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect channel: {str(e)}"
        )


@router.get("/{channel_id}/videos")
async def list_channel_videos(
    channel_id: str,
    max_results: int = 10,
    page_token: Optional[str] = None,
    user = Depends(get_current_user)
):
    """
    List videos for a channel
    
    Args:
        channel_id: YouTube channel ID
        max_results: Maximum results per page
        page_token: Pagination token
        
    Returns:
        List of videos
    """
    try:
        supabase = get_supabase_client()
        channels_manager = YouTubeMCPChannels(supabase)
        
        # Get valid access token
        access_token = await channels_manager.get_valid_access_token(
            channel_id,
            user.id
        )
        
        # Get videos from YouTube
        # This would require implementing a method in YouTubeClient
        # For now, return empty list
        
        return {
            "videos": [],
            "next_page_token": None,
            "message": "Video listing not yet implemented"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list videos: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list videos: {str(e)}"
        )


@router.post("/check-connection")
async def check_connection(
    user = Depends(get_current_user)
):
    """
    Check if user has any YouTube channels connected
    
    Returns:
        Connection status
    """
    try:
        supabase = get_supabase_client()
        channels_manager = YouTubeMCPChannels(supabase)
        
        channels = await channels_manager.get_channels_list(user.id)
        has_channels = len(channels) > 0
        
        return {
            "connected": has_channels,
            "channel_count": len(channels),
            "channels": [
                {
                    "id": ch.id,
                    "name": ch.name
                }
                for ch in channels
            ] if has_channels else []
        }
        
    except Exception as e:
        logger.error(f"Failed to check connection: {e}")
        return {
            "connected": False,
            "channel_count": 0,
            "channels": [],
            "error": str(e)
        }


# Helper function
def _format_count(count: int) -> str:
    """Format large numbers with K/M/B suffixes"""
    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.1f}B"
    elif count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)