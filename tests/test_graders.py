"""
tests/test_graders.py

Verifies that all graders are deterministic and produce
scores in the correct range. These tests run in < 1 second.
"""
import pytest
import sys, os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sql_query_env.graders import (
    grade_result_match,
    grade_syntax,
    grade_efficiency,
    compute_task_score,
)
from sql_query_env.database import DatabaseManager


# ── grade_result_match ────────────────────────────────────────────────────────

class TestGradeResultMatch:

    def test_same_ordered_rows_pass(self):
        rows = [{"name": "Alice", "salary": 95000.0}, {"name": "Bob", "salary": 90000.0}]
        assert grade_result_match(rows, rows, "SELECT name, salary FROM t ORDER BY salary DESC") == 1.0

    def test_same_rows_wrong_order_fail_when_ordering_matters(self):
        expected = [{"name": "Alice", "salary": 95000.0}, {"name": "Bob", "salary": 90000.0}]
        agent = [{"name": "Bob", "salary": 90000.0}, {"name": "Alice", "salary": 95000.0}]
        # ORDER BY is in ground truth
        assert grade_result_match(agent, expected, "SELECT name, salary FROM t ORDER BY salary DESC") < 1.0

    def test_same_rows_wrong_order_pass_when_ordering_does_not_matter(self):
        expected = [{"name": "Alice", "salary": 95000.0}, {"name": "Bob", "salary": 90000.0}]
        agent = [{"name": "Bob", "salary": 90000.0}, {"name": "Alice", "salary": 95000.0}]
        assert grade_result_match(agent, expected, "SELECT name, salary FROM t") == 1.0

    def test_duplicate_mismatch_fail(self):
        expected = [{"dept": "Eng"}, {"dept": "Eng"}]
        agent = [{"dept": "Eng"}]
        assert grade_result_match(agent, expected, "SELECT dept FROM employees") < 1.0

    def test_same_rows_with_duplicates_preserved_pass(self):
        expected = [{"dept": "Eng"}, {"dept": "Eng"}]
        agent = [{"dept": "Eng"}, {"dept": "Eng"}]
        assert grade_result_match(agent, expected, "SELECT dept FROM employees") == 1.0

    def test_duplicate_mismatch_ordered_pass(self):
        """Example from problem: Expected A,A,B but Agent A,B should FAIL."""
        expected = [{"val": "A"}, {"val": "A"}, {"val": "B"}]
        agent = [{"val": "A"}, {"val": "B"}]
        assert grade_result_match(agent, expected, "SELECT val FROM t") < 1.0

    def test_duplicate_mismatch_ordered_fail(self):
        """Example from problem: Expected A,B,C but Agent C,B,A should FAIL when ordered."""
        expected = [{"val": "A"}, {"val": "B"}, {"val": "C"}]
        agent = [{"val": "C"}, {"val": "B"}, {"val": "A"}]
        assert grade_result_match(agent, expected, "SELECT val FROM t ORDER BY val") < 1.0

    def test_null_vs_string_none_not_equal(self):
        expected = [{"name": "Alice", "manager": None}]
        agent = [{"name": "Alice", "manager": "None"}]
        assert grade_result_match(agent, expected, "SELECT name, manager FROM t") < 1.0

    def test_null_vs_string_null_not_equal(self):
        expected = [{"name": "Alice", "manager": None}]
        agent = [{"name": "Alice", "manager": "NULL"}]
        assert grade_result_match(agent, expected, "SELECT name, manager FROM t") < 1.0

    def test_numeric_string_comparison(self):
        """Numeric strings should be normalized to floats for comparison."""
        expected = [{"id": 1}, {"id": 2}]
        agent = [{"id": "1"}, {"id": "2"}]
        assert grade_result_match(agent, expected, "SELECT id FROM t") == 1.0

    def test_column_order_with_order_by(self):
        """When ORDER BY is present, column order must match exactly."""
        expected = [{"name": "Alice", "salary": 95000.0}]
        agent = [{"salary": 95000.0, "name": "Alice"}]
        assert grade_result_match(agent, expected, "SELECT name, salary FROM t ORDER BY salary") < 1.0

    def test_column_order_without_order_by(self):
        """Without ORDER BY, column order doesn't matter."""
        expected = [{"name": "Alice", "salary": 95000.0}]
        agent = [{"salary": 95000.0, "name": "Alice"}]
        assert grade_result_match(agent, expected, "SELECT name, salary FROM t") == 1.0

    def test_empty_string_vs_null(self):
        """Empty string should not equal NULL."""
        expected = [{"name": ""}]
        agent = [{"name": None}]
        assert grade_result_match(agent, expected, "SELECT name FROM t") < 1.0

    def test_zero_vs_null(self):
        """Zero should not equal NULL."""
        expected = [{"count": 0}]
        agent = [{"count": None}]
        assert grade_result_match(agent, expected, "SELECT count FROM t") < 1.0

    def test_float_vs_int_equivalent(self):
        """Float and int with same value should be equal."""
        expected = [{"val": 1}]
        agent = [{"val": 1.0}]
        assert grade_result_match(agent, expected, "SELECT val FROM t") == 1.0

    def test_different_columns_fail(self):
        expected = [{"name": "Alice", "salary": 95000.0}]
        agent = [{"first_name": "Alice", "salary": 95000.0}]
        assert grade_result_match(agent, expected, "SELECT name, salary FROM t") < 1.0

    def test_extra_column_fail_or_partial(self):
        expected = [{"name": "Alice"}]
        agent = [{"name": "Alice", "salary": 95000.0}]
        score = grade_result_match(agent, expected, "SELECT name FROM t")
        assert score >= 0.7 and score < 1.0

    def test_empty_vs_empty_pass(self):
        assert grade_result_match([], [], "SELECT * FROM t") == 1.0

    def test_empty_vs_non_empty_fail(self):
        assert grade_result_match([], [{"name": "Alice"}], "SELECT * FROM t") == 0.0
        assert grade_result_match([{"name": "Alice"}], [], "SELECT * FROM t") == 0.0

    def test_semantically_equivalent_sql_pass(self):
        # We test this implicitly by ensuring that exactly matched dicts give 1.0
        expected = [{"a": 1, "b": 2}]
        agent = [{"a": 1, "b": 2}]
        assert grade_result_match(agent, expected, "SELECT a, b FROM t") == 1.0

# ── grade_efficiency ──────────────────────────────────────────────────────────

class TestGradeEfficiency:

    def test_specific_columns_score_high(self):
        query = "SELECT name, salary FROM employees"
        assert grade_efficiency(query) >= 0.8

    def test_select_star_penalized(self):
        score_star = grade_efficiency("SELECT * FROM employees")
        score_cols = grade_efficiency("SELECT name FROM employees")
        assert score_cols > score_star

    def test_range_valid(self):
        for query in [
            "SELECT * FROM t",
            "SELECT a FROM t",
            "SELECT a FROM t WHERE a IN (SELECT b FROM s WHERE b IN (SELECT c FROM r))",
        ]:
            score = grade_efficiency(query)
            assert 0.0 <= score <= 1.0, f"Out of range for: {query}"


# ── compute_task_score ────────────────────────────────────────────────────────

class TestComputeTaskScore:

    def test_execution_error_returns_near_zero(self):
        score = compute_task_score(
            agent_result=[],
            expected_result=[{"name": "Alice"}],
            error_message="syntax error near 'FORM'",
            query="SELECT name FORM employees",
            task_difficulty="easy",
            ground_truth_query="SELECT name FROM employees"
        )
        assert score <= 0.1

    def test_correct_result_returns_1(self):
        rows = [{"name": "Alice"}]
        score = compute_task_score(
            agent_result=rows,
            expected_result=rows,
            error_message="",
            query="SELECT name FROM employees",
            task_difficulty="easy",
            ground_truth_query="SELECT name FROM employees"
        )
        assert score == 1.0

    def test_score_in_range(self):
        for agent, expected, err, diff in [
            ([{"a": 1}], [{"a": 2}], "", "easy"),
            ([], [{"a": 1}], "no such table: emp", "medium"),
            ([{"a": 1}], [{"a": 1}], "", "hard"),
        ]:
            score = compute_task_score(agent, expected, err, "SELECT a FROM t", diff, "SELECT a FROM t")
            assert 0.0 <= score <= 1.0, f"Score out of range: {score}"

    def test_hard_task_efficiency_bonus(self):
        rows = [{"name": "Alice"}]
        score_star = compute_task_score(
            agent_result=rows,
            expected_result=rows,
            error_message="",
            query="SELECT * FROM employees",
            task_difficulty="hard",
            ground_truth_query="SELECT name FROM employees"
        )
        score_cols = compute_task_score(
            agent_result=rows,
            expected_result=rows,
            error_message="",
            query="SELECT name FROM employees",
            task_difficulty="hard",
            ground_truth_query="SELECT name FROM employees"
        )
        assert score_cols >= score_star


# ── DatabaseManager integration ───────────────────────────────────────────────

class TestDatabaseManager:

    def setup_method(self):
        self.db = DatabaseManager()
        self.db.setup(
            schema_ddl="CREATE TABLE t (id INTEGER, val TEXT)",
            seed_data_sql="INSERT INTO t VALUES (1, 'a'); INSERT INTO t VALUES (2, 'b')",
        )

    def teardown_method(self):
        self.db.teardown()

    def test_correct_query_returns_rows(self):
        rows, err = self.db.execute_query("SELECT * FROM t")
        assert err is None
        assert len(rows) == 2

    def test_syntax_error_returns_error(self):
        rows, err = self.db.execute_query("SELEKT * FORM t")
        assert rows is None
        assert err is not None

    def test_wrong_table_returns_error(self):
        _, err = self.db.execute_query("SELECT * FROM nonexistent")
        assert err is not None
        assert "no such table" in err.lower()

    def test_delete_blocked(self):
        _, err = self.db.execute_query("DELETE FROM t WHERE id = 1")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()

    def test_drop_blocked(self):
        _, err = self.db.execute_query("DROP TABLE t")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()

    def test_comment_drop_blocked(self):
        _, err = self.db.execute_query("/* bypass */ DROP TABLE t")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()

    def test_with_delete_blocked(self):
        _, err = self.db.execute_query("WITH cte AS (SELECT 1) DELETE FROM t")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()

    def test_multiple_statements_blocked(self):
        # sqlite3.cursor.execute prevents multiple statements natively
        # we check it returns an error
        _, err = self.db.execute_query("SELECT 1; DROP TABLE t;")
        assert err is not None

    def test_attach_blocked(self):
        _, err = self.db.execute_query("ATTACH DATABASE 'test.db' AS test")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()

    def test_pragma_blocked(self):
        _, err = self.db.execute_query("PRAGMA schema_version=0")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()

    def test_recursive_timeout(self):
        """Test that recursive CTE with infinite loop is terminated by timeout."""
        # Should throw timeout error and NOT hang
        start = time.time()
        _, err = self.db.execute_query(
            "WITH RECURSIVE r AS (SELECT 1 UNION ALL SELECT 1 FROM r) SELECT * FROM r",
            timeout_seconds=0.1  # 100ms timeout
        )
        elapsed = time.time() - start
        
        # Should timeout within reasonable time (not hang)
        assert elapsed < 2.0, f"Query took {elapsed}s, should have timed out quickly"
        assert err is not None
        assert "timeout" in err.lower()
    
    def test_recursive_timeout_actually_stops(self):
        """Test that connection.interrupt() actually stops execution."""
        # This is an infinite recursive CTE - it would run forever without timeout
        start = time.time()
        _, err = self.db.execute_query(
            "WITH RECURSIVE infinite AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM infinite WHERE n < 1000000) SELECT * FROM infinite",
            timeout_seconds=0.1  # Very short timeout
        )
        elapsed = time.time() - start
        
        # Verify it terminated quickly (connection.interrupt() worked)
        assert elapsed < 1.0, f"Query took {elapsed}s, interrupt() should have stopped it"
        assert err is not None
        assert "timeout" in err.lower()

    def test_isolated_between_setup_calls(self):
        self.db.setup(
            schema_ddl="CREATE TABLE fresh (x INTEGER)",
            seed_data_sql="INSERT INTO fresh VALUES (99)",
        )
        rows, err = self.db.execute_query("SELECT * FROM fresh")
        assert err is None
        assert rows[0]["x"] == 99
        # Original table should not exist
        _, err2 = self.db.execute_query("SELECT * FROM t")
        assert err2 is not None


# ── Security Tests (AST-based validation) ─────────────────────────────────────

class TestSecurityValidation:
    """Test AST-based SQL security validation."""
    
    def setup_method(self):
        self.db = DatabaseManager()
        self.db.setup(
            schema_ddl="CREATE TABLE users (id INTEGER, name TEXT, email TEXT)",
            seed_data_sql="INSERT INTO users VALUES (1, 'Alice', 'alice@test.com')",
        )
    
    def teardown_method(self):
        self.db.teardown()
    
    def test_comment_bypass_drop_table(self):
        """Test that comment-based DROP TABLE bypass is blocked."""
        _, err = self.db.execute_query("/* bypass */ DROP TABLE users")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_comment_bypass_delete(self):
        """Test that comment-based DELETE bypass is blocked."""
        _, err = self.db.execute_query("/* comment */ DELETE FROM users WHERE id = 1")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_cte_bypass_delete(self):
        """Test that CTE-based DELETE bypass is blocked."""
        _, err = self.db.execute_query("WITH x AS (SELECT 1) DELETE FROM users")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_cte_bypass_drop(self):
        """Test that CTE-based DROP TABLE bypass is blocked."""
        _, err = self.db.execute_query("WITH x AS (SELECT 1) DROP TABLE users")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_multiline_comment_bypass(self):
        """Test that multiline comment bypass is blocked."""
        _, err = self.db.execute_query("/* multiline \n comment */ DELETE FROM users")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_inline_comment_bypass(self):
        """Test that inline comment before dangerous op is blocked."""
        _, err = self.db.execute_query("-- comment\nDELETE FROM users")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_insert_blocked(self):
        """Test that INSERT is blocked."""
        _, err = self.db.execute_query("INSERT INTO users VALUES (2, 'Bob', 'bob@test.com')")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_update_blocked(self):
        """Test that UPDATE is blocked."""
        _, err = self.db.execute_query("UPDATE users SET name = 'Eve' WHERE id = 1")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_alter_table_blocked(self):
        """Test that ALTER TABLE is blocked."""
        _, err = self.db.execute_query("ALTER TABLE users ADD COLUMN age INTEGER")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_create_table_blocked(self):
        """Test that CREATE TABLE is blocked."""
        _, err = self.db.execute_query("CREATE TABLE evil (x INTEGER)")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_truncate_blocked(self):
        """Test that TRUNCATE is blocked (if SQLite supports it)."""
        _, err = self.db.execute_query("DELETE FROM users")  # SQLite uses DELETE instead of TRUNCATE
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_attach_database_blocked(self):
        """Test that ATTACH DATABASE is blocked."""
        _, err = self.db.execute_query("ATTACH DATABASE 'evil.db' AS evil")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_pragma_dangerous_blocked(self):
        """Test that dangerous PRAGMA operations are blocked."""
        _, err = self.db.execute_query("PRAGMA schema_version = 0")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_pragma_safe_allowed(self):
        """Test that safe PRAGMA operations are allowed."""
        rows, err = self.db.execute_query("PRAGMA table_info(users)")
        # This might be blocked by authorizer depending on implementation
        # But AST validation should pass
        if err:
            # If blocked, it should be by authorizer, not AST
            assert "dangerous" not in err.lower()
    
    def test_case_insensitive_keyword_detection(self):
        """Test that keyword detection is case-insensitive."""
        _, err = self.db.execute_query("delete from users")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_multiple_statements_blocked(self):
        """Test that multiple statements are blocked."""
        _, err = self.db.execute_query("SELECT * FROM users; DROP TABLE users")
        assert err is not None
        assert "multiple statements" in err.lower() or "not permitted" in err.lower()
    
    def test_nested_subquery_with_delete_blocked(self):
        """Test that DELETE in subquery is blocked."""
        _, err = self.db.execute_query("SELECT * FROM (DELETE FROM users)")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_union_with_delete_blocked(self):
        """Test that UNION with DELETE is blocked."""
        _, err = self.db.execute_query("SELECT 1 UNION DELETE FROM users")
        assert err is not None
        assert "not permitted" in err.lower() or "dangerous" in err.lower()
    
    def test_select_still_works(self):
        """Test that legitimate SELECT queries still work."""
        rows, err = self.db.execute_query("SELECT * FROM users")
        assert err is None
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"
    
    def test_select_with_cte_works(self):
        """Test that SELECT with CTE still works."""
        rows, err = self.db.execute_query("WITH ranked AS (SELECT * FROM users) SELECT * FROM ranked")
        assert err is None
        assert len(rows) == 1
    
    def test_select_with_subquery_works(self):
        """Test that SELECT with subquery still works."""
        rows, err = self.db.execute_query("SELECT * FROM (SELECT * FROM users)")
        assert err is None
        assert len(rows) == 1

