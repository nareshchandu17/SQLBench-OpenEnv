---
title: SQLBench-OpenEnv
emoji: 🦀
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
license: mit
short_description: SQL debugging benchmark environment for evaluating LLM agents
---

# SQLBench-OpenEnv

[![CI](https://github.com/nareshchandu17/SQLBench-OpenEnv/actions/workflows/ci.yml/badge.svg)](https://github.com/nareshchandu17/SQLBench-OpenEnv/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![OpenEnv](https://img.shields.io/badge/OpenEnv-0.1.0-blue)](https://github.com/openenv/openenv)

A reproducible [OpenEnv](https://github.com/openenv/openenv) benchmark for evaluating
large language models on SQL debugging and repair. An agent receives a broken query, a
schema, and a description of the correct result — it must diagnose and fix the fault
within a step budget.

No LLM-as-judge. Grading is fully deterministic: both the agent's query and the
ground-truth are executed against an in-memory SQLite database and the result sets are
compared directly.

---

## Leaderboard (seed=42, 2026-08-23)

| Rank | Model | Easy | Medium | Hard | Avg | Solved |
|---|---|---|---|---|---|---|
| 1 | Qwen2.5-Coder 32B | 0.85 | 0.62 | 0.31 | **0.593** | 3/6 |
| 2 | GPT-4o-mini | 0.78 | 0.54 | 0.24 | **0.520** | 2/6 |
| 3 | Ling-2.6-1T (Free) | 0.00 | 0.00 | 0.07 | **0.023** | 0/6 |

Reproduce with `python run_benchmark.py`. Full per-task breakdown in
[`benchmark_output/benchmark_results.json`](benchmark_output/benchmark_results.json).
Design decisions and grader rationale in [BENCHMARK_CARD.md](BENCHMARK_CARD.md).

---

## What this is

SQLBench-OpenEnv simulates a task developers face daily: a broken SQL query, a schema,
and a description of what it should return. The agent must diagnose the fault and
produce a working fix.

The environment exposes the standard OpenEnv interface. At each step the agent receives
the schema, the broken query, any error message from its last attempt, and a preview of
its last result. A deterministic grader compares result sets — no subjectivity, no
secondary model calls.

**Why SQL repair, not generation?**
Existing benchmarks (Spider, BIRD) measure generation from scratch. Repair is harder
and more common in production: the developer already has a query, it's broken, and they
need it fixed under time pressure. This benchmark measures that task directly.

---

## Quick start

```bash
git clone https://github.com/nareshchandu17/SQLBench-OpenEnv
cd SQLBench-OpenEnv
pip install -r requirements.txt
cp .env.example .env          # add OPENROUTER_API_KEY
python run_benchmark.py       # writes to benchmark_output/
```

---

## Use the environment directly

```python
from sql_query_env.environment import SQLQueryEnv
from sql_query_env.models import SQLAction

env = SQLQueryEnv(seed=42)

obs = env.reset(task_id="fix_join_logic")
print(obs.schema_ddl)
print(obs.broken_query)
print(obs.expected_description)

action = SQLAction(query="""
    SELECT c.customer_name, p.product, p.amount
    FROM customers c
    JOIN purchases p ON c.customer_id = p.customer_id
    WHERE p.amount > 50
""")

obs, reward, done, info = env.step(action)
print(f"Score: {info['episode_score']:.3f}  Solved: {info['solved']}")
print(f"Reward: {reward.value:.3f}  Breakdown: {reward.breakdown}")
```

---

## HTTP API

```bash
# Health check
curl https://nareshchandu17-sql-query-env.hf.space/health

# Start episode
curl -X POST https://nareshchandu17-sql-query-env.hf.space/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "fix_syntax_simple"}'

# Submit a query
curl -X POST https://nareshchandu17-sql-query-env.hf.space/step \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT name, department, salary FROM employees WHERE department = '\''Engineering'\''"}'

# Leaderboard
curl https://nareshchandu17-sql-query-env.hf.space/leaderboard

# All tasks
curl https://nareshchandu17-sql-query-env.hf.space/tasks
```

---

## Observation and action spaces

**Observation** (`SQLObservation`):

| Field | Type | Description |
|---|---|---|
| `task_id` | str | Current task identifier |
| `schema_ddl` | str | CREATE TABLE statements |
| `broken_query` | str | The query to fix |
| `error_message` | str | SQLite error from last attempt, empty if none |
| `expected_description` | str | Natural language description of the correct result |
| `step_count` | int | Steps used so far |
| `max_steps` | int | Step budget |
| `previous_attempts` | list[str] | All queries submitted this episode |
| `last_execution_result` | str or null | First 5 rows of last result |

**Action** (`SQLAction`):

| Field | Type | Description |
|---|---|---|
| `query` | str | A SQL SELECT statement |

Only SELECT is permitted. Destructive operations (DELETE, DROP, INSERT) return an error
and consume a step.

---

## Tasks

| ID | Difficulty | Max steps | Fault class |
|---|---|---|---|
| `fix_syntax_simple` | easy | 5 | Missing comma in SELECT list |
| `fix_table_name` | easy | 5 | Misspelled table identifier |
| `fix_join_logic` | medium | 8 | Wrong JOIN predicate column |
| `fix_aggregate_logic` | medium | 8 | Wrong GROUP BY / HAVING column |
| `multi_constraint_query` | hard | 10 | Four simultaneous logic errors |
| `ecommerce_supply_chain` | hard | 12 | Triple-join + aggregation filter |

Full task descriptions, grader design, and design decisions in
[BENCHMARK_CARD.md](BENCHMARK_CARD.md).

---

## Reward function

Computed at every step (not only at success):

```
R = result_match × 0.70      # did you return the right rows?
  + column_match  × 0.10     # did you select the right columns?
  + row_count     × 0.05     # right number of rows, even if values wrong?
  + efficiency    × 0.10     # hard tasks only — penalise SELECT * and deep nesting
  + progress_delta           # improvement over your prior best this episode
  + step_bonus               # small bonus for early solve, small penalty at timeout
  + syntax_penalty           # -0.1 to -0.2 for execution failure

Clipped to [-1.0, 1.0]
```

---

## Architecture

```
Broken SQL Query
       │
       ▼
 SQLBench-OpenEnv
       │
  ┌────┴────┐
  │         │
SQLite    Deterministic Grader
  │         │
  └────┬────┘
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

## Run benchmark

```bash
python run_benchmark.py
```

Runs all models in `benchmark/models.yaml` against all tasks. Produces:

- `benchmark_output/leaderboard.json` — ranked summary
- `benchmark_output/benchmark_results.json` — per-model, per-task detail
- `benchmark_output/error_taxonomy.json` — error category breakdown

Configure models in `benchmark/models.yaml`. All models use a single
`OPENROUTER_API_KEY` (gateway pattern).

---

## Dashboard

```bash
python server.py          # http://localhost:7860
```

Shows leaderboard, per-difficulty bar charts, and error taxonomy. Requires
`benchmark_output/` to be populated first.

---

## Docker

```bash
docker build -t sql-query-env .
docker run -p 7860:7860 \
  -e OPENROUTER_API_KEY="sk-or-v1-..." \
  sql-query-env
```

---

## Repository structure

```
sql-query-env/
├── README.md
├── BENCHMARK_CARD.md         Task definitions, grader design, design decisions
├── openenv.yaml              OpenEnv spec metadata
├── Dockerfile
├── requirements.txt
├── run_benchmark.py
├── server.py                 FastAPI dashboard server
│
├── sql_query_env/
│   ├── environment.py        SQLQueryEnv — reset / step / state
│   ├── models.py             Pydantic observation / action / reward types
│   ├── tasks.py              Task definitions (schema, broken query, ground truth)
│   ├── graders.py            Deterministic graders
│   ├── database.py           SQLite manager (setup, execute, teardown)
│   └── reward.py             Step reward function
│
├── benchmark/
│   ├── models.yaml           Model registry
│   ├── runner.py             Multi-model evaluation loop
│   ├── leaderboard.py        Leaderboard + error taxonomy generation
│   └── error_taxonomy.py     Error classification
│
├── tests/
│   ├── test_graders.py       Grader unit tests (no API calls)
│   ├── test_benchmark.py     Benchmark layer tests (no API calls)
│   └── test_env.py           Environment integration tests (no API calls)
│
└── benchmark_output/
    ├── leaderboard.json
    ├── benchmark_results.json
    └── error_taxonomy.json
```

---

## Infrastructure

- CPU-only, ≤ 2 vCPU, ≤ 8 GB RAM
- No GPU required
- No external database — SQLite runs in-process
- API calls only in `run_benchmark.py` (via OpenRouter)

---

## License

MIT. See [LICENSE](LICENSE).

---

## Related work

- [OpenEnv](https://github.com/openenv/openenv) — the RL environment framework this builds on
- [Spider](https://yale-lily.github.io/spider) — text-to-SQL benchmark (generation, not repair)
- [BIRD](https://bird-bench.github.io) — large-scale text-to-SQL benchmark
- [HELM](https://crfm.stanford.edu/helm/) — holistic LLM evaluation
- [LM Evaluation Harness](https://github.com/EleutherAI/lm-evaluation-harness) — EleutherAI evaluation suite
