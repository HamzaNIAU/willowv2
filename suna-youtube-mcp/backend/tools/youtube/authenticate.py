"""
YouTube Authenticate Tool for LiteLLM
Initiates YouTube OAuth authentication flow
"""

import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.youtube.oauth import YouTubeMCPOAuth


class AuthenticateParams(BaseModel):
    """Parameters for YouTube authentication"""
    redirect_uri: Optional[str] = Field(
        default=None,
        description="Redirect URI for OAuth2 authentication"
    )
    state: Optional[str] = Field(
        default=None,
        description="State token for CSRF protection"
    )


class AuthenticateTool:
    """
    YouTube authentication tool for LiteLLM
    Starts the OAuth flow and returns authentication URL
    """
    
    name = "youtube_authenticate"
    description = (
        "Start YouTube OAuth authentication flow. "
        "Opens a popup window that handles authentication automatically."
    )
    
    def __init__(self):
        self.oauth_handler = YouTubeMCPOAuth()
    
    async def execute(self, params: AuthenticateParams) -> Dict[str, Any]:
        """
        Execute the authentication tool
        
        Args:
            params: Authentication parameters
            
        Returns:
            Dictionary with authentication URL and instructions
        """
        try:
            # Use default redirect URI if not provided
            redirect_uri = params.redirect_uri
            if not redirect_uri:
                redirect_uri = os.getenv(
                    "YOUTUBE_REDIRECT_URI",
                    "http://localhost:8000/api/youtube/auth/callback"
                )
            
            # Get authentication URL
            auth_url = self.oauth_handler.get_auth_url(
                redirect_uri=redirect_uri,
                state=params.state
            )
            
            # Return formatted response for UI
            return {
                "type": "youtube-auth",
                "auth_url": auth_url,
                "message": "Click the button below to connect your YouTube account. The authentication will complete automatically.",
                "instructions": [
                    "Click the 'Authenticate with YouTube' button",
                    "Log in to your Google account and authorize the application",
                    "The window will close automatically once connected",
                    "Your YouTube channel will appear in the accounts list"
                ]
            }
            
        except ValueError as e:
            # Configuration error - return as informative message
            error_message = str(e)
            if "YouTube OAuth is not configured" in error_message:
                return {
                    "type": "error",
                    "error": "configuration",
                    "message": error_message
                }
            
            # Other errors
            return {
                "type": "error",
                "error": "authentication_failed",
                "message": f"Failed to get authentication URL: {error_message}"
            }
        except Exception as e:
            return {
                "type": "error",
                "error": "unexpected",
                "message": f"Unexpected error during authentication: {str(e)}"
            }
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for this tool
        
        Returns:
            JSON schema compatible with LiteLLM
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "redirect_uri": {
                        "type": "string",
                        "description": "Redirect URI for OAuth2 authentication"
                    },
                    "state": {
                        "type": "string",
                        "description": "State token for CSRF protection"
                    }
                },
                "required": []
            }
        }


# Create singleton instance for import
authenticate_tool = AuthenticateTool()