"""
server/session_manager.py

Session isolation manager for SQLBench-OpenEnv.

Ensures each user/session has their own isolated environment instance.
No global shared episode state across users.

Architecture:
User A → Session A → Environment A (isolated)
User B → Session B → Environment B (isolated)
"""
import uuid
import time
from typing import Dict, Optional
from threading import Lock
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sql_query_env.environment import SQLQueryEnv


@dataclass
class Session:
    """Represents a user session with an isolated environment."""
    session_id: str
    env: SQLQueryEnv
    created_at: datetime
    last_activity: datetime
    user_id: Optional[str] = None
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired due to inactivity."""
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)


class SessionManager:
    """
    Manages isolated environment sessions.
    
    Thread-safe session management with automatic cleanup of expired sessions.
    """
    
    def __init__(self, session_timeout_minutes: int = 30):
        self.sessions: Dict[str, Session] = {}
        self.lock = Lock()
        self.session_timeout_minutes = session_timeout_minutes
    
    def create_session(
        self,
        user_id: Optional[str] = None,
        seed: int = 42
    ) -> str:
        """
        Create a new session with an isolated environment.
        
        Args:
            user_id: Optional user identifier
            seed: Random seed for reproducibility
        
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        env = SQLQueryEnv(seed=seed)
        
        session = Session(
            session_id=session_id,
            env=env,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            user_id=user_id,
        )
        
        with self.lock:
            self.sessions[session_id] = session
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Session object or None if not found
        """
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                session.update_activity()
            return session
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and cleanup its environment.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if session was deleted, False if not found
        """
        with self.lock:
            session = self.sessions.pop(session_id, None)
            if session:
                session.env.close()
                return True
            return False
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        with self.lock:
            expired_ids = [
                sid for sid, session in self.sessions.items()
                if session.is_expired(self.session_timeout_minutes)
            ]
            
            for sid in expired_ids:
                session = self.sessions.pop(sid)
                session.env.close()
            
            return len(expired_ids)
    
    def get_session_count(self) -> int:
        """Get the current number of active sessions."""
        with self.lock:
            return len(self.sessions)
    
    def get_all_sessions(self) -> Dict[str, Session]:
        """Get all sessions (for debugging/monitoring)."""
        with self.lock:
            return self.sessions.copy()


# Global session manager instance
session_manager = SessionManager(session_timeout_minutes=30)
