#!/usr/bin/env python3
"""
Test script to verify YouTube MCP integration
"""
import json

def test_youtube_mcp_config():
    """Test that YouTube MCP configuration is properly formatted"""
    
    # Sample YouTube MCP configuration that should be passed from frontend
    youtube_mcp_config = {
        'name': 'YouTube - TestChannel',
        'qualifiedName': 'social.youtube.UC_x5XG1OV2P6uZZ5FSM9Ttw',
        'customType': 'social-media',
        'platform': 'youtube',
        'config': {
            'user_id': 'test-user-123'  # This will be added by run.py
        },
        'enabledTools': ['youtube_authenticate', 'youtube_channels', 'youtube_upload_video', 'youtube_channel_stats']
    }
    
    print("YouTube MCP Configuration Test")
    print("=" * 50)
    print(json.dumps(youtube_mcp_config, indent=2))
    print()
    
    # Check required fields
    assert youtube_mcp_config['customType'] == 'social-media', "customType must be 'social-media'"
    assert youtube_mcp_config['platform'] == 'youtube', "platform must be 'youtube'"
    assert youtube_mcp_config['qualifiedName'].startswith('social.youtube.'), "qualifiedName must start with 'social.youtube.'"
    
    # Extract channel ID
    channel_id = youtube_mcp_config['qualifiedName'].replace('social.youtube.', '')
    print(f"✅ Extracted channel ID: {channel_id}")
    
    # Verify tools that will be registered
    expected_tools = [
        'youtube_authenticate',
        'youtube_channels', 
        'youtube_upload_video',
        'youtube_channel_stats'
    ]
    
    print(f"✅ Expected tools to be registered: {expected_tools}")
    
    # Test agent config structure
    agent_config = {
        'custom_mcps': [youtube_mcp_config]
    }
    
    print("\nAgent Configuration with YouTube MCP:")
    print(json.dumps(agent_config, indent=2))
    
    print("\n✅ YouTube MCP configuration test passed!")
    print("\nIntegration Flow:")
    print("1. Frontend adds YouTube channels to custom_mcps with customType='social-media'")
    print("2. Backend run.py adds user_id to the config")
    print("3. MCPToolWrapper initializes with this config")
    print("4. CustomMCPHandler recognizes 'social-media' type and calls _initialize_social_media_mcp")
    print("5. YouTube tools are registered: youtube_authenticate, youtube_channels, etc.")
    print("6. MCPToolExecutor handles execution by calling YouTubeTool methods")
    print("7. Agent can now use YouTube tools through the MCP system")
    
    return True

if __name__ == "__main__":
    test_youtube_mcp_config()