"""
Deterministic graders that score agent SQL output against ground truth.
All graders return float in [0.0, 1.0].
No randomness. No LLM calls. Pure comparison logic.
"""
from typing import List, Dict, Set, Any, Optional
from collections import Counter
import json

def _normalize_val(v: Any) -> Any:
    """
    Normalize value for comparison.
    
    Handles:
    - NULL values (None)
    - Numeric types (int, float, numeric strings)
    - String representations
    - Distinguishes NULL from string "NULL"/"None"
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        # Try to convert numeric strings to float for comparison
        try:
            return float(v)
        except ValueError:
            # Not a numeric string, return as-is
            # This preserves distinction between "NULL" string and actual NULL
            return v
    return str(v)

def _row_to_tuple(row: Dict, keys: List[str]) -> tuple:
    """Convert a row to a comparable tuple using a specific key order."""
    return tuple(_normalize_val(row.get(k)) for k in keys)

def _validate_column_order(agent_cols: List[str], expected_cols: List[str], ordered: bool) -> bool:
    """
    Validate column order.
    
    When ordered=True (ORDER BY present), enforce exact column sequence.
    When ordered=False, allow any column order but require same set of columns.
    """
    if ordered:
        # Exact column order required
        return agent_cols == expected_cols
    else:
        # Same set of columns, order doesn't matter
        return set(agent_cols) == set(expected_cols) and len(agent_cols) == len(expected_cols)

def grade_result_exact(agent_result: List[Dict], expected_result: List[Dict], ordered: bool) -> float:
    """
    Exact comparison with support for:
    - ORDER BY enforcement (row order)
    - Duplicate row handling (multiset semantics)
    - NULL value handling
    - Type normalization
    - Column order validation
    """
    # Both empty: perfect match
    if not agent_result and not expected_result:
        return 1.0
    
    # One empty, one not: fail
    if not agent_result or not expected_result:
        return 0.0

    agent_cols = list(agent_result[0].keys())
    expected_cols = list(expected_result[0].keys())

    # Validate columns: same set and same count
    if set(agent_cols) != set(expected_cols) or len(agent_cols) != len(expected_cols):
        return 0.0

    # Validate column order when ORDER BY is present
    if not _validate_column_order(agent_cols, expected_cols, ordered):
        return 0.0

    if ordered:
        # Ordered comparison: exact row-by-row match
        if len(agent_result) != len(expected_result):
            return 0.0
        for ar, er in zip(agent_result, expected_result):
            if _row_to_tuple(ar, expected_cols) != _row_to_tuple(er, expected_cols):
                return 0.0
        return 1.0
    else:
        # Unordered comparison: duplicate-aware multiset match
        agent_counter = Counter(_row_to_tuple(r, expected_cols) for r in agent_result)
        expected_counter = Counter(_row_to_tuple(r, expected_cols) for r in expected_result)
        if agent_counter == expected_counter:
            return 1.0
        return 0.0

def grade_result_match(
    agent_result: List[Dict],
    expected_result: List[Dict],
    ground_truth_query: str = "",
) -> float:
    ordered = "ORDER BY" in ground_truth_query.upper()
    exact = grade_result_exact(agent_result, expected_result, ordered)
    if exact == 1.0:
        return 1.0

    if not agent_result or not expected_result:
        return 0.0

    agent_cols = set(agent_result[0].keys())
    expected_cols = set(expected_result[0].keys())
    expected_keys = list(expected_result[0].keys())
    
    if agent_cols == expected_cols:
        agent_counter = Counter(_row_to_tuple(r, expected_keys) for r in agent_result)
        expected_counter = Counter(_row_to_tuple(r, expected_keys) for r in expected_result)
        overlap = sum((agent_counter & expected_counter).values())
        if overlap == len(expected_result) and len(agent_result) >= len(expected_result):
            return 0.9
        ratio = overlap / max(len(expected_result), 1)
        if ratio >= 0.5:
            return 0.3 + 0.4 * ratio
        return 0.1 + 0.2 * ratio

    if expected_cols.issubset(agent_cols) or agent_cols.issubset(expected_cols):
        shared = list(agent_cols & expected_cols)
        if shared:
            a_shared = Counter(_row_to_tuple(r, shared) for r in agent_result)
            e_shared = Counter(_row_to_tuple(r, shared) for r in expected_result)
            if a_shared == e_shared:
                return 0.7

    if len(agent_result) == len(expected_result):
        return 0.2

    return 0.0

def grade_syntax(error_message: str) -> float:
    return 0.0 if error_message else 1.0

def grade_efficiency(query: str) -> float:
    score = 1.0
    query_upper = query.upper()
    if "SELECT *" in query_upper:
        score -= 0.3
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
    ground_truth_query: str = "",
) -> float:
    if error_message:
        return 0.05
    
    result_score = grade_result_match(agent_result, expected_result, ground_truth_query)
    
    if task_difficulty == "hard":
        efficiency_bonus = grade_efficiency(query) * 0.1
        return min(1.0, result_score * 0.9 + efficiency_bonus)
    
    return result_score