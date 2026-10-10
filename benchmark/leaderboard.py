"""
benchmark/leaderboard.py

Generates leaderboard JSON and console-printed ASCII table
from benchmark run results. Also generates error taxonomy report.
"""
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone

from benchmark.runner import ModelResult
from benchmark.error_taxonomy import ERROR_CATEGORIES
from benchmark.metrics import compute_metrics_summary


def generate_leaderboard(
    results: List[ModelResult],
    output_dir: str = "benchmark_output",
) -> Dict[str, Any]:
    """
    Builds the complete benchmark output:
    - benchmark_results.json   (raw per-task data)
    - leaderboard.json         (ranked summary)
    - error_taxonomy.json      (failure analysis per model)
    - metrics.json              (enhanced metrics with CI, percentiles, costs)

    Returns the leaderboard dict.
    """
    Path(output_dir).mkdir(exist_ok=True)

    # ── 1. Raw results ────────────────────────────────────────────────────────
    raw = {
        "benchmark": "SQLBench-OpenEnv",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "models": [],
    }
    for mr in results:
        raw["models"].append({
            "model_id": mr.model_id,
            "model_name": mr.model_name,
            "tasks": [
                {
                    "task_id": tr.task_id,
                    "difficulty": tr.difficulty,
                    "score": tr.episode_score,
                    "solved": tr.solved,
                    "steps": tr.steps_taken,
                    "error_category": tr.error_category,
                    "reward": tr.total_reward,
                    "seconds": tr.duration_seconds,
                    "input_tokens": tr.input_tokens,
                    "output_tokens": tr.output_tokens,
                    "total_tokens": tr.total_tokens,
                    "cost_usd": tr.cost_usd,
                    "rate_limit_errors": tr.rate_limit_errors,
                    "timeout_errors": tr.timeout_errors,
                    "auth_errors": tr.auth_errors,
                    "provider_errors": tr.provider_errors,
                }
                for tr in mr.task_results
            ],
        })

    with open(f"{output_dir}/benchmark_results.json", "w") as f:
        json.dump(raw, f, indent=2)

    # ── 2. Enhanced metrics ────────────────────────────────────────────────────
    metrics_summary = {}
    for mr in results:
        summary = compute_metrics_summary(mr.model_id, mr.model_name, mr.task_results)
        metrics_summary[mr.model_id] = summary.to_dict()

    with open(f"{output_dir}/metrics.json", "w") as f:
        json.dump({
            "benchmark": "SQLBench-OpenEnv",
            "timestamp": raw["timestamp"],
            "models": metrics_summary,
        }, f, indent=2)

    # ── 3. Leaderboard ────────────────────────────────────────────────────────
    leaderboard_entries = []
    for mr in results:
        by_diff = mr.score_by_difficulty()
        # Clamp all scores to valid [0.0, 1.0] range for crash-proofing
        easy_score = max(0.0, min(1.0, by_diff.get("easy", 0.0)))
        medium_score = max(0.0, min(1.0, by_diff.get("medium", 0.0)))
        hard_score = max(0.0, min(1.0, by_diff.get("hard", 0.0)))
        avg_score = max(0.0, min(1.0, mr.average_score()))

        summary = metrics_summary.get(mr.model_id, {})

        leaderboard_entries.append({
            "rank": 0,  # filled after sort
            "model_id": mr.model_id,
            "model_name": mr.model_name,
            "easy": easy_score,
            "medium": medium_score,
            "hard": hard_score,
            "average_score": avg_score,  # Match server.py field name
            "solved_count": summary.get("solve_metrics", {}).get("solved_count", 0),
            "total_tasks": summary.get("solve_metrics", {}).get("total_tasks", 0),
            "solve_rate": summary.get("solve_metrics", {}).get("solve_rate", 0.0),
            "solve_rate_ci_95": summary.get("solve_metrics", {}).get("solve_rate_ci_95"),
            "score_ci_95": summary.get("score_metrics", {}).get("score_ci_95"),
            "p50_latency": summary.get("latency_metrics", {}).get("p50_latency", 0.0),
            "p95_latency": summary.get("latency_metrics", {}).get("p95_latency", 0.0),
            "total_cost_usd": summary.get("cost_metrics", {}).get("total_cost_usd", 0.0),
        })

    leaderboard_entries.sort(key=lambda x: x["average_score"], reverse=True)
    for i, entry in enumerate(leaderboard_entries):
        entry["rank"] = i + 1

    leaderboard = {
        "benchmark": "SQLBench-OpenEnv",
        "timestamp": raw["timestamp"],
        "rankings": leaderboard_entries,
    }
    try:
        with open(f"{output_dir}/leaderboard.json", "w") as f:
            json.dump(leaderboard, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not write leaderboard: {e}")

    # ── 4. Error taxonomy ─────────────────────────────────────────────────────
    taxonomy = {
        "benchmark": "SQLBench-OpenEnv",
        "timestamp": raw["timestamp"],
        "description": (
            "Rate of each error category per model. "
            "Rates sum to 1.0 across all categories including success."
        ),
        "categories": ERROR_CATEGORIES,
        "models": {},
    }
    for mr in results:
        taxonomy["models"][mr.model_id] = {
            "model_name": mr.model_name,
            "error_rates": mr.error_counts.to_dict(),
            "total_attempts": mr.error_counts.total,
        }

    with open(f"{output_dir}/error_taxonomy.json", "w") as f:
        json.dump(taxonomy, f, indent=2)

    save_leaderboard(leaderboard, output_dir)

    return leaderboard


def generate_error_taxonomy(
    results: List[ModelResult],
    output_dir: str = "benchmark_output",
) -> Dict[str, Any]:
    """Generate error taxonomy analysis for models."""
    Path(output_dir).mkdir(exist_ok=True)
    
    taxonomy = {
        "benchmark": "SQLBench-OpenEnv",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": (
            "Rate of each error category per model. "
            "Rates sum to 1.0 across all categories including success."
        ),
        "categories": ERROR_CATEGORIES,
        "models": {},
    }
    for mr in results:
        taxonomy["models"][mr.model_id] = {
            "model_name": mr.model_name,
            "error_rates": mr.error_counts.to_dict(),
            "total_attempts": mr.error_counts.total,
        }

    try:
        with open(f"{output_dir}/error_taxonomy.json", "w") as f:
            json.dump(taxonomy, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not write error taxonomy: {e}")
    
    return taxonomy


def save_leaderboard(leaderboard: Dict[str, Any], output_dir: str = "benchmark_output") -> None:
    """Save leaderboard to JSON file (separate function for compatibility)."""
    import json
    from pathlib import Path
    
    Path(output_dir).mkdir(exist_ok=True)
    
    try:
        with open(f"{output_dir}/leaderboard.json", "w") as f:
            json.dump(leaderboard, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not write leaderboard: {e}")


def print_leaderboard(leaderboard: Dict[str, Any]) -> None:
    """Print a formatted ASCII leaderboard to stdout."""
    rankings = leaderboard["rankings"]

    print(f"\n{'='*80}")
    print(f"  SQLBench-OpenEnv — Leaderboard")
    print(f"  {leaderboard['timestamp']}")
    print(f"{'='*80}")
    print(f"  {'#':<4} {'Model':<30} {'Solve':>6} {'Easy':>6} {'Med':>6} {'Hard':>6} {'Avg':>6}")
    print(f"  {'─'*70}")

    bar_chars = "█"
    for entry in rankings:
        bar_len = int(entry["average_score"] * 20)
        bar = bar_chars * bar_len
        solve_rate = entry.get("solve_rate", 0.0)
        print(
            f"  {entry['rank']:<4}"
            f"{entry['model_name']:<30}"
            f"{solve_rate:>6.1%}"
            f"{entry['easy']:>6.3f}"
            f"{entry['medium']:>6.3f}"
            f"{entry['hard']:>6.3f}"
            f"{entry['average_score']:>6.3f}"
            f"  {bar:<20}"
        )

    print(f"{'='*80}\n")

    # Print enhanced metrics summary
    print(f"  Enhanced Metrics Summary")
    print(f"  {'─'*80}")
    for entry in rankings:
        print(f"\n  {entry['rank']}. {entry['model_name']}")
        solve_ci = entry.get("solve_rate_ci_95")
        score_ci = entry.get("score_ci_95")
        p50 = entry.get("p50_latency", 0.0)
        p95 = entry.get("p95_latency", 0.0)
        cost = entry.get("total_cost_usd", 0.0)

        if solve_ci is not None:
            print(f"    Solve Rate: {entry.get('solve_rate', 0.0):.1%} ± {solve_ci:.1%} (95% CI)")
        if score_ci is not None:
            print(f"    Avg Score: {entry['average_score']:.3f} ± {score_ci:.3f} (95% CI)")
        print(f"    Latency: P50={p50:.3f}s, P95={p95:.3f}s")
        if cost > 0:
            print(f"    Total Cost: ${cost:.6f}")

    print(f"\n{'='*80}\n")