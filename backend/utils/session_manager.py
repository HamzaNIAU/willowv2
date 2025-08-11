"""Session management for agent context propagation"""

import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from services import redis
from utils.logger import logger


class SessionManager:
    """Manages session storage for agent execution context"""
    
    SESSION_TTL = 3600 * 2  # 2 hours
    SESSION_PREFIX = "agent_session:"
    
    @classmethod
    async def create_session(
        cls,
        user_id: str,
        account_id: str,
        jwt_token: Optional[str] = None,
        thread_id: Optional[str] = None,
        project_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new session and store it in Redis
        
        Returns:
            session_id: Unique identifier for the session
        """
        session_id = str(uuid.uuid4())
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "account_id": account_id,
            "jwt_token": jwt_token,
            "thread_id": thread_id,
            "project_id": project_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        
        # Store in Redis with TTL
        session_key = f"{cls.SESSION_PREFIX}{session_id}"
        await redis.set(
            session_key,
            json.dumps(session_data),
            ex=cls.SESSION_TTL
        )
        
        logger.info(f"Created session {session_id} for user {user_id}")
        return session_id
    
    @classmethod
    async def get_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data from Redis
        
        Returns:
            Session data dict or None if not found
        """
        session_key = f"{cls.SESSION_PREFIX}{session_id}"
        session_data = await redis.get(session_key)
        
        if not session_data:
            logger.warning(f"Session {session_id} not found")
            return None
        
        try:
            if isinstance(session_data, bytes):
                session_data = session_data.decode('utf-8')
            return json.loads(session_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode session {session_id}: {e}")
            return None
    
    @classmethod
    async def update_session(
        cls,
        session_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update an existing session
        
        Returns:
            True if successful, False otherwise
        """
        session_data = await cls.get_session(session_id)
        if not session_data:
            return False
        
        # Update session data
        session_data.update(updates)
        session_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Store back in Redis
        session_key = f"{cls.SESSION_PREFIX}{session_id}"
        await redis.set(
            session_key,
            json.dumps(session_data),
            ex=cls.SESSION_TTL
        )
        
        logger.debug(f"Updated session {session_id}")
        return True
    
    @classmethod
    async def extend_session(cls, session_id: str, ttl_seconds: Optional[int] = None) -> bool:
        """
        Extend the TTL of a session
        
        Returns:
            True if successful, False otherwise
        """
        session_key = f"{cls.SESSION_PREFIX}{session_id}"
        ttl = ttl_seconds or cls.SESSION_TTL
        
        try:
            await redis.expire(session_key, ttl)
            logger.debug(f"Extended session {session_id} TTL to {ttl} seconds")
            return True
        except Exception as e:
            logger.error(f"Failed to extend session {session_id}: {e}")
            return False
    
    @classmethod
    async def delete_session(cls, session_id: str) -> bool:
        """
        Delete a session from Redis
        
        Returns:
            True if deleted, False otherwise
        """
        session_key = f"{cls.SESSION_PREFIX}{session_id}"
        
        try:
            result = await redis.delete(session_key)
            if result:
                logger.info(f"Deleted session {session_id}")
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    @classmethod
    async def get_user_context(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user context from session (convenience method)
        
        Returns:
            Dict with user_id, account_id, jwt_token
        """
        session_data = await cls.get_session(session_id)
        if not session_data:
            return None
        
        return {
            "user_id": session_data.get("user_id"),
            "account_id": session_data.get("account_id"),
            "jwt_token": session_data.get("jwt_token"),
            "thread_id": session_data.get("thread_id"),
            "project_id": session_data.get("project_id")
        }