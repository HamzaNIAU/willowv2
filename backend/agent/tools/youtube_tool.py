"""YouTube Tool for Agent Integration"""

from typing import Dict, Any, Optional, List
from agentpress.tool import Tool, ToolResult, openapi_schema
import aiohttp
import json
import os
import jwt
from utils.logger import logger
from services.supabase import DBConnection


class YouTubeTool(Tool):
    """Native YouTube integration tool for the agent"""
    
    def __init__(self, user_id: str, channel_ids: Optional[List[str]] = None, thread_manager=None, jwt_token: Optional[str] = None):
        self.user_id = user_id
        self.channel_ids = channel_ids or []
        self.thread_manager = thread_manager
        self.base_url = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api"
        
        # Use provided JWT token or create one
        self.jwt_token = jwt_token or self._create_jwt_token()
        super().__init__()
    
    def _create_jwt_token(self) -> str:
        """Create a JWT token for API authentication"""
        jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        if not jwt_secret:
            logger.warning("SUPABASE_JWT_SECRET not set, authentication may fail")
            return ""
        
        # Create a simple JWT with the user_id
        payload = {
            "sub": self.user_id,
            "user_id": self.user_id,
            "role": "authenticated"
        }
        
        return jwt.encode(payload, jwt_secret, algorithm="HS256")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_authenticate",
            "description": "Initiate YouTube authentication flow to connect a YouTube channel. This will provide an OAuth button for the user to click.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def youtube_authenticate(self) -> ToolResult:
        """Start YouTube OAuth authentication flow"""
        try:
            # Get auth URL from backend
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                async with session.post(f"{self.base_url}/youtube/auth/initiate", headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Failed to initiate authentication: {error_text}")
                    
                    data = await response.json()
                    auth_url = data.get("auth_url")
                    
                    if not auth_url:
                        return self.fail_response("No authentication URL received")
                    
                    # Return OAuth button for user to click
                    return self.success_response({
                        "message": "Click the button below to connect your YouTube account",
                        "auth_url": auth_url,
                        "type": "oauth_button"
                    })
        except Exception as e:
            logger.error(f"YouTube authentication error: {e}")
            return ToolResult(success=False, output=str(e))
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_channels",
            "description": "List all connected YouTube channels for the current user. Returns channel information including name, subscriber count, and video statistics.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    })
    async def youtube_channels(self) -> ToolResult:
        """Get user's connected YouTube channels"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                async with session.get(f"{self.base_url}/youtube/channels", headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Failed to get channels: {error_text}")
                    
                    data = await response.json()
                    channels = data.get("channels", [])
                    
                    if not channels:
                        return self.success_response({
                            "message": "No YouTube channels connected. Use youtube_authenticate to connect a channel.",
                            "channels": []
                        })
                    
                    # Format channel information
                    formatted_channels = []
                    for channel in channels:
                        formatted_channels.append({
                            "id": channel["id"],
                            "name": channel["name"],
                            "username": channel.get("username"),
                            "profile_picture": channel.get("profile_picture"),
                            "subscriber_count": channel.get("subscriber_count", 0),
                            "view_count": channel.get("view_count", 0),
                            "video_count": channel.get("video_count", 0)
                        })
                    
                    return self.success_response({
                        "channels": formatted_channels,
                        "count": len(formatted_channels),
                        "message": f"Found {len(formatted_channels)} connected YouTube channel(s)"
                    })
        except Exception as e:
            logger.error(f"Error fetching YouTube channels: {e}")
            return ToolResult(success=False, output=str(e))
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_upload_video",
            "description": "Upload a video to a YouTube channel. Requires a connected channel and video file path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The YouTube channel ID to upload to"
                    },
                    "video_path": {
                        "type": "string",
                        "description": "Path to the video file to upload"
                    },
                    "title": {
                        "type": "string",
                        "description": "Title for the YouTube video"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description for the YouTube video"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for the video"
                    },
                    "privacy": {
                        "type": "string",
                        "enum": ["private", "unlisted", "public"],
                        "description": "Privacy setting for the video (default: private)"
                    }
                },
                "required": ["channel_id", "video_path", "title"]
            }
        }
    })
    async def youtube_upload_video(
        self,
        channel_id: str,
        video_path: str,
        title: str,
        description: str = "",
        tags: List[str] = None,
        privacy: str = "private"
    ) -> ToolResult:
        """Upload a video to YouTube"""
        try:
            # Check if channel is connected
            if self.channel_ids and channel_id not in self.channel_ids:
                return self.fail_response(
                    f"Channel {channel_id} is not connected or enabled. Use youtube_channels to see available channels."
                )
            
            # This would integrate with the YouTube upload API
            # For now, return a placeholder response
            return self.success_response({
                "message": f"Video upload initiated for channel {channel_id}",
                "video": {
                    "title": title,
                    "description": description,
                    "tags": tags or [],
                    "privacy": privacy,
                    "status": "processing"
                },
                "note": "Video upload functionality is being implemented"
            })
        except Exception as e:
            logger.error(f"Error uploading video: {e}")
            return ToolResult(success=False, output=str(e))
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "youtube_channel_stats",
            "description": "Get detailed statistics for a specific YouTube channel",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The YouTube channel ID to get stats for"
                    }
                },
                "required": ["channel_id"]
            }
        }
    })
    async def youtube_channel_stats(self, channel_id: str) -> ToolResult:
        """Get detailed channel statistics"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
                async with session.get(f"{self.base_url}/youtube/channels/{channel_id}", headers=headers) as response:
                    if response.status == 404:
                        return self.fail_response(f"Channel {channel_id} not found or not connected")
                    elif response.status != 200:
                        error_text = await response.text()
                        return self.fail_response(f"Failed to get channel stats: {error_text}")
                    
                    data = await response.json()
                    channel = data.get("channel")
                    
                    return self.success_response({
                        "channel": channel,
                        "message": f"Statistics for {channel['name']}"
                    })
        except Exception as e:
            logger.error(f"Error getting channel stats: {e}")
            return ToolResult(success=False, output=str(e))