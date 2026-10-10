"""
SQL security validation using AST-based parsing and SQLite authorizer.
Provides defense-in-depth against SQL injection and unauthorized operations.
"""
import sqlparse
from sqlparse import tokens as T
from typing import List, Tuple, Optional
import sqlite3


# Dangerous SQL operation types that are never allowed
DANGEROUS_STATEMENT_TYPES = {
    'INSERT',
    'UPDATE',
    'DELETE',
    'DROP',
    'ALTER',
    'CREATE',  # Allow only during setup, not during agent queries
    'TRUNCATE',
    'REPLACE',
    'MERGE',
    'CALL',
    'EXECUTE',
    'EXEC',
    'GRANT',
    'REVOKE',
    'ANALYZE',
    'VACUUM',
    'DETACH',
}

# Dangerous PRAGMA operations
DANGEROUS_PRAGMA = {
    'schema_version',
    'user_version',
    'application_id',
    'compile_options',
    'wal_checkpoint',
    'wal_autocheckpoint',
    'synchronous',
    'journal_mode',
    'page_size',
    'cache_size',
    'temp_store',
    'locking_mode',
}


def is_comment_token(token) -> bool:
    """Check if a token is a comment."""
    return token.ttype in (T.Comment.Single, T.Comment.Multiline, T.Comment.Special)


def is_whitespace_token(token) -> bool:
    """Check if a token is whitespace."""
    return token.ttype in (T.Whitespace, T.Whitespace.Newline, T.Whitespace.Space)


def validate_sql_ast(query: str) -> Tuple[bool, Optional[str]]:
    """
    Validate SQL using AST-based parsing.
    
    This is the first line of defense - validates at the SQL text level
    before any execution attempt.
    
    Returns:
        (is_valid, error_message)
    """
    if not query or not query.strip():
        return False, "Empty query"
    
    try:
        # Parse the SQL into statements
        statements = sqlparse.parse(query)
        
        if not statements:
            return False, "Invalid SQL syntax"
        
        # Check each statement
        for stmt in statements:
            # Get the first non-comment, non-whitespace token (usually the statement type)
            first_keyword = None
            for token in stmt.flatten():
                if not is_whitespace_token(token) and not is_comment_token(token):
                    first_keyword = token.value.upper()
                    break
            
            if first_keyword is None:
                continue
            
            # Check if this is a dangerous statement type
            if first_keyword in DANGEROUS_STATEMENT_TYPES:
                return False, f"Dangerous operation not permitted: {first_keyword}"
            
            # Special handling for PRAGMA
            if first_keyword == 'PRAGMA':
                # Extract the pragma name
                tokens = [t for t in stmt.flatten() if not is_whitespace_token(t) and not is_comment_token(t)]
                if len(tokens) >= 2:
                    pragma_name = tokens[1].value.lower().strip('\'"')
                    if pragma_name in DANGEROUS_PRAGMA:
                        return False, f"Dangerous PRAGMA operation not permitted: {pragma_name}"
            
            # Check for ATTACH DATABASE
            if 'ATTACH' in first_keyword:
                return False, "ATTACH DATABASE is not permitted"
            
            # Check for nested statements in subqueries that might hide dangerous ops
            # We recursively check all tokens for dangerous keywords
            for token in stmt.flatten():
                if token.ttype in T.Keyword:
                    token_upper = token.value.upper()
                    if token_upper in DANGEROUS_STATEMENT_TYPES:
                        return False, f"Dangerous operation detected in query: {token_upper}"
        
        return True, None
        
    except Exception as e:
        return False, f"SQL parsing error: {str(e)}"


def create_sandbox_authorizer() -> callable:
    """
    Create a SQLite authorizer callback for runtime protection.
    
    This is the second line of defense - validates at the SQLite execution level.
    Even if AST validation is bypassed, this will block unauthorized operations.
    """
    def authorizer(action: int, arg1: str, arg2: str, dbname: str, source: str) -> int:
        """
        SQLite authorizer callback.
        
        Returns SQLITE_DENY for unauthorized operations, SQLITE_OK otherwise.
        """
        # Define safe operations
        safe_actions = {
            sqlite3.SQLITE_SELECT,           # SELECT statements
            sqlite3.SQLITE_READ,             # Reading from tables/views
            sqlite3.SQLITE_FUNCTION,         # SQL functions
            sqlite3.SQLITE_TRANSACTION,      # Transaction control (read-only)
            # Recursive CTEs require this
            getattr(sqlite3, "SQLITE_RECURSIVE", 33),
        }
        
        # Allow these specific actions for CTEs and subqueries
        if action in safe_actions:
            return sqlite3.SQLITE_OK
        
        # Block all write operations
        if action in {
            sqlite3.SQLITE_INSERT,
            sqlite3.SQLITE_UPDATE,
            sqlite3.SQLITE_DELETE,
            sqlite3.SQLITE_CREATE_TABLE,
            sqlite3.SQLITE_CREATE_TEMP_TABLE,
            sqlite3.SQLITE_CREATE_VIEW,
            sqlite3.SQLITE_CREATE_TEMP_VIEW,
            sqlite3.SQLITE_CREATE_INDEX,
            sqlite3.SQLITE_CREATE_TRIGGER,
            sqlite3.SQLITE_DROP_TABLE,
            sqlite3.SQLITE_DROP_TEMP_TABLE,
            sqlite3.SQLITE_DROP_VIEW,
            sqlite3.SQLITE_DROP_TEMP_VIEW,
            sqlite3.SQLITE_DROP_INDEX,
            sqlite3.SQLITE_DROP_TRIGGER,
            sqlite3.SQLITE_ALTER_TABLE,
            sqlite3.SQLITE_REINDEX,
            sqlite3.SQLITE_ANALYZE,
            sqlite3.SQLITE_CREATE_VTABLE,
            sqlite3.SQLITE_DROP_VTABLE,
            sqlite3.SQLITE_DETACH,
            sqlite3.SQLITE_ATTACH,
        }:
            return sqlite3.SQLITE_DENY
        
        # Block PRAGMA operations (except safe ones)
        if action == sqlite3.SQLITE_PRAGMA:
            # Allow read-only pragmas
            if arg1 and arg1.lower() in ('table_info', 'table_list', 'column_list'):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        
        # Block transaction operations that could lead to writes
        if action in (sqlite3.SQLITE_TRANSACTION,):
            # Only allow BEGIN transactions (read-only)
            if arg1 and arg1.upper() in ('BEGIN', 'DEFERRED', 'IMMEDIATE'):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        
        # Default: deny unknown actions (fail-safe)
        return sqlite3.SQLITE_DENY
    
    return authorizer


def is_query_safe(query: str) -> Tuple[bool, Optional[str]]:
    """
    Comprehensive safety check combining AST validation and execution-time protection.
    
    Args:
        query: SQL query to validate
        
    Returns:
        (is_safe, error_message)
    """
    # Layer 1: AST-based validation
    is_valid, error = validate_sql_ast(query)
    if not is_valid:
        return False, error
    
    # Layer 2: Check for multiple statements (potential for injection)
    statements = sqlparse.parse(query)
    if len(statements) > 1:
        return False, "Multiple statements not permitted"
    
    return True, None
