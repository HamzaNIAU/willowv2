import json
import asyncio
from typing import Dict, Any
from agentpress.tool import ToolResult
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp_module import mcp_service
from utils.logger import logger


class MCPToolExecutor:
    def __init__(self, custom_tools: Dict[str, Dict[str, Any]], tool_wrapper=None):
        self.mcp_manager = mcp_service
        self.custom_tools = custom_tools
        self.tool_wrapper = tool_wrapper
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        logger.info(f"Executing MCP tool {tool_name} with arguments {arguments}")

        try:
            if tool_name in self.custom_tools:
                return await self._execute_custom_tool(tool_name, arguments)
            else:
                return await self._execute_standard_tool(tool_name, arguments)
        except Exception as e:
            logger.error(f"Error executing MCP tool {tool_name}: {str(e)}")
            return self._create_error_result(f"Error executing tool: {str(e)}")
    
    async def _execute_standard_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        result = await self.mcp_manager.execute_tool(tool_name, arguments)
        if isinstance(result, dict):
            if result.get('isError', False):
                return self._create_error_result(result.get('content', 'Tool execution failed'))
            else:
                return self._create_success_result(result.get('content', result))
        else:
            return self._create_success_result(result)
    
    async def _execute_custom_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        tool_info = self.custom_tools[tool_name]
        custom_type = tool_info['custom_type']
        
        if custom_type == 'composio':
            custom_config = tool_info['custom_config']
            profile_id = custom_config.get('profile_id')
            
            if not profile_id:
                return self._create_error_result("Missing profile_id for Composio tool")
            
            try:
                from composio_integration.composio_profile_service import ComposioProfileService
                from services.supabase import DBConnection
                
                db = DBConnection()
                profile_service = ComposioProfileService(db)
                mcp_url = await profile_service.get_mcp_url_for_runtime(profile_id)
                modified_tool_info = tool_info.copy()
                modified_tool_info['custom_config'] = {
                    **custom_config,
                    'url': mcp_url
                }
                return await self._execute_http_tool(tool_name, arguments, modified_tool_info)
                
            except Exception as e:
                logger.error(f"Failed to resolve Composio profile {profile_id}: {str(e)}")
                return self._create_error_result(f"Failed to resolve Composio profile: {str(e)}")
                
        elif custom_type == 'pipedream':
            return await self._execute_pipedream_tool(tool_name, arguments, tool_info)
        elif custom_type == 'social-media':
            return await self._execute_social_media_tool(tool_name, arguments, tool_info)
        elif custom_type == 'sse':
            return await self._execute_sse_tool(tool_name, arguments, tool_info)
        elif custom_type == 'http':
            return await self._execute_http_tool(tool_name, arguments, tool_info)
        elif custom_type == 'json':
            return await self._execute_json_tool(tool_name, arguments, tool_info)
        else:
            return self._create_error_result(f"Unsupported custom MCP type: {custom_type}")
    
    async def _execute_social_media_tool(self, tool_name: str, arguments: Dict[str, Any], tool_info: Dict[str, Any]) -> ToolResult:
        """Execute social media tools (YouTube, etc.) using native integrations"""
        custom_config = tool_info['custom_config']
        platform = custom_config.get('platform', 'youtube')
        
        if platform == 'youtube':
            # Import YouTube tool
            from agent.tools.youtube_tool import YouTubeTool
            
            # Get user_id from tool_wrapper's config (passed during agent initialization)
            user_id = None
            if self.tool_wrapper and hasattr(self.tool_wrapper, 'mcp_configs'):
                for config in self.tool_wrapper.mcp_configs:
                    if config.get('customType') == 'social-media' and config.get('platform') == 'youtube':
                        user_id = config.get('config', {}).get('user_id')
                        break
            
            if not user_id:
                # Try to get from custom_config
                user_id = custom_config.get('user_id')
            
            if not user_id:
                return self._create_error_result("Missing user_id for YouTube tool")
            
            # Extract channel IDs from all YouTube MCPs
            channel_ids = []
            if self.tool_wrapper and hasattr(self.tool_wrapper, 'mcp_configs'):
                for config in self.tool_wrapper.mcp_configs:
                    if config.get('customType') == 'social-media' and config.get('platform') == 'youtube':
                        qualified_name = config.get('qualifiedName', '')
                        if qualified_name.startswith('social.youtube.'):
                            channel_id = qualified_name.replace('social.youtube.', '')
                            if channel_id:
                                channel_ids.append(channel_id)
            
            try:
                # Create YouTube tool instance
                youtube_tool = YouTubeTool(user_id=user_id, channel_ids=channel_ids)
                
                # Map tool names to methods
                if tool_name == 'youtube_authenticate':
                    result = await youtube_tool.youtube_authenticate()
                elif tool_name == 'youtube_channels':
                    result = await youtube_tool.youtube_channels()
                elif tool_name == 'youtube_upload_video':
                    result = await youtube_tool.youtube_upload_video(
                        title=arguments.get('title'),
                        description=arguments.get('description', ''),
                        file_path=arguments.get('file_path'),
                        channel_id=arguments.get('channel_id'),
                        tags=arguments.get('tags', []),
                        privacy=arguments.get('privacy', 'private')
                    )
                elif tool_name == 'youtube_channel_stats':
                    result = await youtube_tool.youtube_channel_stats(
                        channel_ids=arguments.get('channel_ids', channel_ids)
                    )
                else:
                    return self._create_error_result(f"Unknown YouTube tool: {tool_name}")
                
                return result
                
            except Exception as e:
                logger.error(f"Error executing YouTube tool {tool_name}: {str(e)}")
                return self._create_error_result(f"Error executing YouTube tool: {str(e)}")
        else:
            return self._create_error_result(f"Unsupported social media platform: {platform}")
    
    async def _execute_pipedream_tool(self, tool_name: str, arguments: Dict[str, Any], tool_info: Dict[str, Any]) -> ToolResult:
        custom_config = tool_info['custom_config']
        original_tool_name = tool_info['original_name']
        
        external_user_id = await self._resolve_external_user_id(custom_config)
        if not external_user_id:
            return self._create_error_result("No external_user_id available")
        
        app_slug = custom_config.get('app_slug')
        oauth_app_id = custom_config.get('oauth_app_id')
        
        try:
            import os
            from pipedream import connection_service
            
            access_token = await connection_service._ensure_access_token()
            
            project_id = os.getenv("PIPEDREAM_PROJECT_ID")
            environment = os.getenv("PIPEDREAM_X_PD_ENVIRONMENT", "development")
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "x-pd-project-id": project_id,
                "x-pd-environment": environment,
                "x-pd-external-user-id": external_user_id,
                "x-pd-app-slug": app_slug,
            }
            
            if hasattr(connection_service, 'rate_limit_token') and connection_service.rate_limit_token:
                headers["x-pd-rate-limit"] = connection_service.rate_limit_token
            
            if oauth_app_id:
                headers["x-pd-oauth-app-id"] = oauth_app_id
            
            url = "https://remote.mcp.pipedream.net"
            
            async with asyncio.timeout(30):
                async with streamablehttp_client(url, headers=headers) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.call_tool(original_tool_name, arguments)
                        return self._create_success_result(self._extract_content(result))
                        
        except Exception as e:
            logger.error(f"Error executing Pipedream MCP tool: {str(e)}")
            return self._create_error_result(f"Error executing Pipedream tool: {str(e)}")
    
    async def _execute_sse_tool(self, tool_name: str, arguments: Dict[str, Any], tool_info: Dict[str, Any]) -> ToolResult:
        custom_config = tool_info['custom_config']
        original_tool_name = tool_info['original_name']
        
        url = custom_config['url']
        headers = custom_config.get('headers', {})
        
        async with asyncio.timeout(30):
            try:
                async with sse_client(url, headers=headers) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(original_tool_name, arguments)
                        return self._create_success_result(self._extract_content(result))
                        
            except TypeError as e:
                if "unexpected keyword argument" in str(e):
                    async with sse_client(url) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            result = await session.call_tool(original_tool_name, arguments)
                            return self._create_success_result(self._extract_content(result))
                else:
                    raise
    
    async def _execute_http_tool(self, tool_name: str, arguments: Dict[str, Any], tool_info: Dict[str, Any]) -> ToolResult:
        custom_config = tool_info['custom_config']
        original_tool_name = tool_info['original_name']
        
        url = custom_config['url']
        
        try:
            async with asyncio.timeout(30):
                async with streamablehttp_client(url) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(original_tool_name, arguments)
                        return self._create_success_result(self._extract_content(result))
                        
        except Exception as e:
            logger.error(f"Error executing HTTP MCP tool: {str(e)}")
            return self._create_error_result(f"Error executing HTTP tool: {str(e)}")
    
    async def _execute_json_tool(self, tool_name: str, arguments: Dict[str, Any], tool_info: Dict[str, Any]) -> ToolResult:
        custom_config = tool_info['custom_config']
        original_tool_name = tool_info['original_name']
        
        server_params = StdioServerParameters(
            command=custom_config["command"],
            args=custom_config.get("args", []),
            env=custom_config.get("env", {})
        )
        
        async with asyncio.timeout(30):
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(original_tool_name, arguments)
                    return self._create_success_result(self._extract_content(result))
    
    async def _resolve_external_user_id(self, custom_config: Dict[str, Any]) -> str:
        profile_id = custom_config.get('profile_id')
        external_user_id = custom_config.get('external_user_id')
        
        if not profile_id:
            return external_user_id
        
        try:
            from services.supabase import DBConnection
            from utils.encryption import decrypt_data
            
            db = DBConnection()
            supabase = await db.client
            
            result = await supabase.table('user_mcp_credential_profiles').select(
                'encrypted_config'
            ).eq('profile_id', profile_id).single().execute()
            
            if result.data:
                decrypted_config = decrypt_data(result.data['encrypted_config'])
                config_data = json.loads(decrypted_config)
                return config_data.get('external_user_id', external_user_id)
            
        except Exception as e:
            logger.error(f"Failed to resolve profile {profile_id}: {str(e)}")
        
        return external_user_id
    
    def _extract_content(self, result) -> str:
        if hasattr(result, 'content'):
            content = result.content
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if hasattr(item, 'text'):
                        text_parts.append(item.text)
                    else:
                        text_parts.append(str(item))
                return "\n".join(text_parts)
            elif hasattr(content, 'text'):
                return content.text
            else:
                return str(content)
        else:
            return str(result)
    
    def _create_success_result(self, content: Any) -> ToolResult:
        if self.tool_wrapper and hasattr(self.tool_wrapper, 'success_response'):
            return self.tool_wrapper.success_response(content)
        return ToolResult(
            success=True,
            content=str(content),
            metadata={}
        )
    
    def _create_error_result(self, error_message: str) -> ToolResult:
        if self.tool_wrapper and hasattr(self.tool_wrapper, 'fail_response'):
            return self.tool_wrapper.fail_response(error_message)
        return ToolResult(
            success=False,
            content=error_message,
            metadata={}
        ) 