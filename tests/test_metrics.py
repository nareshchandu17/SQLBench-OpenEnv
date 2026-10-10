"""
tests/test_metrics.py

Runtime tests for enhanced evaluation metrics.
Tests percentile calculation, confidence intervals, and metrics summary.
"""
import pytest
import sys
import os
from dataclasses import dataclass, field
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "benchmark"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from metrics import (
    calculate_percentile,
    calculate_ci_95_mean,
    calculate_ci_95_proportion,
    compute_metrics_summary,
    MetricsSummary,
)


# Minimal TaskResult for testing (avoid importing benchmark/runner which requires dotenv)
@dataclass
class TaskResult:
    task_id: str
    difficulty: str
    episode_score: float
    steps_taken: int
    solved: bool
    error_category: str
    total_reward: float
    duration_seconds: float
    api_errors: List[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    rate_limit_errors: int = 0
    timeout_errors: int = 0
    auth_errors: int = 0
    provider_errors: int = 0


class TestPercentileCalculation:
    """Test percentile calculation with linear interpolation."""

    def test_p50_median(self):
        """Test P50 calculates median correctly."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        p50 = calculate_percentile(values, 50)
        assert p50 == 3.0

    def test_p95_high_percentile(self):
        """Test P95 calculates high percentile correctly."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        p95 = calculate_percentile(values, 95)
        # 95th percentile of 10 values: index = 0.95 * 9 = 8.55
        # Between values[8] = 9.0 and values[9] = 10.0
        # Linear interpolation: 9.0 + 0.55 * (10.0 - 9.0) = 9.55
        assert 9.0 <= p95 <= 10.0

    def test_empty_values(self):
        """Test empty list returns 0.0."""
        assert calculate_percentile([], 50) == 0.0

    def test_single_value(self):
        """Test single value returns that value."""
        assert calculate_percentile([5.0], 50) == 5.0


class TestConfidenceIntervals:
    """Test 95% confidence interval calculations."""

    def test_ci_95_mean(self):
        """Test CI for mean with multiple samples."""
        values = [0.5, 0.6, 0.7, 0.8, 0.9]
        ci = calculate_ci_95_mean(values)
        assert ci is not None
        assert ci > 0.0  # Should have some margin of error

    def test_ci_95_mean_single_sample(self):
        """Test CI for mean with single sample returns None."""
        assert calculate_ci_95_mean([0.5]) is None

    def test_ci_95_proportion(self):
        """Test CI for proportion with Wilson score interval."""
        # 8 successes out of 10 trials
        ci = calculate_ci_95_proportion(8, 10)
        assert ci is not None
        assert ci > 0.0
        assert ci < 0.5  # Should be reasonable margin

    def test_ci_95_proportion_zero_trials(self):
        """Test CI for proportion with zero trials returns None."""
        assert calculate_ci_95_proportion(0, 0) is None

    def test_ci_95_proportion_single_trial(self):
        """Test CI for proportion with single trial returns None."""
        assert calculate_ci_95_proportion(1, 1) is None


class TestMetricsSummary:
    """Test comprehensive metrics summary computation."""

    def test_empty_task_results(self):
        """Test empty task results returns zeroed summary."""
        summary = compute_metrics_summary("test_id", "Test Model", [])
        assert summary.total_tasks == 0
        assert summary.solve_rate == 0.0
        assert summary.average_score == 0.0

    def test_basic_metrics(self):
        """Test basic metrics computation."""
        task_results = [
            TaskResult(
                task_id="task1",
                difficulty="easy",
                episode_score=1.0,
                steps_taken=1,
                solved=True,
                error_category="success",
                total_reward=1.0,
                duration_seconds=1.0,
                api_errors=[],
            ),
            TaskResult(
                task_id="task2",
                difficulty="medium",
                episode_score=0.5,
                steps_taken=2,
                solved=False,
                error_category="logic_error",
                total_reward=0.5,
                duration_seconds=2.0,
                api_errors=[],
            ),
        ]

        summary = compute_metrics_summary("test_id", "Test Model", task_results)

        assert summary.total_tasks == 2
        assert summary.solved_count == 1
        assert summary.solve_rate == 0.5
        assert summary.average_score == 0.75
        assert summary.easy_count == 1
        assert summary.medium_count == 1
        assert summary.hard_count == 0

    def test_latency_percentiles(self):
        """Test latency percentile calculation."""
        task_results = [
            TaskResult(
                task_id="task1",
                difficulty="easy",
                episode_score=1.0,
                steps_taken=1,
                solved=True,
                error_category="success",
                total_reward=1.0,
                duration_seconds=1.0,
                api_errors=[],
            ),
            TaskResult(
                task_id="task2",
                difficulty="easy",
                episode_score=1.0,
                steps_taken=1,
                solved=True,
                error_category="success",
                total_reward=1.0,
                duration_seconds=5.0,
                api_errors=[],
            ),
            TaskResult(
                task_id="task3",
                difficulty="easy",
                episode_score=1.0,
                steps_taken=1,
                solved=True,
                error_category="success",
                total_reward=1.0,
                duration_seconds=10.0,
                api_errors=[],
            ),
        ]

        summary = compute_metrics_summary("test_id", "Test Model", task_results)

        assert summary.avg_latency == 5.333333333333333
        assert summary.p50_latency == 5.0  # Median
        # P95 with linear interpolation: 9.5 for 3 values [1, 5, 10]
        assert summary.p95_latency == 9.5
        assert summary.max_latency == 10.0

    def test_token_usage_tracking(self):
        """Test token usage aggregation."""
        task_results = [
            TaskResult(
                task_id="task1",
                difficulty="easy",
                episode_score=1.0,
                steps_taken=1,
                solved=True,
                error_category="success",
                total_reward=1.0,
                duration_seconds=1.0,
                api_errors=[],
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost_usd=0.0001,
            ),
            TaskResult(
                task_id="task2",
                difficulty="easy",
                episode_score=1.0,
                steps_taken=1,
                solved=True,
                error_category="success",
                total_reward=1.0,
                duration_seconds=1.0,
                api_errors=[],
                input_tokens=200,
                output_tokens=100,
                total_tokens=300,
                cost_usd=0.0002,
            ),
        ]

        summary = compute_metrics_summary("test_id", "Test Model", task_results)

        assert summary.total_input_tokens == 300
        assert summary.total_output_tokens == 150
        assert summary.total_tokens == 450
        assert summary.avg_tokens_per_task == 225.0
        assert abs(summary.total_cost_usd - 0.0003) < 1e-9
        assert abs(summary.avg_cost_per_task - 0.00015) < 1e-9

    def test_failure_rate_tracking(self):
        """Test failure rate and error tracking."""
        task_results = [
            TaskResult(
                task_id="task1",
                difficulty="easy",
                episode_score=1.0,
                steps_taken=1,
                solved=True,
                error_category="success",
                total_reward=1.0,
                duration_seconds=1.0,
                api_errors=[],
                rate_limit_errors=0,
                timeout_errors=0,
                auth_errors=0,
                provider_errors=0,
            ),
            TaskResult(
                task_id="task2",
                difficulty="easy",
                episode_score=0.0,
                steps_taken=1,
                solved=False,
                error_category="syntax_error",
                total_reward=0.0,
                duration_seconds=1.0,
                api_errors=[],
                rate_limit_errors=2,
                timeout_errors=1,
                auth_errors=0,
                provider_errors=1,
            ),
        ]

        summary = compute_metrics_summary("test_id", "Test Model", task_results)

        assert summary.failure_rate == 0.5
        assert summary.rate_limit_rate == 1.0  # 2 errors / 2 tasks
        assert summary.timeout_rate == 0.5  # 1 error / 2 tasks
        assert summary.auth_error_rate == 0.0
        assert summary.provider_error_rate == 0.5

    def test_confidence_interval_computation(self):
        """Test CI computation in summary."""
        task_results = [
            TaskResult(
                task_id=f"task{i}",
                difficulty="easy",
                episode_score=0.5 + (i * 0.1),
                steps_taken=1,
                solved=(i % 2 == 0),
                error_category="success" if i % 2 == 0 else "logic_error",
                total_reward=0.5,
                duration_seconds=1.0,
                api_errors=[],
            )
            for i in range(10)
        ]

        summary = compute_metrics_summary("test_id", "Test Model", task_results)

        # Should have CI values with 10 samples
        assert summary.score_ci_95 is not None
        assert summary.solve_rate_ci_95 is not None

    def test_to_dict_serialization(self):
        """Test MetricsSummary.to_dict() produces valid dictionary."""
        task_results = [
            TaskResult(
                task_id="task1",
                difficulty="easy",
                episode_score=1.0,
                steps_taken=1,
                solved=True,
                error_category="success",
                total_reward=1.0,
                duration_seconds=1.0,
                api_errors=[],
            ),
        ]

        summary = compute_metrics_summary("test_id", "Test Model", task_results)
        d = summary.to_dict()

        assert "model_id" in d
        assert "model_name" in d
        assert "solve_metrics" in d
        assert "score_metrics" in d
        assert "difficulty_metrics" in d
        assert "steps_metrics" in d
        assert "latency_metrics" in d
        assert "token_metrics" in d
        assert "cost_metrics" in d
        assert "failure_metrics" in d


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
