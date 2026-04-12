"""
benchmark — SQLBench-OpenEnv evaluation layer.

Exports:
    BenchmarkRunner   — evaluates multiple models across all tasks
    generate_leaderboard — produces JSON leaderboard from run results
    print_leaderboard    — ASCII leaderboard to stdout
    classify_error       — error taxonomy classifier
    ErrorCounts          — per-model error accumulator
"""
from benchmark.runner import BenchmarkRunner, ModelResult, TaskResult
from benchmark.leaderboard import generate_leaderboard, print_leaderboard
from benchmark.error_taxonomy import classify_error, ErrorCounts, ERROR_CATEGORIES

__all__ = [
    "BenchmarkRunner",
    "ModelResult",
    "TaskResult",
    "generate_leaderboard",
    "print_leaderboard",
    "classify_error",
    "ErrorCounts",
    "ERROR_CATEGORIES",
]