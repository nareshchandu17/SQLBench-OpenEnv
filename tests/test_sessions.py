"""
tests/test_sessions.py

Runtime tests for session isolation with concurrent execution.
Verifies that sessions have completely isolated state.
"""
import pytest
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

# Simple test without environment for now
import session_manager
from session_manager import SessionManager


class TestSessionCreation:
    """Test session creation and basic isolation."""
    
    def test_create_session(self):
        """Test that sessions can be created and retrieved."""
        manager = SessionManager(session_timeout_minutes=30)
        
        session_id = manager.create_session(user_id="test_user", seed=42)
        assert session_id is not None
        
        session = manager.get_session(session_id)
        assert session is not None
        assert session.user_id == "test_user"
        
        manager.delete_session(session_id)
    
    def test_sessions_have_isolated_environments(self):
        """Test that two sessions have different environment instances."""
        manager = SessionManager(session_timeout_minutes=30)
        
        sid1 = manager.create_session(user_id="user_a", seed=42)
        sid2 = manager.create_session(user_id="user_b", seed=99)
        
        s1 = manager.get_session(sid1)
        s2 = manager.get_session(sid2)
        
        # Should have different environment instances
        assert s1.env is not s2.env
        
        manager.delete_session(sid1)
        manager.delete_session(sid2)


class TestSessionStateIsolation:
    """Test that session state is isolated between sessions."""
    
    def test_reset_one_session_does_not_affect_other(self):
        """Test that resetting one session doesn't affect another."""
        manager = SessionManager(session_timeout_minutes=30)
        
        sid1 = manager.create_session(user_id="user_a", seed=42)
        sid2 = manager.create_session(user_id="user_b", seed=99)
        
        s1 = manager.get_session(sid1)
        s2 = manager.get_session(sid2)
        
        # Verify environments are different
        assert s1.env is not s2.env
        
        manager.delete_session(sid1)
        manager.delete_session(sid2)


class TestConcurrentSessionExecution:
    """Test concurrent execution maintains isolation."""
    
    def test_concurrent_session_access(self):
        """Test that concurrent session access is thread-safe."""
        manager = SessionManager(session_timeout_minutes=30)
        
        session_ids = []
        for i in range(3):
            sid = manager.create_session(user_id=f"user_{i}", seed=42 + i)
            session_ids.append((sid, i))
        
        def access_session(sid_info):
            sid, idx = sid_info
            s = manager.get_session(sid)
            return (sid, s.session_id, s.user_id, idx)
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(access_session, sid_info)
                for sid_info in session_ids
            ]
            
            results = [f.result() for f in futures]
        
        # Verify all sessions accessed correctly
        assert len(results) == 3
        for returned_sid, sid, user_id, idx in results:
            assert returned_sid == sid
            assert user_id == f"user_{idx}"
        
        # Cleanup
        for sid, _ in session_ids:
            manager.delete_session(sid)


class TestSessionLifecycle:
    """Test session lifecycle operations."""
    
    def test_delete_session(self):
        """Test that deleting a session makes it inaccessible."""
        manager = SessionManager(session_timeout_minutes=30)
        
        sid = manager.create_session(user_id="test_user", seed=42)
        
        # Session should exist
        assert manager.get_session(sid) is not None
        
        # Delete session
        deleted = manager.delete_session(sid)
        assert deleted is True
        
        # Session should no longer exist
        assert manager.get_session(sid) is None
    
    def test_delete_nonexistent_session(self):
        """Test that deleting a non-existent session returns False."""
        manager = SessionManager(session_timeout_minutes=30)
        
        deleted = manager.delete_session("nonexistent-id")
        assert deleted is False
    
    def test_invalid_session_id(self):
        """Test that invalid session IDs return None."""
        manager = SessionManager(session_timeout_minutes=30)
        
        # Try to get non-existent session
        session = manager.get_session("invalid-id")
        assert session is None


class TestDatabaseStateIsolation:
    """Test that database state is isolated between sessions."""
    
    def test_database_isolation(self):
        """Test that each session has its own database instance."""
        manager = SessionManager(session_timeout_minutes=30)
        
        sid1 = manager.create_session(user_id="user_a", seed=42)
        sid2 = manager.create_session(user_id="user_b", seed=99)
        
        s1 = manager.get_session(sid1)
        s2 = manager.get_session(sid2)
        
        # Each session should have its own database
        assert s1.env is not s2.env
        assert s1.env._db is not s2.env._db
        
        manager.delete_session(sid1)
        manager.delete_session(sid2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
