#!/usr/bin/env python
"""
run_benchmark.py

Reproducible benchmark runner for SQLBench-OpenEnv.
Evaluates models on all SQL debugging tasks and generates leaderboard.

Usage:
    python run_benchmark.py

Environment variables (optional):
    API_BASE_URL    Inference API endpoint (default: Hugging Face router)
    HF_TOKEN        Authentication token for HF model access
    BENCHMARK_MODE  Set to '1' to use default config

Output:
    benchmark_output/benchmark_results.json  — Raw results per model/task
    benchmark_output/leaderboard.json        — Summary leaderboard
    benchmark_output/error_taxonomy.json     — Error analysis
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from benchmark.runner import BenchmarkRunner
from benchmark.leaderboard import generate_leaderboard
from benchmark.report import main as generate_report

# Enable UTF-8 output for Windows terminal (proper Unicode display)
sys.stdout.reconfigure(encoding="utf-8")

# Load environment variables from .env file
load_dotenv()


OUTPUT_DIR = "benchmark_output"


def main():
    """Run full benchmark and generate leaderboard."""
    print("\n" + "=" * 70)
    print("  SQLBench-OpenEnv Benchmark Runner")
    print("=" * 70)

    # Create benchmark runner
    try:
        runner = BenchmarkRunner()
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("\nMake sure you're running from the project root directory:")
        print("  cd sql-query-env")
        print("  python run_benchmark.py")
        sys.exit(1)

    # Run benchmark
    print("\nRunning benchmark...\n")
    results = runner.run()

    # Ensure output directory exists
    Path(OUTPUT_DIR).mkdir(exist_ok=True)

    # Generate leaderboard (this saves all JSON files)
    print("\nGenerating leaderboard...\n")
    leaderboard = generate_leaderboard(results, output_dir=OUTPUT_DIR)

    # Generate model analysis report
    print("\nGenerating model analysis report...\n")
    try:
        generate_report()
    except Exception as e:
        print(f"Warning: Could not generate report: {e}")

    # Display summary
    print("\n" + "=" * 70)
    print("  Benchmark Results")
    print("=" * 70)
    print(f"\nModels evaluated: {len(results)}")
    print(f"Tasks per model: {len(results[0].task_results) if results else 0}")
    print(f"\nLeaderboard:")
    print(f"{'─' * 70}")

    if leaderboard.get("rankings"):
        for i, entry in enumerate(leaderboard["rankings"], 1):
            avg_score = entry.get('average_score', 0.0)
            solved = entry.get('solved_count', 0)
            total = entry.get('total_tasks', 0)
            print(
                f"  {i:2d}. {entry.get('model_name', 'Unknown'):<30} "
                f"Avg: {avg_score:.3f}  "
                f"Solved: {solved}/{total}"
            )
    else:
        print("  (No rankings generated)")

    print(f"{'─' * 70}")
    print(f"\nOutput files saved to: {OUTPUT_DIR}/")
    print(f"  • benchmark_results.json      (raw per-task data)")
    print(f"  • leaderboard.json            (summary rankings)")
    print(f"  • error_taxonomy.json         (failure analysis)")
    print(f"  • model_analysis_report.txt   (research insights)")
    print(f"\nTo view the detailed model analysis report:")
    print(f"  cat {OUTPUT_DIR}/model_analysis_report.txt")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
