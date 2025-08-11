"""
YouTube Authentication API Routes for FastAPI
"""

from fastapi import APIRouter, Request, Response, HTTPException, Depends, Header
from fastapi.responses import HTMLResponse
from typing import Optional
import logging
import os
import jwt
from supabase import create_client, Client

from backend.youtube.oauth import YouTubeMCPOAuth
from backend.youtube.channels import YouTubeMCPChannels

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/youtube/auth", tags=["YouTube Auth"])

# Supabase client initialization
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

def get_supabase_client() -> Client:
    """Get Supabase client instance"""
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """Extract user ID from Supabase JWT token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    try:
        # Decode JWT to get user ID (Supabase uses HS256)
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return payload.get("sub")  # Supabase user ID
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT validation error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/initiate")
async def initiate_oauth(
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    """
    Initiate YouTube OAuth flow
    
    Returns authorization URL for user to visit
    """
    try:
        oauth = YouTubeMCPOAuth()
        
        # Use default redirect URI if not provided
        if not redirect_uri:
            redirect_uri = "http://localhost:8000/api/youtube/auth/callback"
        
        auth_url = oauth.get_auth_url(redirect_uri, state)
        
        return {
            "auth_url": auth_url,
            "message": "Visit the authorization URL to connect your YouTube account"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to initiate OAuth: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate OAuth flow")


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    """
    Handle OAuth callback from Google
    
    Exchanges authorization code for tokens and saves channel
    """
    # Handle OAuth errors
    if error:
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>YouTube Authentication Failed</title>
        </head>
        <body>
            <script>
                window.opener.postMessage({{
                    type: 'youtube-auth-error',
                    error: '{error}'
                }}, '*');
                window.close();
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)
    
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received")
    
    try:
        # Initialize OAuth handler
        oauth = YouTubeMCPOAuth()
        
        # Build redirect URI
        redirect_uri = str(request.url).split('?')[0]  # Remove query params
        
        # Exchange code for tokens
        token = await oauth.exchange_code_for_token(code, redirect_uri)
        
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Initialize channels manager
        channels_manager = YouTubeMCPChannels(supabase)
        
        # Get channel info and save
        channel = await channels_manager.get_channel_for_token(token, user_id)
        await channels_manager.save_channel(channel)
        
        # Create masked channel for display
        masked_channel = channels_manager.mask_channel(channel)
        
        # Return success HTML that closes popup
        success_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>YouTube Authentication Successful</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    background: #fafafa;
                }}
                .message {{
                    text-align: center;
                    color: #333;
                }}
            </style>
        </head>
        <body>
            <div class="message">
                <p>Authentication successful! This window will close automatically...</p>
            </div>
            
            <script>
                // Send success message to parent window
                const message = {{
                    type: 'youtube-auth-success',
                    account: {{
                        id: '{masked_channel.id}',
                        username: '{masked_channel.name}',
                        name: '{masked_channel.name}',
                        thumbnail: '{masked_channel.thumbnail_url or ""}'
                    }}
                }};
                
                if (window.opener) {{
                    window.opener.postMessage(message, '*');
                }}
                
                // Close window after short delay
                setTimeout(() => {{
                    window.close();
                }}, 1000);
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=success_html)
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>YouTube Authentication Failed</title>
        </head>
        <body>
            <script>
                window.opener.postMessage({{
                    type: 'youtube-auth-error',
                    error: 'Authentication failed: {str(e)}'
                }}, '*');
                window.close();
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=error_html, status_code=500)


@router.post("/refresh")
async def refresh_token(
    refresh_token: str,
    user_id: str = Depends(get_current_user)
):
    """
    Refresh an expired access token
    
    Args:
        refresh_token: Refresh token from previous OAuth flow
        
    Returns:
        New access token and expiry
    """
    try:
        oauth = YouTubeMCPOAuth()
        new_token = await oauth.refresh_access_token(refresh_token)
        
        return {
            "access_token": new_token.access_token,
            "expiry": new_token.expiry.isoformat(),
            "message": "Token refreshed successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to refresh token: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh token")