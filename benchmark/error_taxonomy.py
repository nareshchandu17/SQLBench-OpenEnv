"""
benchmark/error_taxonomy.py

Classifies SQL errors into a structured taxonomy.
This turns raw error messages into research-grade failure analysis.

Taxonomy:
  - syntax_error     : Malformed SQL (missing comma, wrong keyword, etc.)
  - reference_error  : Wrong table or column name
  - join_error       : Incorrect JOIN type or condition
  - aggregation_error: Wrong GROUP BY, HAVING, or aggregate function
  - logic_error      : Structurally valid but semantically wrong query
  - ordering_error   : Wrong ORDER BY direction or column
  - success          : Query executed and matched expected result
"""
from typing import Dict
from dataclasses import dataclass, field


ERROR_CATEGORIES = [
    "syntax_error",
    "reference_error",
    "join_error",
    "aggregation_error",
    "logic_error",
    "ordering_error",
    "success",
]


@dataclass
class ErrorCounts:
    syntax_error: int = 0
    reference_error: int = 0
    join_error: int = 0
    aggregation_error: int = 0
    logic_error: int = 0
    ordering_error: int = 0
    success: int = 0
    total: int = 0

    def to_dict(self) -> Dict[str, float]:
        """Return category rates (not counts) for normalized comparison."""
        if self.total == 0:
            return {cat: 0.0 for cat in ERROR_CATEGORIES}
        return {
            cat: round(getattr(self, cat) / self.total, 3)
            for cat in ERROR_CATEGORIES
        }

    def add(self, category: str) -> None:
        self.total += 1
        if hasattr(self, category):
            setattr(self, category, getattr(self, category) + 1)


def classify_error(
    error_message: str,
    agent_result,
    expected_result,
    query: str,
    episode_score: float,
) -> str:
    """
    Classify a single agent attempt into one error category.
    Deterministic — same inputs always produce same category.
    
    Priority order matters: check most specific first.
    """
    # Success case
    if episode_score >= 1.0:
        return "success"

    # No SQL execution error — it ran but produced wrong data
    if not error_message:
        query_upper = query.upper()

        # Join-related logic errors
        if "JOIN" in query_upper:
            # Check for common join mistakes: joining on wrong column
            if episode_score < 0.4:
                return "join_error"

        # Aggregation issues: query has GROUP BY / HAVING
        if "GROUP BY" in query_upper or "HAVING" in query_upper:
            return "aggregation_error"

        # ORDER BY wrong direction / missing
        if "ORDER BY" in query_upper and episode_score < 0.8:
            return "ordering_error"

        # Generic logic error — runs but wrong result
        return "logic_error"

    # SQL execution errors — parse error message
    err_lower = error_message.lower()

    # Reference errors: wrong table/column name
    if any(kw in err_lower for kw in [
        "no such table", "no such column", "unknown column",
        "table not found", "column not found",
    ]):
        return "reference_error"

    # Join errors surfacing as execution errors
    if any(kw in err_lower for kw in ["ambiguous column", "ambiguous"]):
        return "join_error"

    # Aggregation errors
    if any(kw in err_lower for kw in [
        "aggregate", "group by", "non-aggregate", "having",
        "not a single-group group function",
    ]):
        return "aggregation_error"

    # Syntax errors (catch-all for execution failures)
    if any(kw in err_lower for kw in [
        "syntax error", "parse error", "near", "unexpected",
        "incomplete input", "misuse",
    ]):
        return "syntax_error"

    # Default for unrecognized errors
    return "syntax_error"