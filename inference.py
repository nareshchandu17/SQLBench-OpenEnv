"""
inference.py — SQLBench-OpenEnv baseline + benchmark runner.

Modes:
  BENCHMARK_MODE=0 (default): Fast single-model baseline. Used by hackathon validator.
  BENCHMARK_MODE=1           : Full multi-model benchmark. Produces leaderboard.

Environment variables:
  API_BASE_URL   API endpoint (default: HF router)
  HF_TOKEN       API key
  MODEL_NAME     Model for single-model baseline
  BENCHMARK_MODE 0 or 1 (default: 0)
"""
import os
import sys
import json
import time
import textwrap
from typing import List, Dict, Any

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from env.environment import SQLQueryEnv
from env.models import SQLAction

API_BASE_URL   = os.getenv("API_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_NAME     = os.getenv("MODEL_NAME", "meta-llama/llama-3.3-70b-instruct")
HF_TOKEN       = os.getenv("HF_TOKEN")
BENCHMARK_MODE = os.getenv("BENCHMARK_MODE", "0") == "1"

MAX_STEPS   = 5
MAX_TOKENS  = 512
TEMPERATURE = 0.1

# ── Rate Limit Protection ───────────────────────────────────────────────────
RATE_LIMIT_DELAY = 8  # Seconds between API calls
MAX_RETRIES = 3       # Max retries for 429 errors
RETRY_WAIT = 10       # Seconds to wait between retries

BENCHMARK_TASKS = [
    ("fix_syntax_simple",      "easy"),
    ("fix_join_logic",         "medium"),
    ("multi_constraint_query", "hard"),
    ("ecommerce_supply_chain", "hard"),
]

SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert SQL developer. Output ONLY the corrected SQL query.
    No explanations. No markdown. Only SELECT statements are permitted.
""").strip()


def build_prompt(obs) -> str:
    parts = [
        f"Schema:\n{obs.schema_ddl}",
        f"Task: {obs.expected_description}",
        f"Broken query:\n{obs.broken_query}",
    ]
    if obs.error_message:
        parts.append(f"Last error: {obs.error_message}")
    if obs.previous_attempts:
        parts.append(f"Previous attempt:\n{obs.previous_attempts[-1]}")
    parts.append("Corrected SQL:")
    return "\n\n".join(parts)


def extract_sql(text: str) -> str:
    text = text.strip()
    for fence in ["```sql", "```"]:
        if fence in text.lower():
            s = text.lower().find(fence) + len(fence)
            e = text.find("```", s)
            if e > s:
                return text[s:e].strip()
    lines = [l for l in text.split("\n") if l.strip().upper().startswith("SELECT")]
    return "\n".join(lines).strip() if lines else text


def run_baseline() -> int:
    """Single-model baseline. Always runs. Used by hackathon validator."""
    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN or "dummy")
    env = SQLQueryEnv(seed=42)
    results = []

    for task_id, difficulty in BENCHMARK_TASKS:
        print(f"\n  Task: {task_id}  [{difficulty}]")
        obs = env.reset(task_id=task_id, seed=42)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        episode_score = 0.0
        solved = False
        steps = 0
        all_rewards = []

        print(f"[START] task={task_id} env=SQLBench-OpenEnv model={MODEL_NAME}")

        for step in range(MAX_STEPS):
            # 1. Enforce delay before every API call
            time.sleep(RATE_LIMIT_DELAY)
            
            messages.append({"role": "user", "content": build_prompt(obs)})
            
            raw = ""
            for attempt in range(MAX_RETRIES):
                try:
                    resp = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=messages,
                        max_tokens=MAX_TOKENS,
                        temperature=TEMPERATURE,
                    )
                    raw = resp.choices[0].message.content or ""
                    break # Success!
                except Exception as e:
                    err_msg = str(e)
                    if "429" in err_msg or "rate limit" in err_msg.lower():
                        if attempt < MAX_RETRIES - 1:
                            print(f"    Rate limit hit. Retrying in {RETRY_WAIT}s... (Attempt {attempt+1}/{MAX_RETRIES})")
                            time.sleep(RETRY_WAIT)
                            continue
                    print(f"    API error: {e}")
                    raw = "SELECT 1"
                    break

            sql = extract_sql(raw)
            messages.append({"role": "assistant", "content": raw})
            obs, reward, done, info = env.step(SQLAction(query=sql))
            episode_score = info["episode_score"]
            solved = info["solved"]
            steps = step + 1
            all_rewards.append(reward.score)
            
            print(f"    Step {steps}: score={episode_score:.3f} | {'SOLVED' if solved else 'continuing'}")
            print(f"[STEP] step={steps} action={sql.replace(chr(10), ' ')} reward={reward.score:.2f} done={str(done).lower()} error={obs.error_message or 'null'}")
            if done:
                break

        results.append({
            "task_id": task_id,
            "difficulty": difficulty,
            "episode_score": episode_score,
            "solved": solved,
            "steps": steps,
        })
        print(f"[END] success={str(solved).lower()} steps={steps} score={episode_score:.2f} rewards={','.join([f'{r:.2f}' for r in all_rewards])}")

    # Summary
    env.close()
    avg = sum(r["episode_score"] for r in results) / len(results)
    print(f"\n{'='*60}")
    print(f"  BASELINE RESULTS")
    print(f"{'='*60}")
    for r in results:
        bar = "█" * int(r["episode_score"] * 20)
        print(
            f"  [{r['difficulty']:<6}] {r['task_id']:<30} "
            f"{r['episode_score']:.3f}  {bar}"
        )
    print(f"\n  Average: {avg:.3f}")
    print(f"{'='*60}")

    output = {"model": MODEL_NAME, "tasks": results, "average_score": avg}
    print("\nJSON_RESULTS:", json.dumps(output))
    return 0


def run_benchmark() -> int:
    """Full multi-model benchmark. Produces leaderboard JSON."""
    from benchmark.runner import BenchmarkRunner
    from benchmark.leaderboard import generate_leaderboard, print_leaderboard

    runner = BenchmarkRunner(
        config_path="benchmark/models.yaml",
        api_base_url=API_BASE_URL,
        api_key=HF_TOKEN,
    )
    results = runner.run()
    leaderboard = generate_leaderboard(results, output_dir="benchmark_output")
    print_leaderboard(leaderboard)

    # Also emit JSON for programmatic consumption
    print("\nJSON_RESULTS:", json.dumps({
        "benchmark": "SQLBench-OpenEnv",
        "average_scores": {
            e["model_id"]: e["average"]
            for e in leaderboard["rankings"]
        },
    }))
    return 0


if __name__ == "__main__":
    if BENCHMARK_MODE:
        sys.exit(run_benchmark())
    else:
        sys.exit(run_baseline())