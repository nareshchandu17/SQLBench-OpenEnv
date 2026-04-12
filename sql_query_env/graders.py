"""
Deterministic graders that score agent SQL output against ground truth.
All graders return float in [0.0, 1.0].
No randomness. No LLM calls. Pure comparison logic.
"""
from typing import List, Dict, Set
import json


def normalize_rows(rows: List[Dict]) -> List[frozenset]:
    """Convert rows to frozensets for order-independent comparison."""
    return [
        frozenset((k, str(v)) for k, v in row.items())
        for row in rows
    ]


def grade_result_match(
    agent_result: List[Dict],
    expected_result: List[Dict],
) -> float:
    """
    Compare agent query output to ground truth.
    Returns 1.0 for exact match, partial credit otherwise.
    
    Scoring:
    - 1.0: Exact match (same rows, same columns, order ignored)
    - 0.7: Same rows but extra/missing columns
    - 0.5: Correct row count but wrong values
    - 0.3: Partial row overlap (>50% correct rows)
    - 0.1: Some overlap but mostly wrong
    - 0.0: Completely wrong or error
    """
    if not agent_result and not expected_result:
        return 1.0  # Both empty is correct
    
    if not agent_result or not expected_result:
        return 0.0  # One is empty, other is not
    
    agent_cols: Set[str] = set(agent_result[0].keys()) if agent_result else set()
    expected_cols: Set[str] = set(expected_result[0].keys()) if expected_result else set()
    
    agent_rows = normalize_rows(agent_result)
    expected_rows = normalize_rows(expected_result)
    
    # Exact match check
    if set(agent_rows) == set(expected_rows) and agent_cols == expected_cols:
        return 1.0
    
    # Same columns, check row overlap
    if agent_cols == expected_cols:
        overlap = len(set(agent_rows) & set(expected_rows))
        if overlap == len(expected_rows):
            return 0.9  # All correct rows present, but maybe extras
        ratio = overlap / max(len(expected_rows), 1)
        if ratio >= 0.5:
            return 0.3 + 0.4 * ratio  # 0.3 to 0.7
        return 0.1 + 0.2 * ratio  # 0.1 to 0.3
    
    # Column mismatch — check if expected columns are a subset
    if expected_cols.issubset(agent_cols) or agent_cols.issubset(expected_cols):
        # Extract only shared columns and compare
        shared = agent_cols & expected_cols
        if shared:
            agent_shared = normalize_rows(
                [{k: v for k, v in r.items() if k in shared} for r in agent_result]
            )
            exp_shared = normalize_rows(
                [{k: v for k, v in r.items() if k in shared} for r in expected_result]
            )
            if set(agent_shared) == set(exp_shared):
                return 0.7  # Right data, wrong column selection
    
    # Row count match alone
    if len(agent_result) == len(expected_result):
        return 0.2
    
    return 0.0


def grade_syntax(error_message: str) -> float:
    """
    Returns 0.0 if there's a syntax error, 1.0 if query executed.
    Used to apply syntax penalty in reward function.
    """
    return 0.0 if error_message else 1.0


def grade_efficiency(query: str) -> float:
    """
    Checks for obvious inefficiency patterns.
    Returns 0.0 to 1.0. Used as a bonus for hard tasks.
    
    Rewards:
    - Not using SELECT *
    - Using specific column names
    - Not using correlated subqueries when JOIN is possible
    - Using appropriate LIMIT when relevant
    """
    score = 1.0
    query_upper = query.upper()
    
    if "SELECT *" in query_upper:
        score -= 0.3
    
    # Penalize multiple nested subqueries (anti-pattern)
    subquery_count = query_upper.count("SELECT") - 1
    if subquery_count > 2:
        score -= 0.2 * (subquery_count - 2)
    
    return max(0.0, min(1.0, score))


def compute_task_score(
    agent_result: List[Dict],
    expected_result: List[Dict],
    error_message: str,
    query: str,
    task_difficulty: str,
) -> float:
    """
    Master grader — combines all components into final [0.0, 1.0] score.
    This is what gets reported as the episode score.
    """
    if error_message:
        # Query didn't even execute — very low score
        return 0.05
    
    result_score = grade_result_match(agent_result, expected_result)
    
    if task_difficulty == "hard":
        efficiency_bonus = grade_efficiency(query) * 0.1
        return min(1.0, result_score * 0.9 + efficiency_bonus)
    
    return result_score