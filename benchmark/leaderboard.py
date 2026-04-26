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


def generate_leaderboard(
    results: List[ModelResult],
    output_dir: str = "benchmark_output",
) -> Dict[str, Any]:
    """
    Builds the complete benchmark output:
    - benchmark_results.json   (raw per-task data)
    - leaderboard.json         (ranked summary)
    - error_taxonomy.json      (failure analysis per model)

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
                }
                for tr in mr.task_results
            ],
        })

    with open(f"{output_dir}/benchmark_results.json", "w") as f:
        json.dump(raw, f, indent=2)

    # ── 2. Leaderboard ────────────────────────────────────────────────────────
    leaderboard_entries = []
    for mr in results:
        by_diff = mr.score_by_difficulty()
        # Clamp all scores to valid [0.0, 1.0] range for crash-proofing
        easy_score = max(0.0, min(1.0, by_diff.get("easy", 0.0)))
        medium_score = max(0.0, min(1.0, by_diff.get("medium", 0.0)))
        hard_score = max(0.0, min(1.0, by_diff.get("hard", 0.0)))
        avg_score = max(0.0, min(1.0, mr.average_score()))
        
        leaderboard_entries.append({
            "rank": 0,  # filled after sort
            "model_id": mr.model_id,
            "model_name": mr.model_name,
            "easy": easy_score,
            "medium": medium_score,
            "hard": hard_score,
            "average_score": avg_score,  # Match server.py field name
            "solved_count": sum(1 for tr in mr.task_results if tr.solved),
            "total_tasks": len(mr.task_results),
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

    # ── 3. Error taxonomy ─────────────────────────────────────────────────────
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

    print(f"\n{'='*70}")
    print(f"  SQLBench-OpenEnv — Leaderboard")
    print(f"  {leaderboard['timestamp']}")
    print(f"{'='*70}")
    print(f"  {'#':<4} {'Model':<30} {'Easy':>6} {'Medium':>8} {'Hard':>6} {'Avg':>6}")
    print(f"  {'─'*60}")

    bar_chars = "█"
    for entry in rankings:
        bar_len = int(entry["average_score"] * 20)
        bar = bar_chars * bar_len
        solved = f"{entry['solved_count']}/{entry['total_tasks']}"
        print(
            f"  {entry['rank']:<4}"
            f"{entry['model_name']:<30}"
            f"{entry['easy']:>6.3f}"
            f"{entry['medium']:>8.3f}"
            f"{entry['hard']:>6.3f}"
            f"{entry['average_score']:>6.3f}"
            f"  {bar:<20} ({solved} solved)"
        )

    print(f"{'='*70}\n")