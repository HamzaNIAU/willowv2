"""
YouTube Channels Tool for LiteLLM
Lists user's YouTube channels
"""

import logging
from typing import Dict, Any, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ChannelsParams(BaseModel):
    """Parameters for listing YouTube channels"""
    pass  # No parameters needed


class ChannelsTool:
    """
    YouTube channels listing tool for LiteLLM
    Returns list of authenticated user's YouTube channels
    """
    
    name = "youtube_channels"
    description = "List all YouTube channels available for upload"
    
    def __init__(self, channels_manager: Any):
        """
        Initialize channels tool
        
        Args:
            channels_manager: YouTube channels manager
        """
        self.channels = channels_manager
    
    async def execute(self, params: ChannelsParams, user_id: str) -> Dict[str, Any]:
        """
        Execute the channels listing
        
        Args:
            params: Tool parameters (none required)
            user_id: User identifier
            
        Returns:
            List of channels or error
        """
        try:
            # Get user's channels
            channels_list = await self.channels.get_channels_list(user_id)
            
            if not channels_list:
                return {
                    "type": "info",
                    "channels": [],
                    "message": "No YouTube channels connected. Use the authenticate tool to connect a channel."
                }
            
            # Format channels for display
            formatted_channels = []
            for channel in channels_list:
                channel_data = {
                    "id": channel.id,
                    "name": channel.name,
                    "custom_url": channel.custom_url,
                    "thumbnail_url": channel.thumbnail_url,
                    "statistics": {
                        "subscribers": self._format_count(channel.subscriber_count),
                        "views": self._format_count(channel.view_count),
                        "videos": self._format_count(channel.video_count)
                    },
                    "capabilities": channel.capabilities
                }
                formatted_channels.append(channel_data)
            
            return {
                "type": "youtube-channels",
                "channels": formatted_channels,
                "count": len(formatted_channels),
                "message": f"Found {len(formatted_channels)} YouTube channel{'s' if len(formatted_channels) != 1 else ''}"
            }
            
        except Exception as e:
            logger.error(f"Failed to list channels: {e}")
            return {
                "type": "error",
                "error": "channels_failed",
                "message": f"Failed to list YouTube channels: {str(e)}"
            }
    
    @staticmethod
    def _format_count(count: int) -> str:
        """Format large numbers with K/M/B suffixes"""
        if count >= 1_000_000_000:
            return f"{count / 1_000_000_000:.1f}B"
        elif count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        elif count >= 1_000:
            return f"{count / 1_000:.1f}K"
        return str(count)
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for this tool"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }


# For convenience, also create a channels_enabled tool
class ChannelsEnabledTool:
    """
    Check if YouTube channels are available
    """
    
    name = "youtube_channels_enabled"
    description = "Check if user has YouTube channels connected"
    
    def __init__(self, channels_manager: Any):
        """
        Initialize channels enabled tool
        
        Args:
            channels_manager: YouTube channels manager
        """
        self.channels = channels_manager
    
    async def execute(self, params: ChannelsParams, user_id: str) -> Dict[str, Any]:
        """
        Check if channels are enabled
        
        Args:
            params: Tool parameters (none required)
            user_id: User identifier
            
        Returns:
            Status of channel availability
        """
        try:
            channels_list = await self.channels.get_channels_list(user_id)
            
            has_channels = len(channels_list) > 0
            
            return {
                "type": "youtube-channels-status",
                "enabled": has_channels,
                "channel_count": len(channels_list),
                "message": "YouTube channels are connected" if has_channels else "No YouTube channels connected"
            }
            
        except Exception as e:
            logger.error(f"Failed to check channels: {e}")
            return {
                "type": "error",
                "enabled": False,
                "error": str(e)
            }
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for this tool"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }