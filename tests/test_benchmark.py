"""
tests/test_benchmark.py

Tests for the benchmark layer:
- BenchmarkRunner produces valid structured output
- Leaderboard JSON has correct schema
- Error taxonomy classification is deterministic
- generate_leaderboard writes valid files
"""
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from benchmark.runner import BenchmarkRunner, ModelResult, TaskResult
from benchmark.leaderboard import generate_leaderboard, print_leaderboard
from benchmark.error_taxonomy import (
    classify_error,
    ErrorCounts,
    ERROR_CATEGORIES,
)


# ── Error taxonomy ────────────────────────────────────────────────────────────

class TestClassifyError:

    def test_success_when_score_1(self):
        cat = classify_error(
            error_message="",
            agent_result=[{"a": 1}],
            expected_result=[{"a": 1}],
            query="SELECT a FROM t",
            episode_score=1.0,
        )
        assert cat == "success"

    def test_syntax_error_on_execution_failure(self):
        cat = classify_error(
            error_message="syntax error near 'FORM'",
            agent_result=None,
            expected_result=[{"a": 1}],
            query="SELEKT a FORM t",
            episode_score=0.0,
        )
        assert cat == "syntax_error"

    def test_reference_error_on_no_such_table(self):
        cat = classify_error(
            error_message="no such table: employes",
            agent_result=None,
            expected_result=[{"a": 1}],
            query="SELECT a FROM employes",
            episode_score=0.0,
        )
        assert cat == "reference_error"

    def test_join_error_detected(self):
        cat = classify_error(
            error_message="",
            agent_result=[{"name": "Wrong"}],
            expected_result=[{"name": "Alice"}],
            query="SELECT c.name FROM customers c JOIN orders o ON c.id = o.id",
            episode_score=0.1,
        )
        assert cat == "join_error"

    def test_aggregation_error_detected(self):
        cat = classify_error(
            error_message="",
            agent_result=[{"region": "North", "total": 100}],
            expected_result=[{"region": "South", "total": 200}],
            query="SELECT region, SUM(val) FROM t GROUP BY product HAVING SUM(val) > 50",
            episode_score=0.0,
        )
        assert cat == "aggregation_error"

    def test_logic_error_on_wrong_data_no_error(self):
        cat = classify_error(
            error_message="",
            agent_result=[{"name": "Wrong"}],
            expected_result=[{"name": "Alice"}],
            query="SELECT name FROM employees WHERE dept = 'HR'",
            episode_score=0.0,
        )
        assert cat == "logic_error"

    def test_all_categories_are_valid(self):
        for cat in ERROR_CATEGORIES:
            assert isinstance(cat, str)
            assert len(cat) > 0

    def test_deterministic_same_call_twice(self):
        kwargs = dict(
            error_message="no such table: emp",
            agent_result=None,
            expected_result=[{"a": 1}],
            query="SELECT a FROM emp",
            episode_score=0.0,
        )
        assert classify_error(**kwargs) == classify_error(**kwargs)


class TestErrorCounts:

    def test_add_increments_total(self):
        ec = ErrorCounts()
        ec.add("syntax_error")
        ec.add("success")
        assert ec.total == 2

    def test_add_increments_specific_field(self):
        ec = ErrorCounts()
        ec.add("syntax_error")
        ec.add("syntax_error")
        assert ec.syntax_error == 2

    def test_to_dict_returns_rates(self):
        ec = ErrorCounts()
        ec.add("success")
        ec.add("syntax_error")
        d = ec.to_dict()
        assert abs(d["success"] - 0.5) < 0.001
        assert abs(d["syntax_error"] - 0.5) < 0.001

    def test_to_dict_empty_returns_zeros(self):
        ec = ErrorCounts()
        d = ec.to_dict()
        for cat in ERROR_CATEGORIES:
            assert d[cat] == 0.0

    def test_to_dict_has_all_categories(self):
        ec = ErrorCounts()
        d = ec.to_dict()
        for cat in ERROR_CATEGORIES:
            assert cat in d

    def test_rates_sum_to_1(self):
        ec = ErrorCounts()
        for cat in ERROR_CATEGORIES:
            ec.add(cat)
        d = ec.to_dict()
        total = sum(d.values())
        assert abs(total - 1.0) < 0.001


# ── ModelResult ───────────────────────────────────────────────────────────────

class TestModelResult:

    def _make_result(self) -> ModelResult:
        mr = ModelResult(model_id="test-model", model_name="Test Model")
        mr.task_results = [
            TaskResult("fix_syntax_simple",      "easy",   0.9, 2, True,  "success",     0.85, 1.2),
            TaskResult("fix_table_name",          "easy",   0.8, 3, True,  "success",     0.75, 1.5),
            TaskResult("fix_join_logic",          "medium", 0.5, 5, False, "join_error",  0.4,  2.1),
            TaskResult("fix_aggregate_logic",     "medium", 0.4, 5, False, "agg_error",   0.3,  2.3),
            TaskResult("multi_constraint_query",  "hard",   0.2, 5, False, "logic_error", 0.1,  3.0),
        ]
        return mr

    def test_average_score_correct(self):
        mr = self._make_result()
        avg = mr.average_score()
        expected = (0.9 + 0.8 + 0.5 + 0.4 + 0.2) / 5
        assert abs(avg - expected) < 0.001

    def test_score_by_difficulty(self):
        mr = self._make_result()
        by_diff = mr.score_by_difficulty()
        assert "easy" in by_diff
        assert "medium" in by_diff
        assert "hard" in by_diff
        assert abs(by_diff["easy"] - 0.85) < 0.001
        assert abs(by_diff["medium"] - 0.45) < 0.001
        assert abs(by_diff["hard"] - 0.2) < 0.001

    def test_empty_model_result_average(self):
        mr = ModelResult(model_id="x", model_name="X")
        assert mr.average_score() == 0.0

    def test_empty_score_by_difficulty(self):
        mr = ModelResult(model_id="x", model_name="X")
        assert mr.score_by_difficulty() == {}


# ── generate_leaderboard ──────────────────────────────────────────────────────

class TestGenerateLeaderboard:

    def _make_results(self) -> list:
        mr1 = ModelResult(model_id="model-a", model_name="Model A")
        mr1.task_results = [
            TaskResult("fix_syntax_simple", "easy",   0.9, 2, True,  "success",    0.8, 1.0),
            TaskResult("fix_join_logic",     "medium", 0.6, 4, False, "join_error", 0.5, 2.0),
            TaskResult("multi_constraint_query", "hard", 0.3, 5, False, "logic_error", 0.2, 3.0),
        ]
        mr1.error_counts.add("success")
        mr1.error_counts.add("join_error")
        mr1.error_counts.add("logic_error")

        mr2 = ModelResult(model_id="model-b", model_name="Model B")
        mr2.task_results = [
            TaskResult("fix_syntax_simple", "easy",   0.7, 3, False, "syntax_error", 0.6, 1.2),
            TaskResult("fix_join_logic",     "medium", 0.4, 5, False, "logic_error",  0.3, 2.5),
            TaskResult("multi_constraint_query", "hard", 0.1, 5, False, "logic_error", 0.05, 3.5),
        ]
        mr2.error_counts.add("syntax_error")
        mr2.error_counts.add("logic_error")
        mr2.error_counts.add("logic_error")

        return [mr1, mr2]

    def test_writes_three_json_files(self):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_leaderboard(results, output_dir=tmpdir)
            files = os.listdir(tmpdir)
            assert "benchmark_results.json" in files
            assert "leaderboard.json" in files
            assert "error_taxonomy.json" in files

    def test_leaderboard_json_valid_structure(self):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            lb = generate_leaderboard(results, output_dir=tmpdir)
            assert "rankings" in lb
            assert "benchmark" in lb
            assert lb["benchmark"] == "SQLBench-OpenEnv"

    def test_leaderboard_sorted_by_average(self):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            lb = generate_leaderboard(results, output_dir=tmpdir)
            avgs = [e["average"] for e in lb["rankings"]]
            assert avgs == sorted(avgs, reverse=True)

    def test_leaderboard_ranks_assigned(self):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            lb = generate_leaderboard(results, output_dir=tmpdir)
            ranks = [e["rank"] for e in lb["rankings"]]
            assert ranks == list(range(1, len(ranks) + 1))

    def test_leaderboard_has_difficulty_scores(self):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            lb = generate_leaderboard(results, output_dir=tmpdir)
            for entry in lb["rankings"]:
                assert "easy" in entry
                assert "medium" in entry
                assert "hard" in entry
                assert "average" in entry

    def test_benchmark_results_json_valid(self):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_leaderboard(results, output_dir=tmpdir)
            with open(os.path.join(tmpdir, "benchmark_results.json")) as f:
                data = json.load(f)
            assert "models" in data
            assert len(data["models"]) == 2
            for m in data["models"]:
                assert "model_id" in m
                assert "tasks" in m
                for t in m["tasks"]:
                    assert 0.0 <= t["score"] <= 1.0

    def test_error_taxonomy_json_valid(self):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_leaderboard(results, output_dir=tmpdir)
            with open(os.path.join(tmpdir, "error_taxonomy.json")) as f:
                data = json.load(f)
            assert "models" in data
            for model_id, info in data["models"].items():
                rates = info["error_rates"]
                for cat in ERROR_CATEGORIES:
                    assert cat in rates
                    assert 0.0 <= rates[cat] <= 1.0

    def test_scores_in_valid_range(self):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            lb = generate_leaderboard(results, output_dir=tmpdir)
            for entry in lb["rankings"]:
                assert 0.0 <= entry["easy"] <= 1.0
                assert 0.0 <= entry["medium"] <= 1.0
                assert 0.0 <= entry["hard"] <= 1.0
                assert 0.0 <= entry["average"] <= 1.0

    def test_print_leaderboard_runs_without_error(self, capsys):
        results = self._make_results()
        with tempfile.TemporaryDirectory() as tmpdir:
            lb = generate_leaderboard(results, output_dir=tmpdir)
            print_leaderboard(lb)
            captured = capsys.readouterr()
            assert "Model A" in captured.out or "model-a" in captured.out