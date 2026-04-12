"""
tests/test_env.py

Integration tests for SQLQueryEnv.
Verifies reset/step/state contract, episode lifecycle,
reward ranges, and termination conditions.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from env.environment import SQLQueryEnv
from env.models import SQLAction, SQLObservation, SQLReward, TaskState


EASY_TASK   = "fix_syntax_simple"
MEDIUM_TASK = "fix_join_logic"
HARD_TASK   = "multi_constraint_query"

KNOWN_TASKS = [
    "fix_syntax_simple",
    "fix_table_name",
    "fix_join_logic",
    "fix_aggregate_logic",
    "multi_constraint_query",
]


# ── reset() ───────────────────────────────────────────────────────────────────

class TestReset:

    def test_returns_observation(self):
        env = SQLQueryEnv(seed=42)
        obs = env.reset(task_id=EASY_TASK)
        assert isinstance(obs, SQLObservation)

    def test_observation_has_schema(self):
        env = SQLQueryEnv(seed=42)
        obs = env.reset(task_id=EASY_TASK)
        assert "CREATE TABLE" in obs.schema_ddl.upper()

    def test_observation_has_broken_query(self):
        env = SQLQueryEnv(seed=42)
        obs = env.reset(task_id=EASY_TASK)
        assert "SELECT" in obs.broken_query.upper()

    def test_observation_has_description(self):
        env = SQLQueryEnv(seed=42)
        obs = env.reset(task_id=EASY_TASK)
        assert len(obs.expected_description) > 10

    def test_step_count_zero_after_reset(self):
        env = SQLQueryEnv(seed=42)
        obs = env.reset(task_id=EASY_TASK)
        assert obs.step_count == 0

    def test_previous_attempts_empty_after_reset(self):
        env = SQLQueryEnv(seed=42)
        obs = env.reset(task_id=EASY_TASK)
        assert obs.previous_attempts == []

    def test_error_message_empty_after_reset(self):
        env = SQLQueryEnv(seed=42)
        obs = env.reset(task_id=EASY_TASK)
        assert obs.error_message == ""

    def test_reset_with_unknown_task_raises(self):
        env = SQLQueryEnv(seed=42)
        with pytest.raises(ValueError, match="Unknown task_id"):
            env.reset(task_id="nonexistent_task_xyz")

    def test_reset_without_task_id_picks_random(self):
        env = SQLQueryEnv(seed=42)
        obs = env.reset()
        assert obs.task_id in KNOWN_TASKS

    def test_reset_clears_previous_episode(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        # Take a step so state is dirty
        env.step(SQLAction(query="SELECT 1"))
        # Reset again
        obs = env.reset(task_id=EASY_TASK)
        assert obs.step_count == 0
        assert obs.previous_attempts == []
        assert obs.error_message == ""

    def test_all_known_tasks_reset_without_error(self):
        env = SQLQueryEnv(seed=42)
        for task_id in KNOWN_TASKS:
            obs = env.reset(task_id=task_id)
            assert obs.task_id == task_id

    def test_seed_produces_same_task(self):
        env1 = SQLQueryEnv(seed=7)
        env2 = SQLQueryEnv(seed=7)
        obs1 = env1.reset()
        obs2 = env2.reset()
        assert obs1.task_id == obs2.task_id

    def test_max_steps_set_correctly(self):
        env = SQLQueryEnv(seed=42)
        obs = env.reset(task_id=EASY_TASK)
        assert obs.max_steps == 5  # easy tasks have max_steps=5

        obs2 = env.reset(task_id=HARD_TASK)
        assert obs2.max_steps == 10  # hard task has max_steps=10


# ── step() ────────────────────────────────────────────────────────────────────

class TestStep:

    def test_returns_four_tuple(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        result = env.step(SQLAction(query="SELECT 1"))
        assert len(result) == 4

    def test_returns_correct_types(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        obs, reward, done, info = env.step(SQLAction(query="SELECT 1"))
        assert isinstance(obs, SQLObservation)
        assert isinstance(reward, SQLReward)
        assert isinstance(done, bool)
        assert isinstance(info, dict)

    def test_step_increments_count(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        obs, _, _, _ = env.step(SQLAction(query="SELECT 1"))
        assert obs.step_count == 1

    def test_reward_value_in_range(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        _, reward, _, _ = env.step(SQLAction(query="SELECT 1"))
        assert -1.0 <= reward.value <= 1.0

    def test_syntax_error_gives_negative_reward(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        _, reward, _, _ = env.step(SQLAction(sql="TOTALLY BROKEN @#$"))
        assert reward.value < 0.0

    def test_correct_query_gives_positive_reward(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        # Ground truth for fix_syntax_simple 
        correct = (
            "SELECT name, department, salary "
            "FROM employees WHERE department = 'Engineering'"
        )
        _, reward, _, _ = env.step(SQLAction(query=correct))
        assert reward.value > 0.0

    def test_solved_flag_set_on_correct_query(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        correct = (
            "SELECT name, department, salary "
            "FROM employees WHERE department = 'Engineering'"
        )
        _, _, _, info = env.step(SQLAction(query=correct))
        assert info["solved"] is True

    def test_done_true_on_solve(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        correct = (
            "SELECT name, department, salary "
            "FROM employees WHERE department = 'Engineering'"
        )
        _, _, done, _ = env.step(SQLAction(query=correct))
        assert done is True

    def test_done_true_at_step_limit(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)  # max_steps=5
        for _ in range(5):
            _, _, done, _ = env.step(SQLAction(query="SELECT 1"))
            if done:
                break
        assert done is True

    def test_step_after_done_raises(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        correct = (
            "SELECT name, department, salary "
            "FROM employees WHERE department = 'Engineering'"
        )
        env.step(SQLAction(query=correct))
        with pytest.raises(RuntimeError, match="done"):
            env.step(SQLAction(query="SELECT 1"))

    def test_step_before_reset_raises(self):
        env = SQLQueryEnv(seed=42)
        with pytest.raises(RuntimeError, match="reset"):
            env.step(SQLAction(query="SELECT 1"))

    def test_previous_attempts_accumulated(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        env.step(SQLAction(query="SELECT 1"))
        obs, _, _, _ = env.step(SQLAction(query="SELECT 2"))
        assert len(obs.previous_attempts) == 2
        assert "SELECT 1" in obs.previous_attempts[0]
        assert "SELECT 2" in obs.previous_attempts[1]

    def test_error_message_populated_on_bad_query(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        obs, _, _, _ = env.step(SQLAction(sql="SELECT * FROM nonexistent_table"))
        assert len(obs.error_message) > 0

    def test_error_message_empty_on_valid_query(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        obs, _, _, _ = env.step(SQLAction(query="SELECT 1"))
        assert obs.error_message == ""

    def test_delete_blocked(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        obs, _, _, _ = env.step(SQLAction(sql="DELETE FROM employees"))
        assert "not permitted" in obs.error_message.lower()

    def test_info_has_required_keys(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        _, _, _, info = env.step(SQLAction(query="SELECT 1"))
        for key in ["task_id", "step", "cumulative_reward", "episode_score", "solved"]:
            assert key in info, f"Missing key: {key}"

    def test_episode_score_in_range(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        _, _, _, info = env.step(SQLAction(query="SELECT 1"))
        assert 0.0 <= info["episode_score"] <= 1.0

    def test_multiple_episodes_independent(self):
        env = SQLQueryEnv(seed=42)
        # Episode 1
        env.reset(task_id=EASY_TASK)
        env.step(SQLAction(query="SELECT 1"))
        env.step(SQLAction(query="SELECT 2"))

        # Episode 2 — should be clean
        obs = env.reset(task_id=MEDIUM_TASK)
        assert obs.step_count == 0
        assert obs.task_id == MEDIUM_TASK
        assert obs.previous_attempts == []


# ── state() ───────────────────────────────────────────────────────────────────

class TestState:

    def test_returns_task_state(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        state = env.state()
        assert isinstance(state, TaskState)

    def test_state_before_reset_raises(self):
        env = SQLQueryEnv(seed=42)
        with pytest.raises(RuntimeError, match="reset"):
            env.state()

    def test_state_contains_ground_truth(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        state = env.state()
        assert "SELECT" in state.ground_truth_query.upper()

    def test_state_task_id_matches_reset(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=MEDIUM_TASK)
        state = env.state()
        assert state.task_id == MEDIUM_TASK

    def test_state_step_count_updates(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        env.step(SQLAction(query="SELECT 1"))
        env.step(SQLAction(query="SELECT 2"))
        state = env.state()
        assert state.step_count == 2

    def test_ground_truth_not_in_observation(self):
        """Ground truth must never leak into the agent's observation."""
        env = SQLQueryEnv(seed=42)
        obs = env.reset(task_id=EASY_TASK)
        state = env.state()

        # Ground truth should not appear verbatim in observation fields
        gt = state.ground_truth_query.strip()
        observable_text = (
            obs.schema_ddl
            + obs.broken_query
            + obs.expected_description
            + obs.error_message
        )
        # We don't assert it's completely absent (descriptions may mention columns)
        # but it should not be the full query
        assert gt not in observable_text or len(gt) < 20


# ── reward structure ──────────────────────────────────────────────────────────

class TestRewardStructure:

    def test_breakdown_fields_exist(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        _, reward, _, _ = env.step(SQLAction(query="SELECT 1"))
        b = reward.breakdown
        assert hasattr(b, "result_match")
        assert hasattr(b, "syntax_penalty")
        assert hasattr(b, "efficiency_bonus")

    def test_syntax_penalty_on_broken_query(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        _, reward, _, _ = env.step(SQLAction(query="@#$ NOT SQL"))
        assert reward.breakdown.syntax_penalty < 0.0

    def test_result_match_on_correct_query(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        correct = (
            "SELECT name, department, salary "
            "FROM employees WHERE department = 'Engineering'"
        )
        _, reward, _, _ = env.step(SQLAction(query=correct))
        assert reward.breakdown.result_match == 1.0

    def test_success_flag_on_perfect_score(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        correct = (
            "SELECT name, department, salary "
            "FROM employees WHERE department = 'Engineering'"
        )
        _, reward, _, _ = env.step(SQLAction(query=correct))
        assert reward.success is True

    def test_done_and_success_consistent(self):
        env = SQLQueryEnv(seed=42)
        env.reset(task_id=EASY_TASK)
        correct = (
            "SELECT name, department, salary "
            "FROM employees WHERE department = 'Engineering'"
        )
        _, reward, done, _ = env.step(SQLAction(query=correct))
        assert reward.done == done
        assert reward.success == done  # success implies done