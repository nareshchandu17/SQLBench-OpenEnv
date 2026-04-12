"""
In-memory SQLite database manager.
Isolated per episode — no state leaks between resets.
"""
import sqlite3
import json
from typing import List, Dict, Optional, Tuple


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
        Execute the agent's query safely.
        Returns (results, None) on success, (None, error_message) on failure.
        """
        if not self._conn:
            return None, "Database not initialized. Call setup() first."
        
        # Safety: block destructive statements
        normalized = query.strip().upper()
        forbidden = ["DROP ", "DELETE ", "UPDATE ", "INSERT ", "ALTER ", "CREATE "]
        for keyword in forbidden:
            if normalized.startswith(keyword):
                return None, f"Action '{keyword.strip()}' is not permitted. Only SELECT queries allowed."
        
        try:
            cursor = self._conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            # Convert Row objects to plain dicts
            result = [dict(row) for row in rows]
            return result, None
        except sqlite3.Error as e:
            return None, str(e)
        except Exception as e:
            return None, f"Unexpected error: {str(e)}"
    
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