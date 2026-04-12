"""
SQL Query Debugging Environment — OpenEnv compliant implementation.

An RL environment where an agent receives a broken SQL query and
must produce a corrected version. The grader executes both the
agent's query and the ground truth against a live SQLite database
and scores the result match.
"""
import random
from typing import Any, Dict, List, Optional, Tuple

from .database import DatabaseManager
from .models import SQLObservation, SQLAction, SQLReward, TaskState
from .tasks import TASKS, TASK_INDEX
from .reward import compute_step_reward
from .graders import compute_task_score


class SQLQueryEnv:
    """
    OpenEnv-compliant SQL debugging environment.
    
    Episode lifecycle:
    1. reset(task_id?) → loads a task, seeds DB, returns initial observation
    2. step(action) → executes query, grades result, returns (obs, reward, done, info)
    3. state() → returns full internal state (includes ground truth — for debugging)
    
    The agent never sees the ground truth query or expected result directly.
    It only sees the schema, the broken query, error messages, and its own attempts.
    """
    
    def __init__(self, seed: int = 42):
        self._db = DatabaseManager()
        self._rng = random.Random(seed)
        self._state: Optional[TaskState] = None
        self._previous_best_score: float = 0.0
    
    # ── Public API (OpenEnv spec) ─────────────────────────────────────────────
    
    def reset(
        self,
        task_id: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> SQLObservation:
        """
        Start a new episode.
        
        Args:
            task_id: Specific task to load. If None, picks randomly.
            seed: Random seed for reproducibility.
        
        Returns:
            Initial observation containing schema, broken query, and task description.
        """
        if seed is not None:
            self._rng = random.Random(seed)
        
        # Select task
        if task_id:
            task = TASK_INDEX.get(task_id)
            if not task:
                raise ValueError(
                    f"Unknown task_id: '{task_id}'. "
                    f"Available: {list(TASK_INDEX.keys())}"
                )
        else:
            task = self._rng.choice(TASKS)
        
        # Initialize database with dynamic or static data
        if "data_factory" in task:
            seed_data_sql = task["data_factory"](self._rng)
        else:
            seed_data_sql = task.get("seed_data_sql", "")
            
        self._db.setup(
            schema_ddl=task["schema_ddl"],
            seed_data_sql=seed_data_sql,
        )
        
        # Pre-compute ground truth result (hidden from agent)
        expected_result = self._db.get_reference_result(task["ground_truth_query"])
        
        # Initialize episode state
        self._state = TaskState(
            task_id=task["id"],
            schema_ddl=task["schema_ddl"].strip(),
            broken_query=task["broken_query"].strip(),
            ground_truth_query=task["ground_truth_query"].strip(),
            expected_result=expected_result,
            step_count=0,
            max_steps=task["max_steps"],
            done=False,
            cumulative_reward=0.0,
            previous_attempts=[],
        )
        self._previous_best_score = 0.0
        
        return self._make_observation(error_message="", last_result=None)
    
    def step(
        self, action: SQLAction
    ) -> Tuple[SQLObservation, SQLReward, bool, Dict[str, Any]]:
        """
        Execute one step: run the agent's query and grade the result.
        
        Args:
            action: SQLAction with the agent's query string.
        
        Returns:
            (observation, reward, done, info)
        """
        if not self._state:
            raise RuntimeError("Call reset() before step().")
        if self._state.done:
            raise RuntimeError("Episode is done. Call reset() to start a new one.")
        
        s = self._state
        s.step_count += 1
        s.previous_attempts.append(action.query)
        
        is_final = s.step_count >= s.max_steps
        
        # Execute agent's query
        agent_result, error_message = self._db.execute_query(action.query)
        if agent_result is None:
            agent_result = []
        
        # Compute reward
        reward = compute_step_reward(
            agent_result=agent_result,
            expected_result=s.expected_result,
            error_message=error_message or "",
            query=action.query,
            previous_best_score=self._previous_best_score,
            step_count=s.step_count,
            max_steps=s.max_steps,
            task_difficulty=TASK_INDEX[s.task_id]["difficulty"],
            is_final_step=is_final,
        )
        
        # Update best score
        if reward.breakdown.result_match > self._previous_best_score:
            self._previous_best_score = reward.breakdown.result_match
        
        # Update state
        s.done = reward.done
        s.cumulative_reward += reward.value
        
        # Build next observation
        obs = self._make_observation(
            error_message=error_message or "",
            last_result=agent_result,
        )
        
        info = {
            "task_id": s.task_id,
            "step": s.step_count,
            "cumulative_reward": s.cumulative_reward,
            "episode_score": compute_task_score(
                agent_result=agent_result,
                expected_result=s.expected_result,
                error_message=error_message or "",
                query=action.query,
                task_difficulty=TASK_INDEX[s.task_id]["difficulty"],
            ),
            "solved": reward.success,
        }
        
        return obs, reward, reward.done, info
    
    def state(self) -> TaskState:
        """Return full internal state (includes ground truth, for debugging)."""
        if not self._state:
            raise RuntimeError("Call reset() first.")
        return self._state

    def close(self):
        """Cleanup resources."""
        if hasattr(self, "_db"):
            self._db.teardown()
    
    # ── Private helpers ───────────────────────────────────────────────────────
    
    def _make_observation(
        self,
        error_message: str,
        last_result: Optional[List[Dict]],
    ) -> SQLObservation:
        s = self._state
        task_def = TASK_INDEX[s.task_id]
        
        return SQLObservation(
            task_id=s.task_id,
            schema_ddl=s.schema_ddl,
            broken_query=s.broken_query,
            error_message=error_message,
            expected_description=task_def["expected_description"],
            step_count=s.step_count,
            max_steps=s.max_steps,
            previous_attempts=s.previous_attempts.copy(),
            last_execution_result=(
                str(last_result[:5]) if last_result else None
            ),  # Show first 5 rows only to keep context short
        )