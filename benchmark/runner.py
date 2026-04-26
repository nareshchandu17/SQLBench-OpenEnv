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
import random
import textwrap
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor

# Note: We don't load .env here to prioritize environment variables over .env file

sys.path.insert(0, str(Path(__file__).parent.parent))
from sql_query_env.environment import SQLQueryEnv
from sql_query_env.models import SQLAction
from benchmark.error_taxonomy import ErrorCounts, classify_error

# ── Rate Limit Protection ───────────────────────────────────────────────────
LAST_REQUEST_TIME = 0
MIN_INTERVAL = 2  # Minimum seconds between requests

def throttle():
    """Global throttling to prevent request bursts."""
    global LAST_REQUEST_TIME
    now = time.time()
    elapsed = now - LAST_REQUEST_TIME
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    LAST_REQUEST_TIME = time.time()

def retry_with_backoff(api_call, model_name: str, max_retries: int = 5):
    """
    Production-grade retry with exponential backoff and rate limit awareness.
    """
    for attempt in range(max_retries):
        try:
            return api_call()
        except Exception as e:
            err_msg = str(e)
            
            # Check for rate limit errors
            if "429" in err_msg or "rate limit" in err_msg.lower():
                # Exponential backoff with jitter (capped at 60s)
                wait = min(60, (2 ** attempt) + random.uniform(0, 1))
                
                # Check for Retry-After header if available
                if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = max(wait, float(retry_after))
                        except ValueError:
                            pass
                
                print(f"[RETRY] {model_name} | Attempt {attempt + 1}/{max_retries} | Rate limited. Waiting {wait:.2f}s...")
                time.sleep(wait)
                
                if attempt == max_retries - 1:
                    raise Exception(f"Max retries exceeded for {model_name} due to rate limiting")
            else:
                # Non-rate-limit error, re-raise immediately
                raise
    
    raise Exception(f"Max retries exceeded for {model_name}")

MAX_RETRIES = 5  # Increased for better resilience

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

        # Use global provider config from YAML
        self.api_base_url = api_base_url or self.config.get("base_url", "https://openrouter.ai/api/v1")
        
        # Load global API key (gateway pattern)
        # Priority: 1. Direct parameter, 2. Environment variable, 3. .env file
        api_key_env = self.config.get("api_key_env", "OPENROUTER_API_KEY")
        self.default_api_key = api_key or os.environ.get(api_key_env, "").strip()
        
        # If still empty, try loading from .env as fallback
        if not self.default_api_key:
            from dotenv import load_dotenv
            load_dotenv()
            self.default_api_key = os.environ.get(api_key_env, "").strip()
        
        if not self.default_api_key:
            raise ValueError(f"Missing required environment variable: {api_key_env}")
        
        print(f"[DEBUG] Using API key: {self.default_api_key[:8]}...")
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

    def _make_client_config(self, model_cfg: Dict) -> Dict:
        """Create HTTP client config using global gateway pattern."""
        # Backward compatibility warning
        if "api_key_env" in model_cfg:
            print(f"      ⚠ Warning: Per-model API keys are deprecated. Using global gateway.")
        
        # All models use the same global API key (gateway pattern)
        return {
            "base_url": self.api_base_url,
            "api_key": self.default_api_key,
            "headers": {
                "Authorization": f"Bearer {self.default_api_key}",
                "Content-Type": "application/json"
            }
        }

    def _run_episode(
        self,
        client_config: Dict,
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
            # 1. Apply global throttling
            throttle()
            
            messages.append({"role": "user", "content": build_user_prompt(obs)})

            # 2. Make API call with exponential backoff
            raw = ""
            try:
                def api_call():
                    payload = {
                        "model": model_cfg["model_string"],
                        "messages": messages,
                        "max_tokens": model_cfg.get("max_tokens", 512),
                        "temperature": model_cfg.get("temperature", 0.1),
                    }
                    
                    resp = requests.post(
                        f"{client_config['base_url']}/chat/completions",
                        headers=client_config["headers"],
                        json=payload,
                        timeout=30
                    )
                    
                    if resp.status_code == 200:
                        return resp.json()
                    else:
                        raise Exception(f"HTTP {resp.status_code}: {resp.text}")
                
                data = retry_with_backoff(api_call, model_cfg["name"])
                raw = data["choices"][0]["message"]["content"] or ""
                
            except Exception as e:
                err_msg = str(e)
                if "Max retries exceeded" in err_msg:
                    # Rate limit exhaustion - mark as rate limited but continue
                    api_errors.append(f"Step {step+1}: Rate limited after max retries")
                    raw = f"SELECT * FROM sqlite_master LIMIT 0"
                    print(f"[RATE_LIMITED] {model_cfg['name']} - Step {step+1} exhausted rate limits")
                else:
                    # Other API error
                    api_errors.append(f"Step {step+1}: {err_msg}")
                    raw = f"SELECT * FROM sqlite_master LIMIT 0"
                    break

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
            client_config = self._make_client_config(model_cfg)

            print(f"\n  Model: {model_cfg['name']}")
            print(f"  {'─'*50}")

            # Sequential execution for rate limit resilience
            # Use parallel only for non-rate-limited scenarios
            use_parallel = False  # Disabled for rate limit safety
            
            if use_parallel:
                # Parallel execution (original approach)
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    futures = {
                        executor.submit(
                            self._run_episode,
                            client_config,
                            model_cfg,
                            task_info["id"],
                            task_info["difficulty"]
                        ): task_info
                        for task_info in self.benchmark_tasks
                    }

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

                            for err in tr.api_errors:
                                print(f"      ⚠ API error: {err}")

                        except Exception as e:
                            print(f" ERROR: {e}")
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
            else:
                # Sequential execution (rate limit safe)
                print(f"  [SEQUENTIAL] Running tasks sequentially for rate limit safety")
                for task_info in self.benchmark_tasks:
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
                        tr = self._run_episode(client_config, model_cfg, task_id, difficulty)
                        model_result.task_results.append(tr)
                        model_result.error_counts.add(tr.error_category)

                        status = "SOLVED" if tr.solved else f"{tr.episode_score:.2f}"
                        print(f" {status} ({tr.duration_seconds:.1f}s)")

                        for err in tr.api_errors:
                            print(f"      ⚠ API error: {err}")

                    except Exception as e:
                        print(f" ERROR: {e}")
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
                        results.append(model_result)
                        return results

            results.append(model_result)

        total_time = time.time() - wall_start
        print(f"\n{'='*64}")
        print(f"  Benchmark complete in {total_time:.1f}s")
        print(f"{'='*64}\n")

        return results