"""
Reward function with partial progress signals.
The reward shapes agent learning throughout the episode,
not just at the final step.
"""
from .graders import grade_result_match, grade_efficiency
from .models import SQLReward, RewardBreakdown
from typing import List, Dict


def compute_step_reward(
    agent_result: List[Dict],
    expected_result: List[Dict],
    error_message: str,
    query: str,
    previous_best_score: float,
    step_count: int,
    max_steps: int,
    task_difficulty: str,
    is_final_step: bool,
) -> SQLReward:
    """
    Computes the reward for a single step.
    
    Design principles:
    1. Immediate feedback — agent always gets signal even for partial progress
    2. Progress reward — getting closer to solution is rewarded even if not there yet
    3. Syntax penalty — nonsense queries are penalized to discourage spam
    4. Step efficiency — small bonus for solving early, penalty at time limit
    5. Consistency — same inputs always produce same reward
    """
    breakdown = RewardBreakdown()
    
    # ── Case 1: query failed to execute ──────────────────────────────────────
    if error_message:
        breakdown.syntax_penalty = -0.2
        
        # Distinguish "closer" errors from total garbage
        if "no such table" in error_message.lower():
            breakdown.syntax_penalty = -0.1  # Agent knows SQL, wrong table name
        elif "syntax error" in error_message.lower():
            breakdown.syntax_penalty = -0.2
        else:
            breakdown.syntax_penalty = -0.15
        
        total = breakdown.syntax_penalty
        return SQLReward(
            value=max(-1.0, total),
            breakdown=breakdown,
            done=is_final_step,
            success=False,
        )
    
    # ── Case 2: query executed successfully ──────────────────────────────────
    result_score = grade_result_match(agent_result, expected_result)
    breakdown.result_match = result_score
    
    # Column-level partial credit
    if agent_result and expected_result:
        agent_cols = set(agent_result[0].keys())
        expected_cols = set(expected_result[0].keys())
        col_overlap = len(agent_cols & expected_cols) / max(len(expected_cols), 1)
        breakdown.column_match = col_overlap * 0.3
    
    # Row count partial credit
    if len(agent_result) == len(expected_result) and result_score < 1.0:
        breakdown.row_count_match = 0.1
    
    # Efficiency bonus (only for hard tasks)
    if task_difficulty == "hard":
        breakdown.efficiency_bonus = grade_efficiency(query) * 0.1
    
    # ── Progress delta reward ─────────────────────────────────────────────────
    # If this step is better than anything before, reward the improvement
    progress_bonus = max(0.0, result_score - previous_best_score) * 0.3
    
    # ── Step efficiency ───────────────────────────────────────────────────────
    # Solved early → small bonus. Hit step limit → small penalty.
    step_ratio = step_count / max_steps
    if result_score >= 1.0:
        step_bonus = (1.0 - step_ratio) * 0.1  # Up to +0.1 for solving on step 1
    elif is_final_step and result_score < 0.5:
        step_bonus = -0.05  # Tiny penalty for running out of steps without progress
    else:
        step_bonus = 0.0
    
    total = (
        result_score * 0.7
        + breakdown.column_match * 0.1
        + breakdown.row_count_match * 0.05
        + breakdown.efficiency_bonus
        + progress_bonus
        + step_bonus
    )
    
    total = max(-1.0, min(1.0, total))
    breakdown.result_match = result_score
    
    success = result_score >= 1.0
    done = success or is_final_step
    
    return SQLReward(
        value=total,
        breakdown=breakdown,
        done=done,
        success=success,
    )