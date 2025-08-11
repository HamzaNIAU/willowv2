import os
import json
import asyncio
from typing import Optional, Dict, List, Any, AsyncGenerator
from dataclasses import dataclass

from agent.tools.message_tool import MessageTool
from agent.tools.sb_deploy_tool import SandboxDeployTool
from agent.tools.sb_expose_tool import SandboxExposeTool
from agent.tools.web_search_tool import SandboxWebSearchTool
from dotenv import load_dotenv
from utils.config import config
from flags.flags import is_enabled
from agent.agent_builder_prompt import get_agent_builder_prompt
from agentpress.thread_manager import ThreadManager
from agentpress.response_processor import ProcessorConfig
from agent.tools.sb_shell_tool import SandboxShellTool
from agent.tools.sb_files_tool import SandboxFilesTool
from agent.tools.sb_browser_tool import SandboxBrowserTool
from agent.tools.data_providers_tool import DataProvidersTool
from agent.tools.expand_msg_tool import ExpandMessageTool
from agent.prompt import get_system_prompt
from agent.custom_prompt import render_prompt_template
from utils.logger import logger
from utils.auth_utils import get_account_id_from_thread
from services.billing import check_billing_status
from utils.session_manager import SessionManager
from agent.tools.sb_vision_tool import SandboxVisionTool
from agent.tools.sb_image_edit_tool import SandboxImageEditTool
from agent.tools.youtube_tool import YouTubeTool
from services.langfuse import langfuse
from langfuse.client import StatefulTraceClient
from agent.gemini_prompt import get_gemini_system_prompt
from agent.tools.mcp_tool_wrapper import MCPToolWrapper
from agent.tools.task_list_tool import TaskListTool
from agentpress.tool import SchemaType

load_dotenv()


@dataclass
class AgentConfig:
    thread_id: str
    project_id: str
    stream: bool
    native_max_auto_continues: int = 25
    max_iterations: int = 100
    model_name: str = "anthropic/claude-sonnet-4-20250514"
    enable_thinking: Optional[bool] = False
    reasoning_effort: Optional[str] = 'low'
    enable_context_manager: bool = True
    agent_config: Optional[dict] = None
    trace: Optional[StatefulTraceClient] = None
    is_agent_builder: Optional[bool] = False
    target_agent_id: Optional[str] = None
    session_id: Optional[str] = None  # Changed from jwt_token to session_id


class ToolManager:
    def __init__(self, thread_manager: ThreadManager, project_id: str, thread_id: str, user_id: Optional[str] = None, youtube_channels: Optional[List[str]] = None, session_id: Optional[str] = None, jwt_token: Optional[str] = None):
        self.thread_manager = thread_manager
        self.project_id = project_id
        self.thread_id = thread_id
        self.user_id = user_id
        self.youtube_channels = youtube_channels or []
        self.session_id = session_id
        self.jwt_token = jwt_token  # JWT token passed directly from AgentRunner
        self.web_search_enabled = True  # Default to enabled
    
    def register_all_tools(self):
        self.thread_manager.add_tool(ExpandMessageTool, thread_id=self.thread_id, thread_manager=self.thread_manager)
        self.thread_manager.add_tool(MessageTool)
        self.thread_manager.add_tool(SandboxShellTool, project_id=self.project_id, thread_manager=self.thread_manager)
        self.thread_manager.add_tool(SandboxFilesTool, project_id=self.project_id, thread_manager=self.thread_manager)
        self.thread_manager.add_tool(SandboxBrowserTool, project_id=self.project_id, thread_id=self.thread_id, thread_manager=self.thread_manager)
        self.thread_manager.add_tool(SandboxDeployTool, project_id=self.project_id, thread_manager=self.thread_manager)
        self.thread_manager.add_tool(SandboxExposeTool, project_id=self.project_id, thread_manager=self.thread_manager)
        if self.web_search_enabled:
            self.thread_manager.add_tool(SandboxWebSearchTool, project_id=self.project_id, thread_manager=self.thread_manager)
        self.thread_manager.add_tool(SandboxVisionTool, project_id=self.project_id, thread_id=self.thread_id, thread_manager=self.thread_manager)
        self.thread_manager.add_tool(SandboxImageEditTool, project_id=self.project_id, thread_id=self.thread_id, thread_manager=self.thread_manager)
        self.thread_manager.add_tool(TaskListTool, project_id=self.project_id, thread_manager=self.thread_manager, thread_id=self.thread_id)
        if config.RAPID_API_KEY:
            self.thread_manager.add_tool(DataProvidersTool)
        # Add YouTube tool if user_id is available
        if self.user_id:
            self.thread_manager.add_tool(YouTubeTool, user_id=self.user_id, channel_ids=self.youtube_channels, thread_manager=self.thread_manager, jwt_token=self.jwt_token)
    
    def register_agent_builder_tools(self, agent_id: str):
        from agent.tools.agent_builder_tools.agent_config_tool import AgentConfigTool
        from agent.tools.agent_builder_tools.mcp_search_tool import MCPSearchTool
        from agent.tools.agent_builder_tools.credential_profile_tool import CredentialProfileTool
        from agent.tools.agent_builder_tools.workflow_tool import WorkflowTool
        from agent.tools.agent_builder_tools.trigger_tool import TriggerTool
        from services.supabase import DBConnection
        
        db = DBConnection()
        self.thread_manager.add_tool(AgentConfigTool, thread_manager=self.thread_manager, db_connection=db, agent_id=agent_id)
        self.thread_manager.add_tool(MCPSearchTool, thread_manager=self.thread_manager, db_connection=db, agent_id=agent_id)
        self.thread_manager.add_tool(CredentialProfileTool, thread_manager=self.thread_manager, db_connection=db, agent_id=agent_id)
        self.thread_manager.add_tool(WorkflowTool, thread_manager=self.thread_manager, db_connection=db, agent_id=agent_id)
        self.thread_manager.add_tool(TriggerTool, thread_manager=self.thread_manager, db_connection=db, agent_id=agent_id)
    
    def register_custom_tools(self, enabled_tools: Dict[str, Any]):
        self.thread_manager.add_tool(ExpandMessageTool, thread_id=self.thread_id, thread_manager=self.thread_manager)
        self.thread_manager.add_tool(MessageTool)
        self.thread_manager.add_tool(TaskListTool, project_id=self.project_id, thread_manager=self.thread_manager, thread_id=self.thread_id)

        def safe_tool_check(tool_name: str) -> bool:
            try:
                if not isinstance(enabled_tools, dict):
                    return False
                tool_config = enabled_tools.get(tool_name, {})
                if not isinstance(tool_config, dict):
                    return bool(tool_config) if isinstance(tool_config, bool) else False
                return tool_config.get('enabled', False)
            except Exception:
                return False
        
        if safe_tool_check('sb_shell_tool'):
            self.thread_manager.add_tool(SandboxShellTool, project_id=self.project_id, thread_manager=self.thread_manager)
        if safe_tool_check('sb_files_tool'):
            self.thread_manager.add_tool(SandboxFilesTool, project_id=self.project_id, thread_manager=self.thread_manager)
        if safe_tool_check('sb_browser_tool'):
            self.thread_manager.add_tool(SandboxBrowserTool, project_id=self.project_id, thread_id=self.thread_id, thread_manager=self.thread_manager)
        if safe_tool_check('sb_deploy_tool'):
            self.thread_manager.add_tool(SandboxDeployTool, project_id=self.project_id, thread_manager=self.thread_manager)
        if safe_tool_check('sb_expose_tool'):
            self.thread_manager.add_tool(SandboxExposeTool, project_id=self.project_id, thread_manager=self.thread_manager)
        if safe_tool_check('web_search_tool') and self.web_search_enabled:
            self.thread_manager.add_tool(SandboxWebSearchTool, project_id=self.project_id, thread_manager=self.thread_manager)
        if safe_tool_check('sb_vision_tool'):
            self.thread_manager.add_tool(SandboxVisionTool, project_id=self.project_id, thread_id=self.thread_id, thread_manager=self.thread_manager)
        if config.RAPID_API_KEY and safe_tool_check('data_providers_tool'):
            self.thread_manager.add_tool(DataProvidersTool)
        # Add YouTube tool if user_id is available
        if self.user_id:
            self.thread_manager.add_tool(YouTubeTool, user_id=self.user_id, channel_ids=self.youtube_channels, thread_manager=self.thread_manager, jwt_token=self.jwt_token)


class MCPManager:
    def __init__(self, thread_manager: ThreadManager, account_id: str, session_id: Optional[str] = None):
        self.thread_manager = thread_manager
        self.account_id = account_id
        self.session_id = session_id
    
    async def register_mcp_tools(self, agent_config: dict) -> Optional[MCPToolWrapper]:
        all_mcps = []
        
        if agent_config.get('configured_mcps'):
            all_mcps.extend(agent_config['configured_mcps'])
        
        if agent_config.get('custom_mcps'):
            for custom_mcp in agent_config['custom_mcps']:
                custom_type = custom_mcp.get('customType', custom_mcp.get('type', 'sse'))
                
                # Add user_id to social-media MCPs (JWT will be retrieved from session)
                if custom_type == 'social-media':
                    if 'config' not in custom_mcp:
                        custom_mcp['config'] = {}
                    custom_mcp['config']['user_id'] = self.account_id
                    # JWT token will be retrieved from session in MCPToolExecutor
                
                elif custom_type == 'composio':
                    qualified_name = custom_mcp.get('qualifiedName')
                    if not qualified_name:
                        qualified_name = f"composio.{custom_mcp['name'].replace(' ', '_').lower()}"
                    
                    mcp_config = {
                        'name': custom_mcp['name'],
                        'qualifiedName': qualified_name,
                        'config': custom_mcp.get('config', {}),
                        'enabledTools': custom_mcp.get('enabledTools', []),
                        'instructions': custom_mcp.get('instructions', ''),
                        'isCustom': True,
                        'customType': 'composio'
                    }
                    all_mcps.append(mcp_config)
                    continue
                
                mcp_config = {
                    'name': custom_mcp['name'],
                    'qualifiedName': f"custom_{custom_type}_{custom_mcp['name'].replace(' ', '_').lower()}",
                    'config': custom_mcp['config'],
                    'enabledTools': custom_mcp.get('enabledTools', []),
                    'instructions': custom_mcp.get('instructions', ''),
                    'isCustom': True,
                    'customType': custom_type
                }
                all_mcps.append(mcp_config)
        
        if not all_mcps:
            return None
        
        mcp_wrapper_instance = MCPToolWrapper(mcp_configs=all_mcps, session_id=self.session_id)
        try:
            await mcp_wrapper_instance.initialize_and_register_tools()
            
            updated_schemas = mcp_wrapper_instance.get_schemas()
            for method_name, schema_list in updated_schemas.items():
                for schema in schema_list:
                    self.thread_manager.tool_registry.tools[method_name] = {
                        "instance": mcp_wrapper_instance,
                        "schema": schema
                    }
            
            logger.info(f"⚡ Registered {len(updated_schemas)} MCP tools (Redis cache enabled)")
            return mcp_wrapper_instance
        except Exception as e:
            logger.error(f"Failed to initialize MCP tools: {e}")
            return None


class PromptManager:
    @staticmethod
    async def build_system_prompt(model_name: str, agent_config: Optional[dict], 
                                  is_agent_builder: bool, thread_id: str, 
                                  mcp_wrapper_instance: Optional[MCPToolWrapper],
                                  has_youtube_tools: bool = False) -> dict:
        
        if "gemini-2.5-flash" in model_name.lower() and "gemini-2.5-pro" not in model_name.lower():
            default_system_content = get_gemini_system_prompt()
        else:
            default_system_content = get_system_prompt()
        
        if "anthropic" not in model_name.lower():
            sample_response_path = os.path.join(os.path.dirname(__file__), 'sample_responses/1.txt')
            with open(sample_response_path, 'r') as file:
                sample_response = file.read()
            default_system_content = default_system_content + "\n\n <sample_assistant_response>" + sample_response + "</sample_assistant_response>"
        
        if is_agent_builder:
            system_content = get_agent_builder_prompt()
        elif agent_config and agent_config.get('system_prompt'):
            system_content = render_prompt_template(agent_config['system_prompt'].strip())
        else:
            system_content = default_system_content
        
        if agent_config and (agent_config.get('configured_mcps') or agent_config.get('custom_mcps')) and mcp_wrapper_instance and mcp_wrapper_instance._initialized:
            mcp_info = "\n\n--- MCP Tools Available ---\n"
            mcp_info += "You have access to external MCP (Model Context Protocol) server tools.\n"
            mcp_info += "MCP tools can be called directly using their native function names in the standard function calling format:\n"
            mcp_info += '<function_calls>\n'
            mcp_info += '<invoke name="{tool_name}">\n'
            mcp_info += '<parameter name="param1">value1</parameter>\n'
            mcp_info += '<parameter name="param2">value2</parameter>\n'
            mcp_info += '</invoke>\n'
            mcp_info += '</function_calls>\n\n'
            
            mcp_info += "Available MCP tools:\n"
            try:
                registered_schemas = mcp_wrapper_instance.get_schemas()
                for method_name, schema_list in registered_schemas.items():
                    for schema in schema_list:
                        if schema.schema_type == SchemaType.OPENAPI:
                            func_info = schema.schema.get('function', {})
                            description = func_info.get('description', 'No description available')
                            mcp_info += f"- **{method_name}**: {description}\n"
                            
                            params = func_info.get('parameters', {})
                            props = params.get('properties', {})
                            if props:
                                mcp_info += f"  Parameters: {', '.join(props.keys())}\n"
                                
            except Exception as e:
                logger.error(f"Error listing MCP tools: {e}")
                mcp_info += "- Error loading MCP tool list\n"
            
            mcp_info += "\n🚨 CRITICAL MCP TOOL RESULT INSTRUCTIONS 🚨\n"
            mcp_info += "When you use ANY MCP (Model Context Protocol) tools:\n"
            mcp_info += "1. ALWAYS read and use the EXACT results returned by the MCP tool\n"
            mcp_info += "2. For search tools: ONLY cite URLs, sources, and information from the actual search results\n"
            mcp_info += "3. For any tool: Base your response entirely on the tool's output - do NOT add external information\n"
            mcp_info += "4. DO NOT fabricate, invent, hallucinate, or make up any sources, URLs, or data\n"
            mcp_info += "5. If you need more information, call the MCP tool again with different parameters\n"
            mcp_info += "6. When writing reports/summaries: Reference ONLY the data from MCP tool results\n"
            mcp_info += "7. If the MCP tool doesn't return enough information, explicitly state this limitation\n"
            mcp_info += "8. Always double-check that every fact, URL, and reference comes from the MCP tool output\n"
            mcp_info += "\nIMPORTANT: MCP tool results are your PRIMARY and ONLY source of truth for external data!\n"
            mcp_info += "NEVER supplement MCP results with your training data or make assumptions beyond what the tools provide.\n"
            
            system_content += mcp_info
        
        # Add YouTube-specific instructions if YouTube tools are registered
        if has_youtube_tools:
            youtube_instructions = "\n\n🚨 CRITICAL YOUTUBE INTEGRATION RULES 🚨\n"
            youtube_instructions += "YouTube is a NATIVE integration that MUST be handled specially:\n\n"
            youtube_instructions += "✅ CORRECT approach for YouTube:\n"
            youtube_instructions += "1. Use youtube_channels tool FIRST (lists connected channels)\n"
            youtube_instructions += "2. Use youtube_channel_stats tool (get detailed channel statistics)\n"
            youtube_instructions += "3. Use youtube_upload_video tool (uploads videos to channels)\n"
            youtube_instructions += "4. Use youtube_authenticate tool ONLY if user explicitly asks to connect a new channel\n\n"
            youtube_instructions += "❌ NEVER do these for YouTube:\n"
            youtube_instructions += "• NEVER use create_credential_profile for YouTube\n"
            youtube_instructions += "• NEVER search for YouTube in MCP/Composio toolkits\n"
            youtube_instructions += "• NEVER use data_providers_tool for YouTube\n"
            youtube_instructions += "• NEVER treat YouTube as a third-party integration\n\n"
            youtube_instructions += "⚠️ WHY THIS MATTERS:\n"
            youtube_instructions += "YouTube is a first-class native integration with direct OAuth.\n"
            youtube_instructions += "Using the native tools provides better security and functionality.\n\n"
            youtube_instructions += "When user mentions YouTube analytics or channels, IMMEDIATELY use youtube_channels!\n"
            youtube_instructions += "Only use youtube_authenticate if the user explicitly wants to connect a NEW channel.\n"
            system_content += youtube_instructions
        
        return {"role": "system", "content": system_content}


class MessageManager:
    def __init__(self, client, thread_id: str, model_name: str, trace: Optional[StatefulTraceClient]):
        self.client = client
        self.thread_id = thread_id
        self.model_name = model_name
        self.trace = trace
    
    async def build_temporary_message(self) -> Optional[dict]:
        temp_message_content_list = []

        latest_browser_state_msg = await self.client.table('messages').select('*').eq('thread_id', self.thread_id).eq('type', 'browser_state').order('created_at', desc=True).limit(1).execute()
        if latest_browser_state_msg.data and len(latest_browser_state_msg.data) > 0:
            try:
                browser_content = latest_browser_state_msg.data[0]["content"]
                if isinstance(browser_content, str):
                    browser_content = json.loads(browser_content)
                screenshot_base64 = browser_content.get("screenshot_base64")
                screenshot_url = browser_content.get("image_url")
                
                browser_state_text = browser_content.copy()
                browser_state_text.pop('screenshot_base64', None)
                browser_state_text.pop('image_url', None)

                if browser_state_text:
                    temp_message_content_list.append({
                        "type": "text",
                        "text": f"The following is the current state of the browser:\n{json.dumps(browser_state_text, indent=2)}"
                    })
                
                if 'gemini' in self.model_name.lower() or 'anthropic' in self.model_name.lower() or 'openai' in self.model_name.lower():
                    if screenshot_url:
                        temp_message_content_list.append({
                            "type": "image_url",
                            "image_url": {
                                "url": screenshot_url,
                                "format": "image/jpeg"
                            }
                        })
                    elif screenshot_base64:
                        temp_message_content_list.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{screenshot_base64}",
                            }
                        })

            except Exception as e:
                logger.error(f"Error parsing browser state: {e}")

        latest_image_context_msg = await self.client.table('messages').select('*').eq('thread_id', self.thread_id).eq('type', 'image_context').order('created_at', desc=True).limit(1).execute()
        if latest_image_context_msg.data and len(latest_image_context_msg.data) > 0:
            try:
                image_context_content = latest_image_context_msg.data[0]["content"] if isinstance(latest_image_context_msg.data[0]["content"], dict) else json.loads(latest_image_context_msg.data[0]["content"])
                base64_image = image_context_content.get("base64")
                mime_type = image_context_content.get("mime_type")
                file_path = image_context_content.get("file_path", "unknown file")

                if base64_image and mime_type:
                    temp_message_content_list.append({
                        "type": "text",
                        "text": f"Here is the image you requested to see: '{file_path}'"
                    })
                    temp_message_content_list.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}",
                        }
                    })

                await self.client.table('messages').delete().eq('message_id', latest_image_context_msg.data[0]["message_id"]).execute()
            except Exception as e:
                logger.error(f"Error parsing image context: {e}")

        if temp_message_content_list:
            return {"role": "user", "content": temp_message_content_list}
        return None


class AgentRunner:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.jwt_token = None  # Will be retrieved from session
    
    async def setup(self):
        # Retrieve session context if session_id is provided
        if self.config.session_id:
            session_data = await SessionManager.get_session(self.config.session_id)
            if session_data:
                self.jwt_token = session_data.get("jwt_token")
                logger.info(f"Retrieved JWT token from session {self.config.session_id}")
            else:
                logger.warning(f"Session {self.config.session_id} not found in AgentRunner")
        
        if not self.config.trace:
            self.config.trace = langfuse.trace(name="run_agent", session_id=self.config.thread_id, metadata={"project_id": self.config.project_id})
        
        self.thread_manager = ThreadManager(
            trace=self.config.trace, 
            is_agent_builder=self.config.is_agent_builder or False, 
            target_agent_id=self.config.target_agent_id, 
            agent_config=self.config.agent_config
        )
        
        self.client = await self.thread_manager.db.client
        self.account_id = await get_account_id_from_thread(self.client, self.config.thread_id)
        if not self.account_id:
            raise ValueError("Could not determine account ID for thread")

        project = await self.client.table('projects').select('*').eq('project_id', self.config.project_id).execute()
        if not project.data or len(project.data) == 0:
            raise ValueError(f"Project {self.config.project_id} not found")

        project_data = project.data[0]
        sandbox_info = project_data.get('sandbox', {})
        
        # Handle case where sandbox is stored as JSON string
        if isinstance(sandbox_info, str):
            try:
                import json
                sandbox_info = json.loads(sandbox_info)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse sandbox JSON for project {self.config.project_id}")
                sandbox_info = {}
        
        if not sandbox_info.get('id'):
            logger.warning(f"No sandbox found for project {self.config.project_id}, continuing without sandbox tools")
    
    async def setup_tools(self):
        # YouTube channels are now handled through MCP system
        # But we still track them for the system prompt
        youtube_channels = []
        if self.config.agent_config:
            custom_mcps = self.config.agent_config.get('custom_mcps', [])
            for mcp in custom_mcps:
                if mcp.get('customType') == 'social-media' and mcp.get('platform') == 'youtube':
                    qualified_name = mcp.get('qualifiedName', '')
                    if qualified_name.startswith('social.youtube.'):
                        channel_id = qualified_name.replace('social.youtube.', '')
                        if channel_id:
                            youtube_channels.append(channel_id)
        
        self.tool_manager = ToolManager(
            self.thread_manager, 
            self.config.project_id, 
            self.config.thread_id,
            user_id=self.account_id if hasattr(self, 'account_id') else None,
            youtube_channels=youtube_channels,
            session_id=self.config.session_id,
            jwt_token=self.jwt_token  # Pass both session_id and jwt_token
        )
        tool_manager = self.tool_manager  # Keep local reference for backward compatibility
        
        if self.config.agent_config and self.config.agent_config.get('is_suna_default', False):
            suna_agent_id = self.config.agent_config['agent_id']
            tool_manager.register_agent_builder_tools(suna_agent_id)
        
        if self.config.is_agent_builder:
            tool_manager.register_agent_builder_tools(self.config.target_agent_id)

        enabled_tools = None
        if self.config.agent_config and 'agentpress_tools' in self.config.agent_config:
            raw_tools = self.config.agent_config['agentpress_tools']
            
            if isinstance(raw_tools, dict):
                if self.config.agent_config.get('is_suna_default', False) and not raw_tools:
                    enabled_tools = None
                else:
                    enabled_tools = raw_tools
            else:
                enabled_tools = None

        if enabled_tools is None:
            tool_manager.register_all_tools()
        else:
            if not isinstance(enabled_tools, dict):
                enabled_tools = {}
            tool_manager.register_custom_tools(enabled_tools)
    
    async def setup_mcp_tools(self) -> Optional[MCPToolWrapper]:
        if not self.config.agent_config:
            return None
        
        mcp_manager = MCPManager(self.thread_manager, self.account_id, self.config.session_id)
        return await mcp_manager.register_mcp_tools(self.config.agent_config)
    
    def get_max_tokens(self) -> Optional[int]:
        if "sonnet" in self.config.model_name.lower():
            return 8192
        elif "gpt-4" in self.config.model_name.lower():
            return 4096
        elif "gemini-2.5-pro" in self.config.model_name.lower():
            return 64000
        elif "kimi-k2" in self.config.model_name.lower():
            return 8192
        return None
    
    async def run(self) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            await self.setup()
        except Exception as e:
            logger.error(f"Failed to setup agent: {e}", exc_info=True)
            raise
        
        # Tool setup will happen after checking web search preference
        mcp_wrapper_instance = None
        system_message = None

        iteration_count = 0
        continue_execution = True

        # Check for web search preference from latest user message
        web_search_enabled = True  # Default
        latest_user_message = await self.client.table('messages').select('*').eq('thread_id', self.config.thread_id).eq('type', 'user').order('created_at', desc=True).limit(1).execute()
        if latest_user_message.data and len(latest_user_message.data) > 0:
            data = latest_user_message.data[0]['content']
            if isinstance(data, str):
                data = json.loads(data)
            
            # Check for web search preference in message metadata
            message_metadata = latest_user_message.data[0].get('metadata', {})
            if isinstance(message_metadata, str):
                try:
                    message_metadata = json.loads(message_metadata)
                except:
                    message_metadata = {}
            
            # Set web search preference (default to True if not specified)
            web_search_enabled = message_metadata.get('enable_web_search', True)
            
            if self.config.trace:
                self.config.trace.update(input=data['content'])
        
        # Now setup tools with web search preference
        try:
            await self.setup_tools()
            self.tool_manager.web_search_enabled = web_search_enabled
        except Exception as e:
            logger.error(f"Failed to setup tools: {e}", exc_info=True)
            raise
        
        try:
            mcp_wrapper_instance = await self.setup_mcp_tools()
            if mcp_wrapper_instance:
                logger.info(f"MCP tools initialized successfully with JWT token present: {bool(self.jwt_token)}")
        except Exception as e:
            logger.error(f"Failed to setup MCP tools: {e}", exc_info=True)
            raise
        
        # Check if YouTube tools are registered through MCP
        has_youtube_tools = False
        if mcp_wrapper_instance and hasattr(mcp_wrapper_instance, '_custom_tools'):
            for tool_name in mcp_wrapper_instance._custom_tools:
                if tool_name.startswith('youtube_'):
                    has_youtube_tools = True
                    break
        
        # Build system message after tools are set up
        system_message = await PromptManager.build_system_prompt(
            self.config.model_name, self.config.agent_config, 
            self.config.is_agent_builder, self.config.thread_id, 
            mcp_wrapper_instance,
            has_youtube_tools=has_youtube_tools
        )
        
        logger.debug(f"Web search enabled: {web_search_enabled}")

        message_manager = MessageManager(self.client, self.config.thread_id, self.config.model_name, self.config.trace)

        while continue_execution and iteration_count < self.config.max_iterations:
            iteration_count += 1

            can_run, message, subscription = await check_billing_status(self.client, self.account_id)
            if not can_run:
                error_msg = f"Billing limit reached: {message}"
                yield {
                    "type": "status",
                    "status": "stopped",
                    "message": error_msg
                }
                break

            latest_message = await self.client.table('messages').select('*').eq('thread_id', self.config.thread_id).in_('type', ['assistant', 'tool', 'user']).order('created_at', desc=True).limit(1).execute()
            if latest_message.data and len(latest_message.data) > 0:
                message_type = latest_message.data[0].get('type')
                if message_type == 'assistant':
                    continue_execution = False
                    break

            temporary_message = await message_manager.build_temporary_message()
            max_tokens = self.get_max_tokens()
            
            generation = self.config.trace.generation(name="thread_manager.run_thread") if self.config.trace else None
            try:
                response = await self.thread_manager.run_thread(
                    thread_id=self.config.thread_id,
                    system_prompt=system_message,
                    stream=self.config.stream,
                    llm_model=self.config.model_name,
                    llm_temperature=0,
                    llm_max_tokens=max_tokens,
                    tool_choice="auto",
                    max_xml_tool_calls=1,
                    temporary_message=temporary_message,
                    processor_config=ProcessorConfig(
                        xml_tool_calling=True,
                        native_tool_calling=False,
                        execute_tools=True,
                        execute_on_stream=True,
                        tool_execution_strategy="parallel",
                        xml_adding_strategy="user_message"
                    ),
                    native_max_auto_continues=self.config.native_max_auto_continues,
                    include_xml_examples=True,
                    enable_thinking=self.config.enable_thinking,
                    reasoning_effort=self.config.reasoning_effort,
                    enable_context_manager=self.config.enable_context_manager,
                    generation=generation
                )

                if isinstance(response, dict) and "status" in response and response["status"] == "error":
                    yield response
                    break

                last_tool_call = None
                agent_should_terminate = False
                error_detected = False
                full_response = ""

                try:
                    if hasattr(response, '__aiter__') and not isinstance(response, dict):
                        async for chunk in response:
                            if isinstance(chunk, dict) and chunk.get('type') == 'status' and chunk.get('status') == 'error':
                                error_detected = True
                                yield chunk
                                continue
                            
                            if chunk.get('type') == 'status':
                                try:
                                    metadata = chunk.get('metadata', {})
                                    if isinstance(metadata, str):
                                        metadata = json.loads(metadata)
                                    
                                    if metadata.get('agent_should_terminate'):
                                        agent_should_terminate = True
                                        
                                        content = chunk.get('content', {})
                                        if isinstance(content, str):
                                            content = json.loads(content)
                                        
                                        if content.get('function_name'):
                                            last_tool_call = content['function_name']
                                        elif content.get('xml_tag_name'):
                                            last_tool_call = content['xml_tag_name']
                                            
                                except Exception:
                                    pass
                            
                            if chunk.get('type') == 'assistant' and 'content' in chunk:
                                try:
                                    content = chunk.get('content', '{}')
                                    if isinstance(content, str):
                                        assistant_content_json = json.loads(content)
                                    else:
                                        assistant_content_json = content

                                    assistant_text = assistant_content_json.get('content', '')
                                    full_response += assistant_text
                                    if isinstance(assistant_text, str):
                                        if '</ask>' in assistant_text or '</complete>' in assistant_text or '</web-browser-takeover>' in assistant_text:
                                           if '</ask>' in assistant_text:
                                               xml_tool = 'ask'
                                           elif '</complete>' in assistant_text:
                                               xml_tool = 'complete'
                                           elif '</web-browser-takeover>' in assistant_text:
                                               xml_tool = 'web-browser-takeover'

                                           last_tool_call = xml_tool
                                
                                except json.JSONDecodeError:
                                    pass
                                except Exception:
                                    pass

                            yield chunk
                    else:
                        error_detected = True

                    if error_detected:
                        if generation:
                            generation.end(output=full_response, status_message="error_detected", level="ERROR")
                        break
                        
                    if agent_should_terminate or last_tool_call in ['ask', 'complete', 'web-browser-takeover']:
                        if generation:
                            generation.end(output=full_response, status_message="agent_stopped")
                        continue_execution = False

                except Exception as e:
                    error_msg = f"Error during response streaming: {str(e)}"
                    if generation:
                        generation.end(output=full_response, status_message=error_msg, level="ERROR")
                    yield {
                        "type": "status",
                        "status": "error",
                        "message": error_msg
                    }
                    break
                    
            except Exception as e:
                error_msg = f"Error running thread: {str(e)}"
                yield {
                    "type": "status",
                    "status": "error",
                    "message": error_msg
                }
                break
            
            if generation:
                generation.end(output=full_response)

        asyncio.create_task(asyncio.to_thread(lambda: langfuse.flush()))


async def run_agent(
    thread_id: str,
    project_id: str,
    stream: bool,
    thread_manager: Optional[ThreadManager] = None,
    native_max_auto_continues: int = 25,
    max_iterations: int = 100,
    model_name: str = "anthropic/claude-sonnet-4-20250514",
    enable_thinking: Optional[bool] = False,
    reasoning_effort: Optional[str] = 'low',
    enable_context_manager: bool = True,
    agent_config: Optional[dict] = None,    
    trace: Optional[StatefulTraceClient] = None,
    is_agent_builder: Optional[bool] = False,
    target_agent_id: Optional[str] = None,
    session_id: Optional[str] = None  # Changed from jwt_token to session_id
):
    config = AgentConfig(
        thread_id=thread_id,
        project_id=project_id,
        stream=stream,
        native_max_auto_continues=native_max_auto_continues,
        max_iterations=max_iterations,
        model_name=model_name,
        enable_thinking=enable_thinking,
        reasoning_effort=reasoning_effort,
        enable_context_manager=enable_context_manager,
        agent_config=agent_config,
        trace=trace,
        is_agent_builder=is_agent_builder,
        target_agent_id=target_agent_id,
        session_id=session_id  # Pass session_id instead of jwt_token
    )
    
    runner = AgentRunner(config)
    async for chunk in runner.run():
        yield chunk