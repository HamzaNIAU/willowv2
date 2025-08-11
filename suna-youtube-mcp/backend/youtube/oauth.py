"""
YouTube OAuth Implementation for Suna
Handles OAuth flow, token management, and scope capabilities
"""

import os
import json
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from urllib.parse import urlencode
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Default redirect URI for OAuth flow
DEFAULT_REDIRECT_URI = os.getenv(
    "YOUTUBE_REDIRECT_URI",
    "http://localhost:8000/api/youtube/auth/callback"
)

# YouTube OAuth scopes - comprehensive for full functionality
YOUTUBE_SCOPES = [
    # Core scopes (matching Go MCP implementation)
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    
    # Analytics & Reporting scopes
    "https://www.googleapis.com/auth/yt-analytics.readonly",           # General analytics
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",  # Monetization data
    
    # Additional YouTube features
    "https://www.googleapis.com/auth/youtube.channel-memberships.creator",  # Channel memberships
    "https://www.googleapis.com/auth/youtube.force-ssl",                   # Live streaming & management
    "https://www.googleapis.com/auth/youtubepartner"                      # YouTube Partner features
]

# Scope capabilities mapping
SCOPE_CAPABILITIES = {
    "https://www.googleapis.com/auth/youtube.upload": ["upload"],
    "https://www.googleapis.com/auth/youtube.readonly": ["management"],
    "https://www.googleapis.com/auth/yt-analytics.readonly": ["analytics"],
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly": ["monetization"],
    "https://www.googleapis.com/auth/youtube.force-ssl": ["streaming", "management"],
    "https://www.googleapis.com/auth/youtubepartner": ["monetization", "management"],
    "https://www.googleapis.com/auth/youtube.channel-memberships.creator": ["monetization"]
}


class YouTubeToken(BaseModel):
    """YouTube OAuth token model"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expiry: datetime
    scopes: List[str] = []


class YouTubeMCPOAuth:
    """
    YouTube OAuth handler for Suna
    Manages authentication flow and token lifecycle
    """
    
    def __init__(self):
        """Initialize OAuth handler with credentials from environment"""
        self.client_id = os.getenv("YOUTUBE_CLIENT_ID", "")
        self.client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "")
        self.http_client = httpx.AsyncClient()
    
    def __del__(self):
        """Cleanup HTTP client"""
        if hasattr(self, 'http_client'):
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.http_client.aclose())
            except:
                pass
    
    @staticmethod
    def get_capabilities_from_scopes(scopes: List[str]) -> Dict[str, bool]:
        """
        Get capabilities based on granted scopes
        
        Args:
            scopes: List of OAuth scopes
            
        Returns:
            Dictionary of capabilities and their availability
        """
        capabilities = {
            "upload": False,
            "analytics": False,
            "monetization": False,
            "streaming": False,
            "management": False
        }
        
        for scope in scopes:
            scope_capabilities = SCOPE_CAPABILITIES.get(scope, [])
            for capability in scope_capabilities:
                capabilities[capability] = True
        
        return capabilities
    
    def check_config(self) -> None:
        """
        Check if OAuth is properly configured
        
        Raises:
            ValueError: If OAuth credentials are not configured
        """
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "YouTube OAuth is not configured. To enable YouTube uploads:\n\n"
                "1. Go to https://console.cloud.google.com/\n"
                "2. Create a new project or select existing\n"
                "3. Enable YouTube Data API v3\n"
                "4. Create OAuth 2.0 credentials (Web Application type)\n"
                "5. Download the credentials\n"
                "6. Set these environment variables:\n"
                "   - YOUTUBE_CLIENT_ID=your_client_id\n"
                "   - YOUTUBE_CLIENT_SECRET=your_client_secret\n\n"
                "See: https://developers.google.com/youtube/v3/getting-started"
            )
    
    def get_auth_url(self, redirect_uri: str = DEFAULT_REDIRECT_URI, state: Optional[str] = None) -> str:
        """
        Generate authorization URL for OAuth flow
        
        Args:
            redirect_uri: OAuth redirect URI
            state: Optional state token for CSRF protection
            
        Returns:
            Authorization URL for user to visit
            
        Raises:
            ValueError: If OAuth is not configured
        """
        self.check_config()
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(YOUTUBE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state or "state-token"
        }
        
        return f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"
    
    async def exchange_code_for_token(
        self, 
        code: str, 
        redirect_uri: str = DEFAULT_REDIRECT_URI
    ) -> YouTubeToken:
        """
        Exchange authorization code for access and refresh tokens
        
        Args:
            code: Authorization code from OAuth callback
            redirect_uri: OAuth redirect URI (must match initial request)
            
        Returns:
            YouTubeToken with access and refresh tokens
            
        Raises:
            ValueError: If code exchange fails
        """
        if not code:
            raise ValueError("Authorization code must be provided")
        
        self.check_config()
        
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        
        try:
            response = await self.http_client.post(
                "https://oauth2.googleapis.com/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Failed to exchange code: {error_text}")
                raise ValueError(f"Failed to exchange code for token: {error_text}")
            
            token_data = response.json()
            
            # Calculate token expiry
            expires_in = token_data.get("expires_in", 3600)
            expiry = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Extract scopes if provided
            scopes = token_data.get("scope", "").split() if token_data.get("scope") else YOUTUBE_SCOPES
            
            return YouTubeToken(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", ""),
                token_type=token_data.get("token_type", "Bearer"),
                expiry=expiry,
                scopes=scopes
            )
            
        except httpx.RequestError as e:
            logger.error(f"Network error during token exchange: {e}")
            raise ValueError(f"Network error during token exchange: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during token exchange: {e}")
            raise ValueError(f"Failed to exchange code for token: {str(e)}")
    
    async def refresh_access_token(self, refresh_token: str) -> YouTubeToken:
        """
        Refresh an expired access token using refresh token
        
        Args:
            refresh_token: Refresh token from previous OAuth flow
            
        Returns:
            YouTubeToken with new access token
            
        Raises:
            ValueError: If token refresh fails
        """
        if not refresh_token:
            raise ValueError("Refresh token must be provided")
        
        self.check_config()
        
        data = {
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token"
        }
        
        try:
            response = await self.http_client.post(
                "https://oauth2.googleapis.com/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Failed to refresh token: {error_text}")
                raise ValueError(f"Failed to refresh access token: {error_text}")
            
            token_data = response.json()
            
            # Calculate new token expiry
            expires_in = token_data.get("expires_in", 3600)
            expiry = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Preserve original refresh token if not returned
            actual_refresh_token = token_data.get("refresh_token", refresh_token)
            
            # Extract scopes if provided
            scopes = token_data.get("scope", "").split() if token_data.get("scope") else YOUTUBE_SCOPES
            
            return YouTubeToken(
                access_token=token_data["access_token"],
                refresh_token=actual_refresh_token,
                token_type=token_data.get("token_type", "Bearer"),
                expiry=expiry,
                scopes=scopes
            )
            
        except httpx.RequestError as e:
            logger.error(f"Network error during token refresh: {e}")
            raise ValueError(f"Network error during token refresh: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}")
            raise ValueError(f"Failed to refresh access token: {str(e)}")
    
    def is_token_expired(self, token: YouTubeToken, buffer_minutes: int = 5) -> bool:
        """
        Check if a token is expired or about to expire
        
        Args:
            token: YouTubeToken to check
            buffer_minutes: Minutes before expiry to consider token expired
            
        Returns:
            True if token is expired or will expire soon
        """
        buffer = timedelta(minutes=buffer_minutes)
        return datetime.utcnow() + buffer >= token.expiry
    
    async def get_valid_access_token(self, token: YouTubeToken) -> str:
        """
        Get a valid access token, refreshing if necessary
        
        Args:
            token: Current YouTubeToken
            
        Returns:
            Valid access token string
            
        Raises:
            ValueError: If token cannot be refreshed
        """
        if self.is_token_expired(token):
            if not token.refresh_token:
                raise ValueError("Token is expired and no refresh token available")
            
            logger.info("Token expired, refreshing...")
            new_token = await self.refresh_access_token(token.refresh_token)
            
            # Update the original token object
            token.access_token = new_token.access_token
            token.expiry = new_token.expiry
            
            return new_token.access_token
        
        return token.access_token