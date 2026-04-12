---
title: My Openenv
emoji: 🦀
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
license: mit
short_description: SQL debugging benchmark environment for evaluating LLM agent
---

# SQLBench-OpenEnv

[![OpenEnv](https://img.shields.io/badge/OpenEnv-0.1.0-blue)](https://github.com/openenv/openenv)
[![Python](https://img.shields.io/badge/Python-3.11-green)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

A reproducible [OpenEnv](https://github.com/openenv/openenv) benchmark for
evaluating large language model capability on SQL debugging, correction,
and optimization tasks.

---

## 30-Second Demo

Run the full benchmark locally:

```bash
git clone https://huggingface.co/spaces/YOUR_HF_USERNAME/sql-query-env
cd sql-query-env
pip install -r requirements.txt
python run_benchmark.py
```

Example output:
```
SQLBench-OpenEnv Benchmark

Models evaluated: 3
Tasks per model: 6

Leaderboard
1. Llama 3.3 70B   Avg: 0.208
2. Gemma 27B       Avg: 0.208
3. Dolphin 24B     Avg: 0.023
```

---

## Architecture

```text
      Broken SQL Query
              │
              ▼
       SQLBench-OpenEnv
              │
      ┌───────┴───────┐
      │               │
SQLite Execution    Deterministic Grader
      │               │
      └───────┬───────┘
              ▼
       Reward Function
              │
              ▼
       Benchmark Runner
              │
              ▼
  Leaderboard + Error Analysis
```

---

```
Model             Easy    Medium    Hard     Avg
────────────────────────────────────────────────
Llama 3.3 70B     0.05    0.05      0.52    0.21
Gemma 27B         0.52    0.05      0.05    0.21
Dolphin 24B       0.00    0.00      0.07    0.02

Run: python run_benchmark.py
```

---

## Key Findings

Running SQLBench-OpenEnv on three instruction-tuned models revealed several consistent failure patterns:

- Models frequently produce **syntactically valid SQL but semantically incorrect queries**.
- **Reference errors** (wrong column/table names) are the most common failure category.
- Large models (70B) perform significantly better on **nested logic tasks**, but still struggle with complex multi-table joins.

These results suggest that current LLMs require stronger **schema reasoning and relational planning** to reliably repair SQL queries in production environments.

---

## What this is

SQLBench-OpenEnv simulates a real-world task: a developer hands you a
broken SQL query and a description of what it should return. You must
diagnose the fault and produce a working fix.

The environment exposes the standard OpenEnv interface. At each step the
agent receives a database schema, the broken query, any error message from
its last attempt, and a preview of its last result. The agent submits a
corrected SQL query. A deterministic grader executes both the agent's
query and the hidden ground-truth against an in-memory SQLite database
and scores the result match — no LLM-as-judge, no subjectivity.

**Why SQL debugging?**  
Developers already use LLMs to write and fix SQL daily. Evaluating how
reliably models perform this task matters for production deployment
decisions. Existing benchmarks measure generation from scratch (Spider,
BIRD) — this benchmark measures repair, which is the harder and more
common real-world task.

---

## Quick start

```bash
git clone https://huggingface.co/spaces/YOUR_HF_USERNAME/sql-query-env
cd sql-query-env

pip install -r requirements.txt

# Configure your .env file
cp .env.example .env

# Run the full benchmark
python run_benchmark.py
```

---

## Using the environment directly

```python
from env.environment import SQLQueryEnv
from env.models import SQLAction

env = SQLQueryEnv(seed=42)

# Start an episode
obs = env.reset(task_id="fix_join_logic")
print(obs.schema_ddl)
print(obs.broken_query)
print(obs.expected_description)

# Submit a corrected query
action = SQLAction(query="""
    SELECT c.customer_name, p.product, p.amount
    FROM customers c
    JOIN purchases p ON c.customer_id = p.customer_id
    WHERE p.amount > 50
""")

obs, reward, done, info = env.step(action)
print(f"Score: {info['episode_score']:.3f}")
print(f"Solved: {info['solved']}")
print(f"Reward breakdown: {reward.breakdown}")
```

---

## HTTP API (when running as HF Space)

```bash
# Health check
curl https://YOUR_SPACE.hf.space/health

# Start episode
curl -X POST https://YOUR_SPACE.hf.space/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "fix_syntax_simple"}'

# Submit action
curl -X POST https://YOUR_SPACE.hf.space/step \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT name, department, salary FROM employees WHERE department = '\''Engineering'\''"}'

# Get state (includes ground truth — for debugging)
curl https://YOUR_SPACE.hf.space/state

# List all tasks
curl https://YOUR_SPACE.hf.space/tasks

# Get leaderboard
curl https://YOUR_SPACE.hf.space/leaderboard
```

---

## Observation and action spaces

**Observation** (`SQLObservation`):

| Field | Type | Description |
|---|---|---|
| `task_id` | str | Current task |
| `schema_ddl` | str | Database schema |
| `broken_query` | str | Query to fix |
| `error_message` | str | SQLite error from last attempt |
| `expected_description` | str | What the correct result should be |
| `step_count` | int | Steps used |
| `max_steps` | int | Step limit |
| `previous_attempts` | list[str] | Queries submitted this episode |
| `last_execution_result` | str or null | First 5 rows of last result |

**Action** (`SQLAction`):

| Field | Type | Description |
|---|---|---|
| `query` | str | A SQL SELECT statement |

Only SELECT is permitted. Destructive operations return an error message
and consume a step.

---

## Tasks

| ID | Difficulty | Max steps | Error type |
|---|---|---|---|
| `fix_syntax_simple` | easy | 5 | Missing comma in SELECT |
| `fix_table_name` | easy | 5 | Wrong table name |
| `fix_join_logic` | medium | 8 | Wrong JOIN column |
| `fix_aggregate_logic` | medium | 8 | Wrong GROUP BY column |
| `multi_constraint_query` | hard | 10 | Four simultaneous errors |
| `fix_nested_subquery_logic` | hard | 10 | Invalid aggregation in subquery |

See [BENCHMARK_CARD.md](BENCHMARK_CARD.md) for full task descriptions
and grader design.

---

## Reward function

Reward is computed at every step (not only at success):

```
R = result_match × 0.70
  + column_match  × 0.10
  + row_count     × 0.05
  + efficiency    × 0.05   (hard tasks only)
  + progress_delta         (improvement over prior best)
  + step_bonus             (early solve bonus, timeout penalty)
  + syntax_penalty         (execution failure penalty)

Clipped to [-1.0, 1.0]
```

---

## Run Benchmark

**Reproducible multi-model benchmark** (generates leaderboard, ≈ 8–15 minutes):

```bash
python run_benchmark.py
```

This runs all configured models against all benchmark tasks and generates:

- **`benchmark_output/leaderboard.json`** — Ranked summary by average score
- **`benchmark_output/benchmark_results.json`** — Per-model, per-task details
- **`benchmark_output/error_taxonomy.json`** — Error analysis and breakdown

Expected output:

```
======================================================================
  SQLBench-OpenEnv Benchmark Runner
======================================================================

Running benchmark...

======================================================================
  Benchmark Results
======================================================================

Models evaluated: 3
Tasks per model: 6

Leaderboard:
──────────────────────────────────────────────────────────────────────
   1. Llama 3.3 70B             Avg: 0.208  Solved: 1/6
   2. Gemma 27B                 Avg: 0.208  Solved: 1/6
   3. Dolphin Mistral 24B       Avg: 0.023  Solved: 0/6
──────────────────────────────────────────────────────────────────────

Output files saved to: benchmark_output/
  • benchmark_results.json   (raw per-task data)
  • leaderboard.json         (summary rankings)
  • error_taxonomy.json      (failure analysis)

======================================================================
```

**Manual inference** (evaluate a single model baseline):

```bash
# Set environment variables for the baseline script
# (inference.py uses standard OpenAI client variables)
export LLAMA_API_KEY="sk-..." 
python inference.py
```

**Configure models** in `benchmark/models.yaml`.

---

## Interactive Benchmark Dashboard

After running the benchmark, visualize results on an interactive dashboard:

```bash
# Run benchmark (generates JSON output files)
python run_benchmark.py

# Start dashboard server
python server.py

# Open browser to http://localhost:7860
```

The dashboard displays:

- **📊 Leaderboard** — Model rankings by average score (easy/medium/hard breakdown)
- **📈 Model Scores** — Bar chart comparing average scores across models
- **🎚️ Difficulty** — Doughnut chart showing task performance by difficulty level
- **🐛 Error Taxonomy** — Pie chart of error categorization and frequencies
- **📋 Summary Stats** — Model count, task count, and error categories

**API Endpoints**:

- `GET /` — Interactive HTML dashboard with Chart.js visualizations
- `GET /leaderboard` — JSON API (programmatic leaderboard)
- `GET /error_taxonomy` — JSON API (programmatic error stats)
- `GET /health` — Health check
- `GET /docs` — Auto-generated API documentation (Swagger UI)

The dashboard gracefully handles missing benchmark data — it displays helpful
prompts and runs the benchmark dynamically as needed. Perfect for demos and judge reviews.

---

## Docker

```bash
docker build -t sql-query-env .
docker run -p 7860:7860 \
  -e API_BASE_URL="https://router.huggingface.co/v1" \
  -e HF_TOKEN="hf_..." \
  -e MODEL_NAME="meta-llama/Llama-3.1-8B-Instruct" \
  sql-query-env
```

---

## Repository structure

```
sql-query-env/
├── openenv.yaml              OpenEnv spec metadata
├── Dockerfile                Container build
├── requirements.txt          Pinned dependencies
├── inference.py              Baseline + benchmark runner
├── server.py                 FastAPI server (HF Spaces)
├── README.md
├── BENCHMARK_CARD.md         Research-style benchmark documentation
│
├── env/
│   ├── environment.py        SQLQueryEnv (reset/step/state)
│   ├── models.py             Pydantic observation/action/reward models
│   ├── tasks.py              Task definitions
│   ├── graders.py            Deterministic graders
│   ├── database.py           SQLite manager
│   └── reward.py             Reward function
│
└── benchmark/
    ├── models.yaml           Model registry for benchmark runs
    ├── runner.py             Multi-model evaluation loop
    ├── leaderboard.py        Leaderboard generation
    └── error_taxonomy.py     Error classification system
```

---

## Infrastructure

- Runtime: CPU-only, ≤ 2 vCPU, ≤ 8 GB RAM
- Inference runtime: < 20 minutes
- No GPU required
- No external database — SQLite runs in-process
- No external API calls in the environment itself (only in `inference.py`)

---

## License

MIT. See [LICENSE](LICENSE).

---

## Related work

- [OpenEnv](https://github.com/openenv/openenv) — the RL environment framework this builds on
- [Spider](https://yale-lily.github.io/spider) — text-to-SQL benchmark (generation, not repair)
- [BIRD](https://bird-bench.github.io) — large-scale text-to-SQL benchmark
- [HELM](https://crfm.stanford.edu/helm/) — holistic LLM evaluation framework
- [LM Evaluation Harness](https://github.com/EleutherAI/lm-evaluation-harness) — EleutherAI evaluation suite

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
