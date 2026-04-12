"""
benchmark/runner.py

Benchmark runner: evaluates multiple LLMs on all SQLBench tasks.
Produces structured JSON results for leaderboard generation.

Design constraints respected:
- 2 vCPU / 8GB RAM: no parallel execution, sequential only
- < 20 min total: max_steps kept low, models limited to HF-hosted small models
- Deterministic: fixed seed, temperature=0.1, same prompt format for all models
"""
import os
import sys
import json
import time
import textwrap
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
import yaml
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))
from sql_query_env.environment import SQLQueryEnv
from sql_query_env.models import SQLAction
from benchmark.error_taxonomy import ErrorCounts, classify_error

# ── Rate Limit Protection ───────────────────────────────────────────────────
RATE_LIMIT_DELAY = 8  # Seconds between API calls
MAX_RETRIES = 3       # Max retries for 429 errors
RETRY_WAIT = 10       # Seconds to wait between retries

# ── Prompt (identical across all models for fair comparison) ──────────────────
SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert SQL developer. You will be given:
    1. A database schema (CREATE TABLE statements)
    2. A broken SQL query that contains errors
    3. A description of what the correct query should return

    Output ONLY the corrected SQL query — nothing else.
    No explanations, no markdown code blocks, no preamble.
    Only SELECT statements are permitted.
""").strip()

# ── Parallel Execution Configuration ──────────────────────────────────────────
MAX_WORKERS = 5  # Number of parallel tasks per model (safe for API rate limits)


def build_user_prompt(obs) -> str:
    parts = [
        f"## Schema\n{obs.schema_ddl}",
        f"## Task\n{obs.expected_description}",
        f"## Broken query\n{obs.broken_query}",
    ]
    if obs.error_message:
        parts.append(f"## Last error\n{obs.error_message}")
    if obs.previous_attempts:
        parts.append(f"## Previous attempt\n{obs.previous_attempts[-1]}")
    parts.append("Corrected SQL:")
    return "\n\n".join(parts)


def extract_sql(text: str) -> str:
    text = text.strip()
    for fence in ["```sql", "```"]:
        if fence in text.lower():
            start = text.lower().find(fence) + len(fence)
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
    lines = [l for l in text.split("\n") if l.strip().upper().startswith("SELECT")]
    return "\n".join(lines).strip() if lines else text


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class TaskResult:
    task_id: str
    difficulty: str
    episode_score: float
    steps_taken: int
    solved: bool
    error_category: str
    total_reward: float
    duration_seconds: float
    api_errors: List[str] = field(default_factory=list)


@dataclass
class ModelResult:
    model_id: str
    model_name: str
    task_results: List[TaskResult] = field(default_factory=list)
    error_counts: ErrorCounts = field(default_factory=ErrorCounts)

    def score_by_difficulty(self) -> Dict[str, float]:
        by_diff: Dict[str, List[float]] = {}
        for tr in self.task_results:
            by_diff.setdefault(tr.difficulty, []).append(tr.episode_score)
        return {
            diff: round(sum(scores) / len(scores), 3)
            for diff, scores in by_diff.items()
        }

    def average_score(self) -> float:
        if not self.task_results:
            return 0.0
        return round(
            sum(tr.episode_score for tr in self.task_results) / len(self.task_results),
            3,
        )


# ── Runner ────────────────────────────────────────────────────────────────────

class BenchmarkRunner:
    """
    Evaluates multiple models against all benchmark tasks.
    Sequential execution — safe for 2vCPU / 8GB.
    """

    def __init__(
        self,
        config_path: str = "benchmark/models.yaml",
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.api_base_url = api_base_url or os.getenv(
            "API_BASE_URL", "https://openrouter.ai/api/v1"
        )
        # Fallback for backward compatibility (single-key mode)
        self.default_api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("HF_TOKEN") or os.getenv("API_KEY", "")
        # Don't create shared env — each thread will create its own
        # to avoid SQLite threading issues
        self.max_steps = self.config["settings"]["max_steps_per_episode"]
        self.seed = self.config["settings"]["seed"]

        # Flatten task list from config
        self.benchmark_tasks: List[Dict] = []
        for difficulty, task_ids in self.config["benchmark_tasks"].items():
            for task_id in task_ids:
                self.benchmark_tasks.append(
                    {"id": task_id, "difficulty": difficulty}
                )

    def _make_client(self, model_cfg: Dict) -> OpenAI:
        """Create OpenAI client with model-specific API key."""
        # If model specifies api_key_env, use that; otherwise fall back to default
        api_key = ""
        if "api_key_env" in model_cfg:
            api_key = os.getenv(model_cfg["api_key_env"], "")
        
        # Fall back to default key if model-specific key not found
        if not api_key:
            api_key = self.default_api_key
        
        if not api_key or api_key == "dummy":
            print(f"      ⚠ Warning: No API key found for {model_cfg['name']}. Using 'dummy' (will likely 401).")

        return OpenAI(
            base_url=self.api_base_url,
            api_key=api_key or "dummy",
        )

    def _run_episode(
        self,
        client: OpenAI,
        model_cfg: Dict,
        task_id: str,
        difficulty: str,
    ) -> TaskResult:
        """Run one episode of one model on one task."""
        # Small delay to avoid rate limits
        time.sleep(0.2)
        
        t0 = time.time()
        # Create fresh environment for this thread to avoid SQLite threading issues
        env = SQLQueryEnv(seed=self.seed)
        obs = env.reset(
            task_id=task_id,
            seed=self.config["settings"]["seed"],
        )
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        episode_score = 0.0
        total_reward = 0.0
        solved = False
        last_error = ""
        last_result = []
        last_query = obs.broken_query
        steps = 0

        api_errors = []
        for step in range(self.max_steps):
            # 1. Enforce delay before every API call
            time.sleep(RATE_LIMIT_DELAY)
            
            messages.append({"role": "user", "content": build_user_prompt(obs)})

            raw = ""
            for attempt in range(MAX_RETRIES):
                try:
                    resp = client.chat.completions.create(
                        model=model_cfg["model_string"],
                        messages=messages,
                        max_tokens=model_cfg.get("max_tokens", 512),
                        temperature=model_cfg.get("temperature", 0.1),
                    )
                    raw = resp.choices[0].message.content or ""
                    break # Success!
                except Exception as e:
                    err_msg = str(e)
                    # Check if it's a rate limit error (HTTP 429)
                    if "429" in err_msg or "rate limit" in err_msg.lower():
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_WAIT)
                            continue
                    
                    api_errors.append(f"Step {step+1} (Attempt {attempt+1}): {err_msg}")
                    raw = f"SELECT * FROM sqlite_master LIMIT 0"
                    break # Generic error or max retries

            sql = extract_sql(raw)
            messages.append({"role": "assistant", "content": raw})

            try:
                action = SQLAction(query=sql)
                obs, reward, done, info = env.step(action)

                # Safe dictionary access with fallbacks
                total_reward += reward.value
                episode_score = max(0.0, min(1.0, info.get("episode_score", 0.0)))
                solved = info.get("solved", False)
                last_error = obs.error_message
            except Exception as e:
                print(f"      Step {step+1} error: {e}")
                # Graceful fallback: treat as failed step
                episode_score = max(0.0, min(1.0, episode_score))
                solved = False
                last_error = f"Step error: {str(e)}"
                continue
            last_result = []  # not exposed directly but grader has it
            last_query = sql
            steps = step + 1

            if done:
                break

        # Classify the final-step error
        error_cat = classify_error(
            error_message=last_error,
            agent_result=last_result,
            expected_result=[],  # grader handles internally
            query=last_query,
            episode_score=episode_score,
        )

        duration = time.time() - t0
        return TaskResult(
            task_id=task_id,
            difficulty=difficulty,
            episode_score=round(episode_score, 3),
            steps_taken=steps,
            solved=solved,
            error_category=error_cat,
            total_reward=round(total_reward, 3),
            duration_seconds=round(duration, 1),
            api_errors=api_errors,
        )

    def run(self) -> List[ModelResult]:
        """Run the full benchmark. Returns list of ModelResult objects."""
        models = self.config["models"]
        results: List[ModelResult] = []

        total_episodes = len(models) * len(self.benchmark_tasks)
        episode_num = 0
        wall_start = time.time()

        print(f"\n{'='*64}")
        print(f"  SQLBench-OpenEnv  |  {len(models)} models × {len(self.benchmark_tasks)} tasks")
        print(f"{'='*64}")

        for model_cfg in models:
            model_result = ModelResult(
                model_id=model_cfg["id"],
                model_name=model_cfg["name"],
            )
            client = self._make_client(model_cfg)

            print(f"\n  Model: {model_cfg['name']}")
            print(f"  {'─'*50}")

            # Parallel execution of tasks for this model
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # Submit all tasks at once
                futures = {
                    executor.submit(
                        self._run_episode,
                        client,
                        model_cfg,
                        task_info["id"],
                        task_info["difficulty"]
                    ): task_info
                    for task_info in self.benchmark_tasks
                }

                # Process results as they complete
                completed = 0
                for future in futures:
                    task_info = futures[future]
                    task_id = task_info["id"]
                    difficulty = task_info["difficulty"]
                    episode_num += 1

                    print(
                        f"  [{episode_num:02d}/{total_episodes}] "
                        f"{task_id:<32} [{difficulty}] ...",
                        end="",
                        flush=True,
                    )

                    try:
                        tr = future.result()
                        model_result.task_results.append(tr)
                        model_result.error_counts.add(tr.error_category)

                        status = "SOLVED" if tr.solved else f"{tr.episode_score:.2f}"
                        print(f" {status} ({tr.duration_seconds:.1f}s)")
                        
                        # Print buffered API errors cleanly
                        for err in tr.api_errors:
                            print(f"      ⚠ API error: {err}")

                    except Exception as e:
                        print(f" ERROR: {e}")
                        traceback.print_exc()
                        # Record zero score so benchmark doesn't abort
                        model_result.task_results.append(TaskResult(
                            task_id=task_id,
                            difficulty=difficulty,
                            episode_score=0.0,
                            steps_taken=0,
                            solved=False,
                            error_category="syntax_error",
                            total_reward=0.0,
                            duration_seconds=0.0,
                        ))

                    # Safety: abort if approaching 18-minute wall clock
                    elapsed = time.time() - wall_start
                    if elapsed > 18 * 60:
                        print(f"\n  WARNING: Approaching 20-min limit. Stopping early.")
                        results.append(model_result)
                        return results

            results.append(model_result)

        total_time = time.time() - wall_start
        print(f"\n{'='*64}")
        print(f"  Benchmark complete in {total_time:.1f}s")
        print(f"{'='*64}\n")

        return results