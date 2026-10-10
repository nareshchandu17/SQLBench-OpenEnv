"""
In-memory SQLite database manager.
Isolated per episode — no state leaks between resets.
"""
import sqlite3
import json
import time
from typing import List, Dict, Optional, Tuple
from .security import is_query_safe, create_sandbox_authorizer


class DatabaseManager:
    """
    Creates a fresh in-memory SQLite database for each task.
    Runs the agent's query and returns results or error messages.
    """
    
    def __init__(self):
        self._conn: Optional[sqlite3.Connection] = None
    
    def setup(self, schema_ddl: str, seed_data_sql: str) -> None:
        """
        Initialize a fresh in-memory database with the given schema and data.
        Called by environment.reset().
        """
        if self._conn:
            self._conn.close()
        
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row
        
        cursor = self._conn.cursor()
        # Execute each statement (schema may have multiple CREATE TABLE)
        for statement in schema_ddl.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                cursor.execute(stmt)
        
        # Seed with test data
        for statement in seed_data_sql.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                cursor.execute(stmt)
        
        self._conn.commit()
    
    def execute_query(
        self, query: str, timeout_seconds: int = 5
    ) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """
        Execute the agent's query safely with defense-in-depth security.
        
        Security layers:
        1. AST-based SQL validation (pre-execution)
        2. SQLite authorizer callback (runtime protection)
        3. Real timeout handler with connection.interrupt() (prevents infinite loops)
        
        The timeout mechanism uses SQLite's progress handler which is called every N
        virtual machine instructions. When timeout is exceeded, connection.interrupt()
        is called to actually stop execution, not just return an error.
        
        Returns (results, None) on success, (None, error_message) on failure.
        """
        if not self._conn:
            return None, "Database not initialized. Call setup() first."
        
        # Layer 1: AST-based validation
        is_safe, security_error = is_query_safe(query)
        if not is_safe:
            return None, security_error
        
        # Layer 2: SQLite authorizer for runtime protection
        authorizer = create_sandbox_authorizer()
        
        # Layer 3: Real timeout with progress handler and connection.interrupt()
        start_time = time.time()
        timeout_triggered = False
        
        def progress_handler():
            """
            Progress handler called by SQLite every N virtual machine instructions.
            Returns non-zero to interrupt execution.
            """
            nonlocal timeout_triggered
            if time.time() - start_time > timeout_seconds:
                timeout_triggered = True
                # Trigger interrupt to actually stop execution
                self._conn.interrupt()
                return 1  # Return non-zero to signal interrupt
            return 0

        # Enable sandbox restrictions
        self._conn.set_authorizer(authorizer)
        # Call progress handler every 1000 VM instructions for frequent checks
        self._conn.set_progress_handler(progress_handler, 1000)
        
        try:
            cursor = self._conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            # Convert Row objects to plain dicts
            result = [dict(row) for row in rows]
            return result, None
        except sqlite3.Error as e:
            err_msg = str(e)
            if "not authorized" in err_msg.lower():
                return None, "Action is not permitted. Only SELECT queries allowed."
            if "interrupted" in err_msg.lower() or timeout_triggered:
                return None, f"Query execution exceeded {timeout_seconds}s timeout."
            return None, err_msg
        except Exception as e:
            return None, f"Unexpected error: {str(e)}"
        finally:
            # Disable sandbox restrictions
            self._conn.set_authorizer(None)
            self._conn.set_progress_handler(None, 0)
    
    def get_reference_result(self, ground_truth_query: str) -> List[Dict]:
        """
        Execute the ground truth query to get the expected result.
        Called during task initialization, not exposed to agent.
        """
        results, error = self.execute_query(ground_truth_query)
        if error:
            raise ValueError(
                f"Ground truth query failed — check task definition: {error}"
            )
        return results or []
    
    def teardown(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None