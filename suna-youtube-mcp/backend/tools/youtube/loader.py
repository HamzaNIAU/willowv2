"""
YouTube Tools Loader for LiteLLM
Dynamically loads YouTube tools based on user's connection status
"""

import logging
from typing import Dict, Any, List

from .authenticate import AuthenticateTool
from .upload_video import UploadVideoTool
from .channels import ChannelsTool, ChannelsEnabledTool

logger = logging.getLogger(__name__)


class YouTubeToolsLoader:
    """
    Manages YouTube tools for LiteLLM integration
    """
    
    def __init__(self, supabase_client: Any, channels_manager: Any, file_manager: Any):
        """
        Initialize tools loader with dependencies
        
        Args:
            supabase_client: Supabase client
            channels_manager: YouTube channels manager
            file_manager: YouTube file manager
        """
        self.supabase = supabase_client
        self.channels_manager = channels_manager
        self.file_manager = file_manager
        
        # Initialize tools
        self.authenticate_tool = AuthenticateTool()
        self.upload_video_tool = UploadVideoTool(
            supabase_client,
            channels_manager,
            file_manager
        )
        self.channels_tool = ChannelsTool(channels_manager)
        self.channels_enabled_tool = ChannelsEnabledTool(channels_manager)
    
    async def load_tools_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Load YouTube tools for a specific user
        
        Args:
            user_id: User identifier
            
        Returns:
            List of tool schemas for LiteLLM
        """
        # Check if user has YouTube channels connected
        try:
            channels = await self.channels_manager.get_channels_list(user_id)
            has_channels = len(channels) > 0
        except Exception as e:
            logger.error(f"Failed to check user channels: {e}")
            has_channels = False
        
        tools = []
        
        # Always include authentication tool
        tools.append(self._create_tool_wrapper(
            self.authenticate_tool,
            "mcp_youtube_uploader_youtube_authenticate"
        ))
        
        # Include channels status check
        tools.append(self._create_tool_wrapper(
            self.channels_enabled_tool,
            "mcp_youtube_uploader_youtube_channels_enabled"
        ))
        
        # If user has channels, include all tools
        if has_channels:
            tools.extend([
                self._create_tool_wrapper(
                    self.channels_tool,
                    "mcp_youtube_uploader_youtube_channels"
                ),
                self._create_tool_wrapper(
                    self.upload_video_tool,
                    "mcp_youtube_uploader_youtube_upload_video"
                )
            ])
        
        logger.info(f"Loaded {len(tools)} YouTube tools for user {user_id}")
        return tools
    
    def _create_tool_wrapper(self, tool: Any, name: str) -> Dict[str, Any]:
        """
        Create a tool wrapper for LiteLLM
        
        Args:
            tool: Tool instance
            name: Tool name for LiteLLM
            
        Returns:
            Tool wrapper dictionary
        """
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": tool.description,
                "parameters": tool.get_schema()["parameters"]
            }
        }
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute a YouTube tool
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            user_id: User identifier
            
        Returns:
            Tool execution result
        """
        # Map tool names to tool instances
        tool_map = {
            "mcp_youtube_uploader_youtube_authenticate": self.authenticate_tool,
            "mcp_youtube_uploader_youtube_channels": self.channels_tool,
            "mcp_youtube_uploader_youtube_channels_enabled": self.channels_enabled_tool,
            "mcp_youtube_uploader_youtube_upload_video": self.upload_video_tool
        }
        
        tool = tool_map.get(tool_name)
        if not tool:
            return {
                "type": "error",
                "error": "tool_not_found",
                "message": f"YouTube tool '{tool_name}' not found"
            }
        
        # Create params object based on tool type
        if tool == self.authenticate_tool:
            from .authenticate import AuthenticateParams
            params = AuthenticateParams(**parameters)
            return await tool.execute(params)
        elif tool == self.upload_video_tool:
            from .upload_video import UploadVideoParams
            params = UploadVideoParams(**parameters)
            return await tool.execute(params, user_id)
        elif tool in [self.channels_tool, self.channels_enabled_tool]:
            from .channels import ChannelsParams
            params = ChannelsParams(**parameters)
            return await tool.execute(params, user_id)
        else:
            return {
                "type": "error",
                "error": "execution_failed",
                "message": f"Failed to execute tool '{tool_name}'"
            }
    
    def get_all_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get schemas for all YouTube tools
        
        Returns:
            List of all tool schemas
        """
        return [
            self.authenticate_tool.get_schema(),
            self.channels_tool.get_schema(),
            self.channels_enabled_tool.get_schema(),
            self.upload_video_tool.get_schema()
        ]


# Singleton instance
_loader_instance = None


def get_youtube_tools_loader(supabase_client: Any, channels_manager: Any, file_manager: Any) -> YouTubeToolsLoader:
    """
    Get or create YouTube tools loader instance
    
    Args:
        supabase_client: Supabase client
        channels_manager: YouTube channels manager
        file_manager: YouTube file manager
        
    Returns:
        YouTubeToolsLoader instance
    """
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = YouTubeToolsLoader(
            supabase_client,
            channels_manager,
            file_manager
        )
    return _loader_instance