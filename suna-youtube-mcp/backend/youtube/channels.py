"""
YouTube Channel Management for Suna
Handles channel storage, retrieval, and token management
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel
import json

from .oauth import YouTubeMCPOAuth, YouTubeToken
from .client import YouTubeClient, YouTubeChannel

logger = logging.getLogger(__name__)


class MCPChannel(BaseModel):
    """YouTube channel with authentication information"""
    id: str
    name: str
    custom_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    subscriber_count: int = 0
    view_count: int = 0
    video_count: int = 0
    token: YouTubeToken
    user_id: str
    created_at: datetime = None
    updated_at: datetime = None
    
    def __init__(self, **data):
        if 'created_at' not in data or data['created_at'] is None:
            data['created_at'] = datetime.utcnow()
        if 'updated_at' not in data or data['updated_at'] is None:
            data['updated_at'] = datetime.utcnow()
        super().__init__(**data)


class MCPChannelMasked(BaseModel):
    """YouTube channel with masked tokens for display"""
    id: str
    name: str
    custom_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    subscriber_count: int = 0
    view_count: int = 0
    video_count: int = 0
    has_token: bool = False
    capabilities: Dict[str, bool] = {}


class YouTubeMCPChannels:
    """
    YouTube channel manager for Suna
    Handles channel CRUD operations and token management
    """
    
    def __init__(self, supabase_client: Any):
        """
        Initialize channel manager with Supabase client
        
        Args:
            supabase_client: Initialized Supabase client
        """
        self.supabase = supabase_client
        self.oauth_handler = YouTubeMCPOAuth()
        self._channels_cache: Dict[str, Dict[str, MCPChannel]] = {}
    
    async def get_channel_for_token(
        self,
        token: YouTubeToken,
        user_id: str
    ) -> MCPChannel:
        """
        Get channel information for a given token
        
        Args:
            token: YouTube OAuth token
            user_id: User identifier
            
        Returns:
            MCPChannel with channel information
            
        Raises:
            ValueError: If no channels found for token
        """
        # Create YouTube client and fetch channel info
        client = YouTubeClient(token.access_token)
        channels = await client.get_my_channels()
        
        if not channels:
            raise ValueError("No channels found for this YouTube account")
        
        # Use the first channel (primary channel)
        channel_data = channels[0]
        
        # Create MCPChannel object
        mcp_channel = MCPChannel(
            id=channel_data.id,
            name=channel_data.name,
            custom_url=channel_data.custom_url,
            thumbnail_url=channel_data.thumbnail_url,
            subscriber_count=channel_data.subscriber_count,
            view_count=channel_data.view_count,
            video_count=channel_data.video_count,
            token=token,
            user_id=user_id
        )
        
        return mcp_channel
    
    async def save_channel(self, channel: MCPChannel) -> MCPChannel:
        """
        Save or update a channel in the database
        
        Args:
            channel: MCPChannel to save
            
        Returns:
            Saved MCPChannel
            
        Raises:
            ValueError: If save operation fails
        """
        if not channel or not channel.token:
            raise ValueError("Invalid channel: channel or token is missing")
        
        channel.updated_at = datetime.utcnow()
        
        # Prepare data for Supabase
        channel_data = {
            "id": channel.id,
            "user_id": channel.user_id,
            "name": channel.name,
            "custom_url": channel.custom_url,
            "thumbnail_url": channel.thumbnail_url,
            "subscriber_count": channel.subscriber_count,
            "view_count": channel.view_count,
            "video_count": channel.video_count,
            "token_data": json.dumps({
                "access_token": channel.token.access_token,
                "refresh_token": channel.token.refresh_token,
                "token_type": channel.token.token_type,
                "expiry": channel.token.expiry.isoformat(),
                "scopes": channel.token.scopes
            }),
            "updated_at": channel.updated_at.isoformat()
        }
        
        try:
            # Upsert channel data
            result = self.supabase.table("youtube_channels").upsert(
                channel_data,
                on_conflict="id,user_id"
            ).execute()
            
            # Update cache
            if channel.user_id not in self._channels_cache:
                self._channels_cache[channel.user_id] = {}
            self._channels_cache[channel.user_id][channel.id] = channel
            
            logger.info(f"Saved YouTube channel {channel.id} for user {channel.user_id}")
            return channel
            
        except Exception as e:
            logger.error(f"Failed to save channel: {e}")
            raise ValueError(f"Failed to save channel: {str(e)}")
    
    async def get_user_channels(
        self,
        user_id: str,
        use_cache: bool = True
    ) -> Dict[str, MCPChannel]:
        """
        Get all channels for a user
        
        Args:
            user_id: User identifier
            use_cache: Whether to use cached data
            
        Returns:
            Dictionary of channel ID to MCPChannel
        """
        # Check cache first
        if use_cache and user_id in self._channels_cache:
            return self._channels_cache[user_id]
        
        try:
            # Fetch from database
            result = self.supabase.table("youtube_channels").select("*").eq(
                "user_id", user_id
            ).execute()
            
            channels = {}
            for row in result.data:
                # Parse token data
                token_data = json.loads(row["token_data"])
                token = YouTubeToken(
                    access_token=token_data["access_token"],
                    refresh_token=token_data["refresh_token"],
                    token_type=token_data.get("token_type", "Bearer"),
                    expiry=datetime.fromisoformat(token_data["expiry"]),
                    scopes=token_data.get("scopes", [])
                )
                
                # Create MCPChannel object
                channel = MCPChannel(
                    id=row["id"],
                    name=row["name"],
                    custom_url=row.get("custom_url"),
                    thumbnail_url=row.get("thumbnail_url"),
                    subscriber_count=row.get("subscriber_count", 0),
                    view_count=row.get("view_count", 0),
                    video_count=row.get("video_count", 0),
                    token=token,
                    user_id=user_id,
                    created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                    updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None
                )
                
                channels[channel.id] = channel
            
            # Update cache
            self._channels_cache[user_id] = channels
            
            return channels
            
        except Exception as e:
            logger.error(f"Failed to fetch channels for user {user_id}: {e}")
            return {}
    
    async def get_channel_by_id(
        self,
        channel_id: str,
        user_id: str
    ) -> MCPChannel:
        """
        Get a specific channel by ID
        
        Args:
            channel_id: YouTube channel ID
            user_id: User identifier
            
        Returns:
            MCPChannel object
            
        Raises:
            ValueError: If channel not found
        """
        if not channel_id:
            raise ValueError("Channel ID must be provided")
        
        channels = await self.get_user_channels(user_id)
        
        if channel_id not in channels:
            raise ValueError(f"Channel with ID {channel_id} not found for user")
        
        return channels[channel_id]
    
    async def get_valid_access_token(
        self,
        channel_id: str,
        user_id: str
    ) -> str:
        """
        Get a valid access token for a channel, refreshing if necessary
        
        Args:
            channel_id: YouTube channel ID
            user_id: User identifier
            
        Returns:
            Valid access token string
            
        Raises:
            ValueError: If token cannot be obtained
        """
        channel = await self.get_channel_by_id(channel_id, user_id)
        
        if not channel.token or not channel.token.access_token:
            raise ValueError("No access token available for this channel")
        
        # Check if token needs refresh
        if self.oauth_handler.is_token_expired(channel.token):
            if not channel.token.refresh_token:
                raise ValueError("Token is expired and no refresh token available")
            
            logger.info(f"Refreshing token for channel {channel_id}")
            
            try:
                # Refresh the token
                new_token = await self.oauth_handler.refresh_access_token(
                    channel.token.refresh_token
                )
                
                # Update channel with new token
                channel.token = new_token
                await self.save_channel(channel)
                
                return new_token.access_token
                
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                raise ValueError(f"Failed to refresh access token: {str(e)}")
        
        return channel.token.access_token
    
    async def delete_channel(
        self,
        channel_id: str,
        user_id: str
    ) -> bool:
        """
        Delete a channel from storage
        
        Args:
            channel_id: YouTube channel ID
            user_id: User identifier
            
        Returns:
            True if successful
            
        Raises:
            ValueError: If deletion fails
        """
        try:
            # Delete from database
            result = self.supabase.table("youtube_channels").delete().eq(
                "id", channel_id
            ).eq("user_id", user_id).execute()
            
            # Remove from cache
            if user_id in self._channels_cache and channel_id in self._channels_cache[user_id]:
                del self._channels_cache[user_id][channel_id]
            
            logger.info(f"Deleted YouTube channel {channel_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete channel: {e}")
            raise ValueError(f"Failed to delete channel: {str(e)}")
    
    @staticmethod
    def mask_channel(channel: MCPChannel) -> MCPChannelMasked:
        """
        Create a masked version of a channel for display
        
        Args:
            channel: MCPChannel to mask
            
        Returns:
            MCPChannelMasked with sensitive data removed
        """
        capabilities = {}
        if channel.token and channel.token.scopes:
            capabilities = YouTubeMCPOAuth.get_capabilities_from_scopes(
                channel.token.scopes
            )
        
        return MCPChannelMasked(
            id=channel.id,
            name=channel.name,
            custom_url=channel.custom_url,
            thumbnail_url=channel.thumbnail_url,
            subscriber_count=channel.subscriber_count,
            view_count=channel.view_count,
            video_count=channel.video_count,
            has_token=bool(channel.token),
            capabilities=capabilities
        )
    
    async def get_channels_list(
        self,
        user_id: str
    ) -> List[MCPChannelMasked]:
        """
        Get list of masked channels for display
        
        Args:
            user_id: User identifier
            
        Returns:
            List of MCPChannelMasked objects
        """
        channels = await self.get_user_channels(user_id)
        
        masked_channels = []
        for channel in channels.values():
            masked_channels.append(self.mask_channel(channel))
        
        return masked_channels