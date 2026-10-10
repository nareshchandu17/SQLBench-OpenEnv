"""
benchmark/metrics.py

Enhanced evaluation metrics for SQLBench-OpenEnv.
Provides research-grade metrics beyond simple average scores.

Metrics:
- Exact execution accuracy (solve rate)
- Partial correctness (episode score distribution)
- Difficulty-stratified accuracy (easy/medium/hard)
- Steps to solve distribution
- Latency percentiles (P50, P95)
- Token usage statistics
- Cost estimation
- Failure rate breakdown
- 429 rate tracking
- 95% confidence intervals
"""
import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from statistics import mean, median, stdev


@dataclass
class MetricsSummary:
    """Comprehensive metrics summary for a model's performance."""
    model_id: str
    model_name: str

    # Solve metrics
    total_tasks: int = 0
    solved_count: int = 0
    solve_rate: float = 0.0  # exact execution accuracy

    # Score metrics
    average_score: float = 0.0
    score_std: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0

    # Difficulty-stratified metrics
    easy_count: int = 0
    easy_accuracy: float = 0.0
    medium_count: int = 0
    medium_accuracy: float = 0.0
    hard_count: int = 0
    hard_accuracy: float = 0.0

    # Steps metrics
    avg_steps: float = 0.0
    median_steps: float = 0.0
    max_steps: int = 0

    # Latency metrics (seconds)
    avg_latency: float = 0.0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    max_latency: float = 0.0

    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    avg_tokens_per_task: float = 0.0

    # Cost estimation (USD)
    total_cost_usd: float = 0.0
    avg_cost_per_task: float = 0.0

    # Failure rates
    failure_rate: float = 0.0
    rate_limit_rate: float = 0.0  # 429 rate
    timeout_rate: float = 0.0
    auth_error_rate: float = 0.0
    provider_error_rate: float = 0.0

    # Confidence intervals
    score_ci_95: Optional[float] = None  # 95% CI for average score
    solve_rate_ci_95: Optional[float] = None  # 95% CI for solve rate

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "solve_metrics": {
                "total_tasks": self.total_tasks,
                "solved_count": self.solved_count,
                "solve_rate": round(self.solve_rate, 4),
                "solve_rate_ci_95": round(self.solve_rate_ci_95, 4) if self.solve_rate_ci_95 else None,
            },
            "score_metrics": {
                "average_score": round(self.average_score, 4),
                "score_std": round(self.score_std, 4),
                "min_score": round(self.min_score, 4),
                "max_score": round(self.max_score, 4),
                "score_ci_95": round(self.score_ci_95, 4) if self.score_ci_95 else None,
            },
            "difficulty_metrics": {
                "easy": {
                    "count": self.easy_count,
                    "accuracy": round(self.easy_accuracy, 4),
                },
                "medium": {
                    "count": self.medium_count,
                    "accuracy": round(self.medium_accuracy, 4),
                },
                "hard": {
                    "count": self.hard_count,
                    "accuracy": round(self.hard_accuracy, 4),
                },
            },
            "steps_metrics": {
                "avg_steps": round(self.avg_steps, 2),
                "median_steps": round(self.median_steps, 2),
                "max_steps": self.max_steps,
            },
            "latency_metrics": {
                "avg_latency": round(self.avg_latency, 3),
                "p50_latency": round(self.p50_latency, 3),
                "p95_latency": round(self.p95_latency, 3),
                "max_latency": round(self.max_latency, 3),
            },
            "token_metrics": {
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_tokens": self.total_tokens,
                "avg_tokens_per_task": round(self.avg_tokens_per_task, 1),
            },
            "cost_metrics": {
                "total_cost_usd": round(self.total_cost_usd, 6),
                "avg_cost_per_task": round(self.avg_cost_per_task, 6),
            },
            "failure_metrics": {
                "failure_rate": round(self.failure_rate, 4),
                "rate_limit_rate": round(self.rate_limit_rate, 4),
                "timeout_rate": round(self.timeout_rate, 4),
                "auth_error_rate": round(self.auth_error_rate, 4),
                "provider_error_rate": round(self.provider_error_rate, 4),
            },
        }


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculate percentile using linear interpolation."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]

    k = (percentile / 100) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)

    if f == c:
        return sorted_values[int(k)]

    # Linear interpolation
    lower = sorted_values[int(f)]
    upper = sorted_values[int(c)]
    weight = k - f
    return lower * (1 - weight) + upper * weight


def calculate_ci_95_mean(values: List[float]) -> Optional[float]:
    """
    Calculate 95% confidence interval for the mean.
    Returns the margin of error (half-width of the CI).
    Returns None if sample size < 2.
    """
    if len(values) < 2:
        return None

    sample_mean = mean(values)
    sample_std = stdev(values) if len(values) > 1 else 0.0
    n = len(values)

    # Standard error of the mean
    sem = sample_std / math.sqrt(n)

    # 95% CI margin of error (1.96 for normal distribution)
    margin_of_error = 1.96 * sem

    return margin_of_error


def calculate_ci_95_proportion(successes: int, total: int) -> Optional[float]:
    """
    Calculate 95% confidence interval for a proportion using Wilson score interval.
    Returns the margin of error (half-width of the CI).
    Returns None if total < 2.
    """
    if total < 2:
        return None

    p = successes / total if total > 0 else 0.0
    z = 1.96  # 95% confidence

    # Wilson score interval
    denominator = 1 + (z ** 2) / total
    center = (p + (z ** 2) / (2 * total)) / denominator
    margin = (z * math.sqrt((p * (1 - p) / total) + (z ** 2) / (4 * total ** 2))) / denominator

    return margin


def compute_metrics_summary(
    model_id: str,
    model_name: str,
    task_results: List[Any],
) -> MetricsSummary:
    """
    Compute comprehensive metrics from task results.

    Args:
        model_id: Model identifier
        model_name: Human-readable model name
        task_results: List of TaskResult objects

    Returns:
        MetricsSummary with all computed metrics
    """
    if not task_results:
        return MetricsSummary(model_id=model_id, model_name=model_name)

    total_tasks = len(task_results)
    solved_count = sum(1 for tr in task_results if tr.solved)
    solve_rate = solved_count / total_tasks if total_tasks > 0 else 0.0

    # Score metrics
    scores = [tr.episode_score for tr in task_results]
    average_score = mean(scores)
    score_std = stdev(scores) if len(scores) > 1 else 0.0
    min_score = min(scores)
    max_score = max(scores)

    # Difficulty-stratified metrics
    easy_tasks = [tr for tr in task_results if tr.difficulty == "easy"]
    medium_tasks = [tr for tr in task_results if tr.difficulty == "medium"]
    hard_tasks = [tr for tr in task_results if tr.difficulty == "hard"]

    easy_count = len(easy_tasks)
    easy_accuracy = sum(1 for tr in easy_tasks if tr.solved) / easy_count if easy_count > 0 else 0.0

    medium_count = len(medium_tasks)
    medium_accuracy = sum(1 for tr in medium_tasks if tr.solved) / medium_count if medium_count > 0 else 0.0

    hard_count = len(hard_tasks)
    hard_accuracy = sum(1 for tr in hard_tasks if tr.solved) / hard_count if hard_count > 0 else 0.0

    # Steps metrics
    steps = [tr.steps_taken for tr in task_results]
    avg_steps = mean(steps)
    median_steps = median(steps)
    max_steps = max(steps)

    # Latency metrics
    latencies = [tr.duration_seconds for tr in task_results]
    avg_latency = mean(latencies)
    p50_latency = calculate_percentile(latencies, 50)
    p95_latency = calculate_percentile(latencies, 95)
    max_latency = max(latencies)

    # Token usage
    total_input_tokens = sum(tr.input_tokens for tr in task_results)
    total_output_tokens = sum(tr.output_tokens for tr in task_results)
    total_tokens = sum(tr.total_tokens for tr in task_results)
    avg_tokens_per_task = total_tokens / total_tasks if total_tasks > 0 else 0.0

    # Cost estimation
    total_cost_usd = sum(tr.cost_usd for tr in task_results)
    avg_cost_per_task = total_cost_usd / total_tasks if total_tasks > 0 else 0.0

    # Failure rates
    failure_rate = 1.0 - solve_rate
    total_429_errors = sum(tr.rate_limit_errors for tr in task_results)
    total_timeout_errors = sum(tr.timeout_errors for tr in task_results)
    total_auth_errors = sum(tr.auth_errors for tr in task_results)
    total_provider_errors = sum(tr.provider_errors for tr in task_results)

    # Rate per task (not per API call, to normalize by task count)
    rate_limit_rate = total_429_errors / total_tasks if total_tasks > 0 else 0.0
    timeout_rate = total_timeout_errors / total_tasks if total_tasks > 0 else 0.0
    auth_error_rate = total_auth_errors / total_tasks if total_tasks > 0 else 0.0
    provider_error_rate = total_provider_errors / total_tasks if total_tasks > 0 else 0.0

    # Confidence intervals
    score_ci_95 = calculate_ci_95_mean(scores)
    solve_rate_ci_95 = calculate_ci_95_proportion(solved_count, total_tasks)

    return MetricsSummary(
        model_id=model_id,
        model_name=model_name,
        total_tasks=total_tasks,
        solved_count=solved_count,
        solve_rate=solve_rate,
        average_score=average_score,
        score_std=score_std,
        min_score=min_score,
        max_score=max_score,
        easy_count=easy_count,
        easy_accuracy=easy_accuracy,
        medium_count=medium_count,
        medium_accuracy=medium_accuracy,
        hard_count=hard_count,
        hard_accuracy=hard_accuracy,
        avg_steps=avg_steps,
        median_steps=median_steps,
        max_steps=max_steps,
        avg_latency=avg_latency,
        p50_latency=p50_latency,
        p95_latency=p95_latency,
        max_latency=max_latency,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_tokens=total_tokens,
        avg_tokens_per_task=avg_tokens_per_task,
        total_cost_usd=total_cost_usd,
        avg_cost_per_task=avg_cost_per_task,
        failure_rate=failure_rate,
        rate_limit_rate=rate_limit_rate,
        timeout_rate=timeout_rate,
        auth_error_rate=auth_error_rate,
        provider_error_rate=provider_error_rate,
        score_ci_95=score_ci_95,
        solve_rate_ci_95=solve_rate_ci_95,
    )
