"""
tests/test_graders.py

Verifies that all graders are deterministic and produce
scores in the correct range. These tests run in < 1 second.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from env.graders import (
    grade_result_match,
    grade_syntax,
    grade_efficiency,
    compute_task_score,
)
from env.database import DatabaseManager


# ── grade_result_match ────────────────────────────────────────────────────────

class TestGradeResultMatch:

    def test_exact_match_returns_1(self):
        rows = [{"name": "Alice", "salary": 95000.0}]
        assert grade_result_match(rows, rows) == 1.0

    def test_both_empty_returns_1(self):
        assert grade_result_match([], []) == 1.0

    def test_agent_empty_expected_nonempty_returns_0(self):
        assert grade_result_match([], [{"name": "Alice"}]) == 0.0

    def test_expected_empty_agent_nonempty_returns_0(self):
        assert grade_result_match([{"name": "Alice"}], []) == 0.0

    def test_wrong_column_returns_partial(self):
        agent   = [{"name": "Alice"}]
        expected = [{"name": "Alice", "salary": 95000.0}]
        score = grade_result_match(agent, expected)
        assert 0.5 <= score <= 0.9

    def test_correct_rows_extra_column_returns_high(self):
        agent    = [{"name": "Alice", "salary": 95000.0, "extra": 1}]
        expected = [{"name": "Alice", "salary": 95000.0}]
        score = grade_result_match(agent, expected)
        assert score >= 0.7

    def test_wrong_values_returns_low(self):
        agent    = [{"name": "Wrong", "salary": 0.0}]
        expected = [{"name": "Alice", "salary": 95000.0}]
        score = grade_result_match(agent, expected)
        assert score < 0.5

    def test_partial_row_overlap(self):
        agent    = [{"name": "Alice"}, {"name": "Wrong"}]
        expected = [{"name": "Alice"}, {"name": "Bob"}]
        score = grade_result_match(agent, expected)
        assert 0.0 < score < 1.0

    def test_deterministic_same_inputs(self):
        rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        s1 = grade_result_match(rows, rows)
        s2 = grade_result_match(rows, rows)
        assert s1 == s2 == 1.0

    def test_order_independent(self):
        agent    = [{"name": "Bob"}, {"name": "Alice"}]
        expected = [{"name": "Alice"}, {"name": "Bob"}]
        assert grade_result_match(agent, expected) == 1.0


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
        )
        assert score == 1.0

    def test_score_in_range(self):
        for agent, expected, err, diff in [
            ([{"a": 1}], [{"a": 2}], "", "easy"),
            ([], [{"a": 1}], "no such table: emp", "medium"),
            ([{"a": 1}], [{"a": 1}], "", "hard"),
        ]:
            score = compute_task_score(agent, expected, err, "SELECT a FROM t", diff)
            assert 0.0 <= score <= 1.0, f"Score out of range: {score}"

    def test_hard_task_efficiency_bonus(self):
        rows = [{"name": "Alice"}]
        score_star = compute_task_score(
            agent_result=rows,
            expected_result=rows,
            error_message="",
            query="SELECT * FROM employees",
            task_difficulty="hard",
        )
        score_cols = compute_task_score(
            agent_result=rows,
            expected_result=rows,
            error_message="",
            query="SELECT name FROM employees",
            task_difficulty="hard",
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
        assert "not permitted" in err.lower()

    def test_drop_blocked(self):
        _, err = self.db.execute_query("DROP TABLE t")
        assert err is not None

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