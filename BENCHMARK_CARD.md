# BENCHMARK_CARD — SQLBench-OpenEnv

## Overview

SQLBench-OpenEnv is a reinforcement learning benchmark for evaluating large language
models on SQL repair. An agent receives a broken query, a database schema, and a
description of the expected result. It submits corrected queries across up to N steps
and receives graded feedback after each attempt.

| Property | Value |
|---|---|
| Tasks | 6 (2 easy, 2 medium, 2 hard) |
| Grading | Deterministic (SQLite execution + result comparison) |
| Reward range | [-1.0, 1.0] |
| Step budget | 5–12 depending on difficulty |
| LLM-as-judge | No |
| Reproducibility | Fixed seed (42), temperature 0.1 |

---

## Task Definitions

| ID | Difficulty | Max steps | Fault class | Schema complexity |
|---|---|---|---|---|
| `fix_syntax_simple` | easy | 5 | Missing comma in SELECT list | 1 table, 5 columns |
| `fix_table_name` | easy | 5 | Misspelled table identifier | 1 table, 5 columns |
| `fix_join_logic` | medium | 8 | Wrong JOIN predicate column | 2 tables, FK relationship |
| `fix_aggregate_logic` | medium | 8 | Wrong GROUP BY / HAVING column | 2 tables, aggregation |
| `multi_constraint_query` | hard | 10 | Four simultaneous logic errors | 3 tables, subquery |
| `ecommerce_supply_chain` | hard | 12 | Triple-join + aggregation filter | 4 tables, complex FK graph |

---

## Grader Design

### Why deterministic grading over LLM-as-judge

LLM-as-judge approaches introduce at least three problems for a benchmark like this.
First, they add a second model's error distribution on top of the first — if the judge
halluccinates that a query is correct, the signal is permanently poisoned for that
episode. Second, they are expensive: each evaluation call doubles the API cost and
latency budget. Third, and most importantly, SQL has an oracle: you can just run both
queries against the same database and compare the result sets. There is no ambiguity in
"did the agent return the right rows?" the way there is in open-ended writing tasks.

This benchmark uses SQLite as the execution oracle. The ground-truth query and the
agent's query are both executed against an identical in-memory database seeded with
deterministic fixture data. The grader compares result sets using set-based row
matching (order-independent) and produces a score in [0.0, 1.0] with defined partial
credit levels.

The tradeoff is that strict result-set comparison penalizes stylistically different but
semantically equivalent queries. A query that returns the right rows via a different
JOIN order is correct; the grader handles this via frozenset comparison. A query that
returns the right data with an extra unrequested column gets 0.7 rather than 1.0 — a
deliberate choice to reward precision in column selection, which matters in production
SQL review.

### Result-match scoring levels

| Score | Condition |
|---|---|
| 1.0 | Exact match: same rows, same columns, order ignored |
| 0.9 | All correct rows present, but extra rows included |
| 0.7 | Right data with extra or missing columns (shared cols match) |
| 0.3–0.7 | Partial row overlap (≥50% correct rows, same columns) |
| 0.1–0.3 | Partial row overlap (<50% correct rows) |
| 0.2 | Correct row count but wrong values |
| 0.0 | Completely wrong, empty, or query failed to execute |

---

## Reward Function Design

### Why this specific reward shape

Sparse reward — only rewarding the final correct answer — collapses multi-step episodes
into a bandit problem. The agent has no signal about whether step 3 was closer than
step 2, making it impossible for an RL training loop to credit intermediate progress.

The step reward is:

```
R = result_match × 0.70      # primary signal — did you get the right data?
  + column_match  × 0.10     # secondary — did you select the right columns?
  + row_count     × 0.05     # weak — right number of rows, even if values wrong?
  + efficiency    × 0.10     # hard tasks only — penalise SELECT * and deep nesting
  + progress_delta           # improvement over agent's prior best this episode
  + step_bonus               # small bonus for early solve, small penalty at timeout
  + syntax_penalty           # -0.1 to -0.2 for execution failure
clipped to [-1.0, 1.0]
```

The 0.70 weight on `result_match` keeps it dominant — you cannot game the benchmark
by writing queries that get partial column credit without actually solving the task.
`progress_delta` is the key RL shaping term: it rewards any step where the agent's
best result so far improves, even if it hasn't solved the task yet. This prevents the
agent from learning to repeat a "safe" partial query that locks in some reward.

The `step_bonus` is intentionally small (±0.1 at most) to avoid distorting the primary
signal. A model that solves the task on step 5 should not score significantly worse
than one that solves it on step 1 — the point is whether the model can repair SQL,
not whether it guesses correctly on the first try.

### What I would change at scale

**More tasks, harder schemas.** Six tasks with 1–4 tables is enough to differentiate
models on basic SQL reasoning, but not enough to stress schema-awareness at realistic
production scale (20–50 table databases, views, CTEs, window functions). The next
version should include tasks generated from real open-source database dumps (e.g.,
Northwind, Chinook) with adversarial perturbations.

**Adversarial cases.** The current fault set is fixed and known. A more rigorous
benchmark would generate novel faults at evaluation time — e.g., randomly swap a
column alias, inject an off-by-one in a LIMIT clause, flip a JOIN direction — so
models cannot overfit to the specific broken queries in the task definitions.

**Variance runs.** Each task is currently run once (seed 42). Running 3–5 seeds and
reporting mean ± std would separate models that happen to solve a task from those that
reliably do so. The infrastructure already supports `runs_per_task` in `models.yaml`.

---

## Leaderboard (as of 2026-08-23, seed=42)

Run `python run_benchmark.py` to reproduce.

| Rank | Model | Easy | Medium | Hard | Avg | Solved |
|---|---|---|---|---|---|---|
| 1 | Qwen2.5-Coder 32B | 0.85 | 0.62 | 0.31 | 0.593 | 3/6 |
| 2 | GPT-4o-mini | 0.78 | 0.54 | 0.24 | 0.520 | 2/6 |
| 3 | Ling-2.6-1T (Free) | 0.00 | 0.00 | 0.07 | 0.023 | 0/6 |

Key observations:
- Frontier models solve easy tasks reliably but fail hard tasks consistently. The gap
  between easy (0.78–0.85) and hard (0.24–0.31) scores confirms that multi-table join
  repair and complex constraint reasoning remain unsolved at current capability levels.
- The free/small open-weight baseline (Ling-2.6-1T) scored 0.023 average — near zero.
  Its 0.07 on hard tasks is a scoring artifact from partial column credit, not actual
  problem-solving. It solved zero tasks outright. This is a useful calibration point:
  small instruction-tuned models produce syntactically valid SQL but fail at semantic
  repair even on simple schemas.
- Medium tasks are the most informative discriminator. Easy tasks approach ceiling for
  frontier models; hard tasks are near floor for everyone. Medium tasks — wrong JOIN
  predicates, broken GROUP BY logic — separate models that understand relational
  semantics from those that pattern-match.

---

## Reproducibility

```bash
git clone https://github.com/nareshchandu17/SQLBench-OpenEnv
cd SQLBench-OpenEnv
pip install -r requirements.txt
cp .env.example .env          # add your OPENROUTER_API_KEY
python run_benchmark.py       # writes to benchmark_output/
```

All randomness is controlled by `seed: 42` in `benchmark/models.yaml`.
Database fixture data is deterministic per task. Temperature is fixed at 0.1.

---

## Limitations

- SQLite only. Production SQL (window functions, CTEs, dialect-specific syntax) is not
  covered. Results may not transfer to PostgreSQL or BigQuery repair tasks.
- Static fault set. The six broken queries are fixed; models could in principle be
  evaluated against a leaked test set. Adversarial regeneration is on the roadmap.
- Single-turn grading. The grader compares final result sets, not intermediate query
  plans. A model that arrives at the right answer through wrong reasoning gets full
  credit — this is appropriate for a repair benchmark but limits interpretability.
- No cost normalisation. GPT-4o-mini costs roughly 50× more per token than the free
  baseline. The leaderboard ranks by accuracy; a cost-adjusted Pareto frontier is not
  computed here.
