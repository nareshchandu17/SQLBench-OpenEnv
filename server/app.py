"""
server.py

Interactive benchmark dashboard for SQLBench-OpenEnv.
Runs on port 7860 for Hugging Face Spaces.

Serves:
  GET /              → Interactive HTML dashboard with leaderboard and charts
  GET /leaderboard   → JSON: leaderboard data
  GET /error_taxonomy → JSON: error taxonomy
  GET /health        → JSON: health status
"""

import json
import uuid
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import FastAPI, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from dataclasses import asdict

from sql_query_env.environment import SQLQueryEnv
from sql_query_env.models import SQLAction
from sql_query_env.tasks import TASKS, TASK_INDEX

# Database imports
from database import init_db, get_db
from benchmark.models import BenchmarkRun, BenchmarkSummary, LeaderboardView, ModelPerformance

# ── Configuration ──────────────────────────────────────────────────────────

APP_TITLE = "SQLBench-OpenEnv"
PORT = 7860
OUTPUT_DIR = Path("benchmark_output")

# ── FastAPI Setup ──────────────────────────────────────────────────────────

app = FastAPI(
    title=APP_TITLE,
    description="Interactive benchmark dashboard for SQL query debugging environment",
    version="1.0.0",
)

# Enable CORS for Hugging Face Spaces
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Environment Instance ───────────────────────────────────────────

env = SQLQueryEnv(seed=42)

# ── Job Store for Background Benchmark Execution ───────────────────────

jobs: Dict[str, Dict[str, Any]] = {}  # In-memory job store

# ── Database Initialization ───────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup."""
    init_db()
    print("✅ Database initialized")

# ── Helper Functions ───────────────────────────────────────────────────────

def load_json_safe(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON file safely with fallback default structure."""
    try:
        if not file_path.exists():
            return None
        with open(file_path, "r") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return None
            return data
    except (json.JSONDecodeError, IOError, ValueError) as e:
        print(f"Warning: Could not load {file_path}: {e}")
        return None


def get_leaderboard_data() -> Optional[Dict[str, Any]]:
    """Load leaderboard JSON from benchmark_output/."""
    return load_json_safe(OUTPUT_DIR / "leaderboard.json")


def get_error_taxonomy_data() -> Optional[Dict[str, Any]]:
    """Load error taxonomy JSON from benchmark_output/."""
    return load_json_safe(OUTPUT_DIR / "error_taxonomy.json")


def format_timestamp(iso_string: Optional[str]) -> str:
    """Format ISO timestamp to readable format."""
    if not iso_string:
        return "Not available"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return iso_string


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def save_benchmark_result(run_id: str, model_cfg: Dict, task_info: Dict, result: Any):
    """Save benchmark result to database."""
    from database import SessionLocal
    from benchmark.models import BenchmarkRun, serialize_errors, serialize_extra_data, create_run_id
    
    db = SessionLocal()
    try:
        # Extract result data
        if hasattr(result, 'model_dump'):
            result_data = result.model_dump()
        else:
            result_data = asdict(result)
        
        # Create benchmark run entry
        db_entry = BenchmarkRun(
            run_id=run_id,
            model_name=model_cfg.get("name", "Unknown"),
            model_id=model_cfg.get("id", "unknown"),
            task_id=task_info.get("id", "unknown"),
            task_difficulty=task_info.get("difficulty", "unknown"),
            episode_score=result_data.get("episode_score", 0.0),
            total_reward=result_data.get("total_reward", 0.0),
            steps_taken=result_data.get("steps_taken", 0),
            solved=result_data.get("solved", False),
            duration_seconds=result_data.get("duration_seconds", 0.0),
            error_category=result_data.get("error_category", ""),
            api_errors=serialize_errors(result_data.get("api_errors", [])),
            status="completed"
        )
        
        db.add(db_entry)
        db.commit()
        
    except Exception as e:
        print(f"Failed to save benchmark result: {e}")
        db.rollback()
    finally:
        db.close()


def save_model_performance(run_id: str, results: List[Any]):
    """Save individual model performance data for analytics."""
    from database import SessionLocal
    from benchmark.models import ModelPerformance, serialize_errors
    from collections import defaultdict
    
    db = SessionLocal()
    try:
        # Group results by model
        model_results = defaultdict(list)
        
        for result in results:
            if hasattr(result, 'model_name'):
                model_name = result.model_name
            elif hasattr(result, 'model_id'):
                # Look up model name from config if needed
                model_name = result.model_id
            else:
                continue
                
            model_results[model_name].append(result)
        
        # Calculate and save performance metrics for each model
        for model_name, model_task_results in model_results.items():
            if not model_task_results:
                continue
            
            # Calculate metrics
            scores = []
            solve_rates = []
            durations = []
            easy_scores = []
            medium_scores = []
            hard_scores = []
            
            error_categories = defaultdict(int)
            
            for task_result in model_task_results:
                if hasattr(task_result, 'episode_score'):
                    scores.append(task_result.episode_score)
                elif hasattr(task_result, 'model_dump'):
                    data = task_result.model_dump()
                    scores.append(data.get('episode_score', 0.0))
                else:
                    scores.append(0.0)
                
                # Solve rate
                solved = hasattr(task_result, 'solved') and task_result.solved
                solve_rates.append(1.0 if solved else 0.0)
                
                # Duration
                if hasattr(task_result, 'duration_seconds'):
                    durations.append(task_result.duration_seconds)
                else:
                    durations.append(0.0)
                
                # Error categories
                if hasattr(task_result, 'error_category'):
                    error_categories[task_result.error_category] += 1
            
            # Calculate averages
            avg_score = sum(scores) / len(scores) if scores else 0.0
            avg_solve_rate = sum(solve_rates) / len(solve_rates) if solve_rates else 0.0
            avg_duration = sum(durations) / len(durations) if durations else 0.0
            
            # Create model performance entry
            performance_entry = ModelPerformance(
                run_id=run_id,
                model_name=model_name,
                model_id=model_name.lower().replace(' ', '-'),
                average_score=avg_score,
                tasks_solved=int(sum(solve_rates)),
                total_tasks=len(model_task_results),
                solve_rate=avg_solve_rate,
                avg_duration=avg_duration,
                total_duration=sum(durations),
                error_categories=serialize_extra_data(dict(error_categories))
            )
            
            db.add(performance_entry)
        
        db.commit()
        
    except Exception as e:
        print(f"Failed to save model performance: {e}")
        db.rollback()
    finally:
        db.close()


def save_benchmark_summary(run_id: str, model_configs: List[Dict], task_configs: List[Dict], 
                         settings: Dict, results: List[Any], status: str = "completed"):
    """Save benchmark summary to database."""
    from database import SessionLocal
    from benchmark.models import BenchmarkSummary, serialize_extra_data
    from datetime import datetime
    
    db = SessionLocal()
    try:
        # Calculate summary metrics
        total_tasks = len(task_configs) * len(model_configs)
        completed_tasks = len(results)
        
        # Calculate average score
        if results:
            if hasattr(results[0], 'episode_score'):
                scores = [r.episode_score for r in results]
            else:
                scores = [r.get('episode_score', 0) for r in results]
            average_score = sum(scores) / len(scores)
            total_duration = sum(r.get('duration_seconds', 0) for r in results)
        else:
            average_score = 0.0
            total_duration = 0.0
        
        # Create summary entry
        summary = BenchmarkSummary(
            run_id=run_id,
            started_at=datetime.now(),
            completed_at=datetime.now() if status == "completed" else None,
            status=status,
            models_config=serialize_extra_data(model_configs),
            tasks_config=serialize_extra_data(task_configs),
            settings=serialize_extra_data(settings),
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            average_score=average_score,
            total_duration=total_duration
        )
        
        db.add(summary)
        db.commit()
        
    except Exception as e:
        print(f"Failed to save benchmark summary: {e}")
        db.rollback()
    finally:
        db.close()


def run_benchmark_background(job_id: str):
    """Background task to run the full benchmark pipeline with database persistence."""
    try:
        # Update job status
        jobs[job_id]["status"] = "running"
        jobs[job_id]["started_at"] = datetime.now().isoformat()
        
        # Import and run benchmark
        import sys
        from pathlib import Path as PathLib
        sys.path.insert(0, str(PathLib(__file__).parent.parent))
        from benchmark.runner import BenchmarkRunner
        from benchmark.models import create_run_id
        
        # Initialize runner and create run ID
        runner = BenchmarkRunner()
        run_id = create_run_id()
        jobs[job_id]["run_id"] = run_id
        
        total_tasks = len(runner.config["models"]) * len(runner.benchmark_tasks)
        
        # Update total tasks count
        jobs[job_id]["total_tasks"] = total_tasks
        jobs[job_id]["completed_tasks"] = 0
        jobs[job_id]["current_model"] = ""
        jobs[job_id]["current_task"] = ""
        
        # Save initial summary
        save_benchmark_summary(
            run_id=run_id,
            model_configs=runner.config["models"],
            task_configs=runner.benchmark_tasks,
            settings=runner.config["settings"],
            results=[],
            status="running"
        )
        
        # Custom progress tracking with database persistence
        original_run_episode = runner._run_episode
        all_results = []
        
        def tracked_run_episode(client, model_cfg, task_id, difficulty):
            # Update progress
            jobs[job_id]["completed_tasks"] += 1
            jobs[job_id]["current_model"] = model_cfg["name"]
            jobs[job_id]["current_task"] = f"{task_id} [{difficulty}]"
            
            # Run original episode
            result = original_run_episode(client, model_cfg, task_id, difficulty)
            
            # Save to database
            task_info = {"id": task_id, "difficulty": difficulty}
            save_benchmark_result(run_id, model_cfg, task_info, result)
            all_results.append(result)
            
            return result
        
        # Monkey patch for progress tracking
        runner._run_episode = tracked_run_episode
        
        # Run benchmark
        results = runner.run()
        
        # Store results in job
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        jobs[job_id]["results"] = [asdict(result) for result in results]
        
        # Save model performance data for analytics
        save_model_performance(run_id, results)
        
        # Save final summary to database
        save_benchmark_summary(
            run_id=run_id,
            model_configs=runner.config["models"],
            task_configs=runner.benchmark_tasks,
            settings=runner.config["settings"],
            results=results,
            status="completed"
        )
        
        # Generate output files (same as CLI)
        from benchmark.report import generate_reports
        generate_reports(results, OUTPUT_DIR)
        
    except Exception as e:
        # Mark as failed
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["failed_at"] = datetime.now().isoformat()
        
        # Save failed summary if we have a run_id
        if "run_id" in jobs[job_id]:
            try:
                save_benchmark_summary(
                    run_id=jobs[job_id]["run_id"],
                    model_configs=runner.config["models"] if 'runner' in locals() else [],
                    task_configs=runner.benchmark_tasks if 'runner' in locals() else [],
                    settings=runner.config["settings"] if 'runner' in locals() else {},
                    results=all_results if 'all_results' in locals() else [],
                    status="failed"
                )
            except:
                pass  # Don't let summary saving fail the error reporting
        
        import traceback
        print(f"Benchmark job {job_id} failed: {e}")
        traceback.print_exc()


# ── HTML Template Generation ───────────────────────────────────────────────

def generate_dashboard_html(
    leaderboard: Optional[Dict],
    error_taxonomy: Optional[Dict],
) -> str:
    """Generate interactive dashboard HTML with Chart.js visualization."""

    # Extract data with defaults
    rankings = leaderboard.get("rankings", []) if leaderboard else []
    timestamp = leaderboard.get("timestamp") if leaderboard else None
    error_data = error_taxonomy.get("global_error_rates", {}) if error_taxonomy else {}

    # Prepare leaderboard chart data with safe access
    model_names = json.dumps([escape_html(r.get("model_name", "Unknown")) for r in rankings])
    model_scores = json.dumps([
        max(0.0, min(1.0, r.get("average_score", r.get("average", 0.0))))
        for r in rankings
    ])

    # Difficulty breakdown with safe access and value clamping
    try:
        difficulty_easy = sum(max(0.0, min(1.0, r.get("easy", 0.0))) for r in rankings) if rankings else 0.0
        difficulty_medium = sum(max(0.0, min(1.0, r.get("medium", 0.0))) for r in rankings) if rankings else 0.0
        difficulty_hard = sum(max(0.0, min(1.0, r.get("hard", 0.0))) for r in rankings) if rankings else 0.0
    except (TypeError, ValueError):
        difficulty_easy = difficulty_medium = difficulty_hard = 0.0

    # Error categories with safe value access
    try:
        error_labels = json.dumps(list(error_data.keys()) if error_data else [])
        error_values = list(error_data.values()) if error_data else []
        # Clamp error percentages to [0, 100]
        error_percentages = json.dumps([max(0.0, min(100.0, float(v))) for v in error_values])
    except (TypeError, ValueError):
        error_labels = json.dumps([])
        error_percentages = json.dumps([])

    # Check if data available
    has_leaderboard = bool(rankings)
    has_errors = bool(error_data)

    # Build table rows with safe dictionary access and fallbacks
    table_rows = ""
    if has_leaderboard:
        for i, entry in enumerate(rankings, 1):
            model_name = escape_html(entry.get('model_name', 'Unknown'))
            easy = max(0.0, min(1.0, entry.get('easy', 0.0)))
            medium = max(0.0, min(1.0, entry.get('medium', 0.0)))
            hard = max(0.0, min(1.0, entry.get('hard', 0.0)))
            avg = max(0.0, min(1.0, entry.get('average_score', entry.get('average', 0.0))))
            
            table_rows += f"""
            <tr>
                <td class="rank">{i}</td>
                <td class="model-name">{model_name}</td>
                <td><span class="score">{easy:.3f}</span></td>
                <td><span class="score">{medium:.3f}</span></td>
                <td><span class="score">{hard:.3f}</span></td>
                <td><span class="score high">{avg:.3f}</span></td>
            </tr>"""
    else:
        table_rows = """
            <tr>
                <td colspan="6" class="no-data">
                    No benchmark results yet. Run: <code>python run_benchmark.py</code>
                </td>
            </tr>"""

    # Build chart initialization scripts
    model_chart_init = ""
    if has_leaderboard:
        model_chart_init = f"""
        const modelCtx = document.getElementById('modelChart')?.getContext('2d');
        if (modelCtx) {{
            new Chart(modelCtx, {{
                type: 'bar',
                data: {{
                    labels: {model_names},
                    datasets: [{{
                        label: 'Average Score',
                        data: {model_scores},
                        backgroundColor: 'rgba(102, 126, 234, 0.7)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        borderWidth: 2,
                        borderRadius: 6,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    scales: {{
                        x: {{
                            beginAtZero: true,
                            max: 1.0,
                            ticks: {{ callback: (val) => val.toFixed(2) }}
                        }}
                    }},
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{ callbacks: {{ label: (ctx) => ctx.raw.toFixed(3) }} }}
                    }}
                }}
            }});
        }}
        """

    difficulty_chart_init = ""
    if has_leaderboard:
        difficulty_chart_init = f"""
        const diffCtx = document.getElementById('difficultyChart')?.getContext('2d');
        if (diffCtx) {{
            new Chart(diffCtx, {{
                type: 'doughnut',
                data: {{
                    labels: ['Easy', 'Medium', 'Hard'],
                    datasets: [{{
                        data: [{difficulty_easy:.2f}, {difficulty_medium:.2f}, {difficulty_hard:.2f}],
                        backgroundColor: [
                            'rgba(76, 175, 80, 0.7)',
                            'rgba(255, 193, 7, 0.7)',
                            'rgba(244, 67, 54, 0.7)'
                        ],
                        borderColor: [
                            'rgba(76, 175, 80, 1)',
                            'rgba(255, 193, 7, 1)',
                            'rgba(244, 67, 54, 1)'
                        ],
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{ padding: 15, font: {{ size: 12 }} }}
                        }},
                        tooltip: {{ callbacks: {{ label: (ctx) => ctx.raw.toFixed(2) }} }}
                    }}
                }}
            }});
        }}
        """

    error_chart_init = ""
    if has_errors:
        error_chart_init = f"""
        const errorCtx = document.getElementById('errorChart')?.getContext('2d');
        if (errorCtx) {{
            new Chart(errorCtx, {{
                type: 'pie',
                data: {{
                    labels: {error_labels},
                    datasets: [{{
                        data: {error_percentages},
                        backgroundColor: [
                            'rgba(255, 107, 107, 0.7)',
                            'rgba(255, 159, 64, 0.7)',
                            'rgba(255, 206, 86, 0.7)',
                            'rgba(75, 192, 192, 0.7)',
                            'rgba(54, 162, 235, 0.7)',
                            'rgba(153, 102, 255, 0.7)',
                        ],
                        borderColor: [
                            'rgba(255, 107, 107, 1)',
                            'rgba(255, 159, 64, 1)',
                            'rgba(255, 206, 86, 1)',
                            'rgba(75, 192, 192, 1)',
                            'rgba(54, 162, 235, 1)',
                            'rgba(153, 102, 255, 1)',
                        ],
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{ padding: 15, font: {{ size: 11 }} }}
                        }},
                        tooltip: {{ callbacks: {{ label: (ctx) => (ctx.parsed * 100).toFixed(1) + '%' }} }}
                    }}
                }}
            }});
        }}
        """

    # Assemble HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{APP_TITLE} · Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            background: white;
            border-radius: 12px;
            padding: 30px 40px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
        }}

        h1 {{
            color: #2d3748;
            font-size: 2em;
            margin-bottom: 10px;
        }}

        .subtitle {{
            color: #718096;
            font-size: 1em;
        }}

        .timestamp {{
            color: #a0aec0;
            font-size: 0.9em;
            margin-top: 15px;
            font-style: italic;
        }}

        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }}

        @media (max-width: 1024px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
        }}

        .card h2 {{
            color: #2d3748;
            font-size: 1.3em;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #e2e8f0;
        }}

        .leaderboard {{
            grid-column: 1 / -1;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}

        th {{
            background: #f7fafc;
            color: #2d3748;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #e2e8f0;
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
            color: #4a5568;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        .rank {{
            font-weight: 600;
            color: #667eea;
            width: 40px;
        }}

        .model-name {{
            font-weight: 500;
            color: #2d3748;
        }}

        .score {{
            background: #e6fffa;
            color: #0c7792;
            font-weight: 600;
            border-radius: 6px;
            padding: 4px 8px;
            display: inline-block;
            min-width: 50px;
            text-align: center;
        }}

        .score.high {{
            background: #c6f6d5;
            color: #22543d;
        }}

        .score.medium {{
            background: #fed7d7;
            color: #742a2a;
        }}

        .chart-wrapper {{
            position: relative;
            height: 350px;
        }}

        .no-data {{
            color: #a0aec0;
            font-style: italic;
            text-align: center;
            padding: 40px 20px;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}

        .stat {{
            background: #f7fafc;
            border-left: 4px solid #667eea;
            padding: 15px;
            border-radius: 6px;
        }}

        .stat-label {{
            color: #718096;
            font-size: 0.85em;
            margin-bottom: 5px;
        }}

        .stat-value {{
            color: #2d3748;
            font-size: 1.5em;
            font-weight: 700;
        }}

        footer {{
            text-align: center;
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.9em;
            margin-top: 40px;
        }}

        .api-link {{
            color: rgba(255, 255, 255, 0.9);
            text-decoration: none;
            margin: 0 10px;
        }}

        .api-link:hover {{
            text-decoration: underline;
        }}

        code {{
            background: #f5f5f5;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 {APP_TITLE}</h1>
            <p class="subtitle">Interactive benchmark dashboard for LLM evaluation on SQL debugging tasks</p>
            <div class="timestamp">Last updated: {format_timestamp(timestamp)}</div>
            
            <!-- Run Benchmark Button -->
            <div style="margin-top: 20px;">
                <button id="runBenchmarkBtn" onclick="runBenchmark()" 
                        style="background: #667eea; color: white; border: none; padding: 12px 24px; 
                               border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;
                               transition: all 0.3s ease;">
                    🚀 Run Benchmark
                </button>
                <div id="benchmarkStatus" style="margin-top: 15px; color: #718096; font-size: 14px;"></div>
                <div id="benchmarkProgress" style="margin-top: 10px;">
                    <div id="progressBar" style="display: none; width: 100%; height: 20px; background: #e2e8f0; border-radius: 10px; overflow: hidden;">
                        <div id="progressFill" style="height: 100%; background: #667eea; width: 0%; transition: width 0.3s ease;"></div>
                    </div>
                    <div id="progressText" style="margin-top: 5px; font-size: 12px; color: #718096;"></div>
                </div>
            </div>
        </header>

        <!-- Leaderboard Section -->
        <div class="card leaderboard">
            <h2>📊 Leaderboard</h2>
            <table>
                <thead>
                    <tr>
                        <th class="rank">#</th>
                        <th class="model-name">Model</th>
                        <th>Easy</th>
                        <th>Medium</th>
                        <th>Hard</th>
                        <th>Average</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>

        <!-- Charts Grid -->
        <div class="grid">
            <!-- Model Scores Chart -->
            <div class="card">
                <h2>📈 Average Scores by Model</h2>
                {'<div class="chart-wrapper"><canvas id="modelChart"></canvas></div>' if has_leaderboard else '<div class="no-data">Waiting for benchmark results</div>'}
            </div>

            <!-- Difficulty Breakdown -->
            <div class="card">
                <h2>🎚️ Difficulty Breakdown (All Models)</h2>
                {f'<div class="stats"><div class="stat"><div class="stat-label">Easy</div><div class="stat-value">{difficulty_easy:.2f}</div></div><div class="stat"><div class="stat-label">Medium</div><div class="stat-value">{difficulty_medium:.2f}</div></div><div class="stat"><div class="stat-label">Hard</div><div class="stat-value">{difficulty_hard:.2f}</div></div></div><div class="chart-wrapper"><canvas id="difficultyChart"></canvas></div>' if has_leaderboard else '<div class="no-data">Waiting for benchmark results</div>'}
            </div>

            <!-- Error Taxonomy -->
            <div class="card">
                <h2>🐛 Error Taxonomy</h2>
                {'<div class="chart-wrapper"><canvas id="errorChart"></canvas></div>' if has_errors else '<div class="no-data">No error taxonomy data available</div>'}
            </div>

            <!-- Analytics Section -->
            <div class="card">
                <h2>📊 Model Performance Analytics</h2>
                <div class="analytics-container">
                    <div class="analytics-controls">
                        <button id="loadAnalyticsBtn" onclick="loadAnalytics()" 
                                style="background: #667eea; color: white; border: none; padding: 8px 16px; 
                                       border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer;">
                            📈 Load Analytics
                        </button>
                        <div id="analyticsStatus" style="margin-left: 15px; color: #718096; font-size: 12px;"></div>
                    </div>
                    
                    <!-- Analytics Chart -->
                    <div id="analyticsChartContainer" style="margin-top: 20px; display: none;">
                        <div class="chart-wrapper">
                            <canvas id="analyticsChart"></canvas>
                        </div>
                    </div>
                    
                    <!-- Insights Panel -->
                    <div id="insightsPanel" style="margin-top: 20px; display: none;">
                        <h3 style="color: #2d3748; font-size: 1.1em; margin-bottom: 10px;">🧠 AI-Generated Insights</h3>
                        <div id="insightsList" style="background: #f8fafc; padding: 15px; border-radius: 8px; border-left: 4px solid #667eea;">
                            <div style="color: #718096; font-style: italic;">Loading insights...</div>
                        </div>
                    </div>
                    
                    <!-- Analytics Summary -->
                    <div id="analyticsSummary" style="margin-top: 15px; display: none;">
                        <div class="stats">
                            <div class="stat"><div class="stat-label">Models Tracked</div><div class="stat-value" id="modelsTracked">-</div></div>
                            <div class="stat"><div class="stat-label">Total Runs</div><div class="stat-value" id="totalRuns">-</div></div>
                            <div class="stat"><div class="stat-label">Data Points</div><div class="stat-value" id="dataPoints">-</div></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Stats Summary -->
            <div class="card">
                <h2>📋 Summary Stats</h2>
                <div class="stats">
                    <div class="stat"><div class="stat-label">Models</div><div class="stat-value">{len(rankings)}</div></div>
                    <div class="stat"><div class="stat-label">Tasks</div><div class="stat-value">5</div></div>
                    <div class="stat"><div class="stat-label">Errors</div><div class="stat-value">{len(error_data)}</div></div>
                    <div class="stat"><div class="stat-label">Time</div><div class="stat-label" style="color:#2d3748; font-weight:600;">{datetime.now().strftime("%H:%M:%S")}</div></div>
                </div>
            </div>
        </div>

        <footer>
            <a href="/leaderboard" class="api-link">📥 JSON Leaderboard</a> |
            <a href="/error_taxonomy" class="api-link">📥 Error Taxonomy</a> |
            <a href="/docs" class="api-link">📖 API Docs</a>
        </footer>
    </div>

    <script>
        {model_chart_init}
        {difficulty_chart_init}
        {error_chart_init}
        
        // Benchmark execution
        let currentJobId = null;
        let pollingInterval = null;
        
        async function runBenchmark() {{
            const btn = document.getElementById('runBenchmarkBtn');
            const status = document.getElementById('benchmarkStatus');
            const progressBar = document.getElementById('progressBar');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            
            // Disable button
            btn.disabled = true;
            btn.style.opacity = '0.6';
            btn.style.cursor = 'not-allowed';
            btn.textContent = '⏳ Starting...';
            
            status.textContent = 'Initializing benchmark...';
            progressBar.style.display = 'block';
            progressFill.style.width = '0%';
            progressText.textContent = '';
            
            try {{
                // Start benchmark
                const response = await fetch('/run-benchmark', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }}
                }});
                
                if (!response.ok) {{
                    throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                }}
                
                const data = await response.json();
                currentJobId = data.job_id;
                
                // Start polling
                startPolling();
                
            }} catch (error) {{
                console.error('Failed to start benchmark:', error);
                status.textContent = `❌ Failed to start: ${{error.message}}`;
                resetButton();
            }}
        }}
        
        function startPolling() {{
            if (pollingInterval) {{
                clearInterval(pollingInterval);
            }}
            
            pollingInterval = setInterval(async () => {{
                if (!currentJobId) return;
                
                try {{
                    const response = await fetch(`/status/${{currentJobId}}`);
                    const data = await response.json();
                    
                    updateProgress(data);
                    
                    if (data.status === 'completed' || data.status === 'failed') {{
                        clearInterval(pollingInterval);
                        pollingInterval = null;
                        handleCompletion(data);
                    }}
                }} catch (error) {{
                    console.error('Polling error:', error);
                    clearInterval(pollingInterval);
                    pollingInterval = null;
                    document.getElementById('benchmarkStatus').textContent = '❌ Connection lost';
                    resetButton();
                }}
            }}, 2000);
        }}
        
        function updateProgress(data) {{
            const status = document.getElementById('benchmarkStatus');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            const btn = document.getElementById('runBenchmarkBtn');
            
            if (data.status === 'running') {{
                const progress = data.total_tasks > 0 ? 
                    (data.completed_tasks / data.total_tasks * 100) : 0;
                
                progressFill.style.width = `${{progress}}%`;
                progressText.textContent = 
                    `${{data.completed_tasks}}/${{data.total_tasks}} tasks | ${{data.current_model}} | ${{data.current_task}}`;
                
                status.textContent = '🏃 Running benchmark...';
                btn.textContent = `⏳ Running (${{data.completed_tasks}}/${{data.total_tasks}})`;
            }}
        }}
        
        function handleCompletion(data) {{
            const status = document.getElementById('benchmarkStatus');
            const btn = document.getElementById('runBenchmarkBtn');
            const progressText = document.getElementById('progressText');
            
            if (data.status === 'completed') {{
                status.textContent = '✅ Benchmark completed successfully!';
                progressText.textContent = '🎉 All tasks completed. Refreshing results...';
                btn.textContent = '✅ Completed';
                
                // Refresh dashboard after 2 seconds
                setTimeout(() => {{
                    window.location.reload();
                }}, 2000);
                
            }} else if (data.status === 'failed') {{
                status.textContent = `❌ Benchmark failed: ${{data.error || 'Unknown error'}}`;
                progressText.textContent = '💥 Check logs for details';
                btn.textContent = '❌ Failed';
                resetButton();
            }}
        }}
        
        function resetButton() {{
            const btn = document.getElementById('runBenchmarkBtn');
            btn.disabled = false;
            btn.style.opacity = '1';
            btn.style.cursor = 'pointer';
            btn.textContent = '🚀 Run Benchmark';
        }}
        
        // Analytics functionality
        let analyticsChart = null;
        
        async function loadAnalytics() {{
            const btn = document.getElementById('loadAnalyticsBtn');
            const status = document.getElementById('analyticsStatus');
            const chartContainer = document.getElementById('analyticsChartContainer');
            const insightsPanel = document.getElementById('insightsPanel');
            const summaryPanel = document.getElementById('analyticsSummary');
            
            // Update UI state
            btn.disabled = true;
            btn.textContent = '⏳ Loading...';
            status.textContent = 'Fetching analytics data...';
            
            try {{
                // Fetch analytics data
                const response = await fetch('/api/analytics/model-comparison');
                if (!response.ok) {{
                    throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                }}
                
                const data = await response.json();
                
                // Update summary
                updateAnalyticsSummary(data.summary);
                
                // Create chart
                createAnalyticsChart(data.timeseries);
                
                // Display insights
                displayInsights(data.insights);
                
                // Show panels
                chartContainer.style.display = 'block';
                insightsPanel.style.display = 'block';
                summaryPanel.style.display = 'block';
                
                status.textContent = '✅ Analytics loaded successfully';
                btn.textContent = '🔄 Refresh';
                
            }} catch (error) {{
                console.error('Analytics loading failed:', error);
                status.textContent = `❌ Failed to load: ${{error.message}}`;
                btn.textContent = '📈 Load Analytics';
            }} finally {{
                btn.disabled = false;
            }}
        }}
        
        function updateAnalyticsSummary(summary) {{
            document.getElementById('modelsTracked').textContent = summary.total_models || 0;
            document.getElementById('totalRuns').textContent = summary.total_runs || 0;
            document.getElementById('dataPoints').textContent = summary.total_runs || 0;
        }}
        
        function createAnalyticsChart(timeseriesData) {{
            const ctx = document.getElementById('analyticsChart').getContext('2d');
            
            // Destroy existing chart if present
            if (analyticsChart) {{
                analyticsChart.destroy();
            }}
            
            // Prepare data for Chart.js
            const labels = [];
            const datasets = [];
            const colors = [
                '#667eea', '#f56565', '#48bb78', '#ed8936', '#9f7aea', '#38b2ac'
            ];
            
            // Collect all unique run IDs
            const allRunIds = new Set();
            Object.values(timeseriesData).forEach(modelData => {{
                modelData.forEach(point => {{
                    allRunIds.add(point.run_id.substring(0, 8)); // Shorten for display
                }});
            }});
            
            const sortedRunIds = Array.from(allRunIds).sort();
            
            // Create datasets for each model
            let colorIndex = 0;
            Object.entries(timeseriesData).forEach(([modelName, modelData]) => {{
                const scores = sortedRunIds.map(runId => {{
                    const point = modelData.find(p => p.run_id.substring(0, 8) === runId);
                    return point ? point.score : null;
                }});
                
                datasets.push({{
                    label: modelName,
                    data: scores,
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    borderWidth: 2,
                    tension: 0.1,
                    fill: false,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }});
                
                colorIndex++;
            }});
            
            // Create chart
            analyticsChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: sortedRunIds,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'Model Performance Over Time',
                            font: {{
                                size: 16,
                                weight: 'bold'
                            }}
                        }},
                        legend: {{
                            display: true,
                            position: 'top'
                        }}
                    }},
                    scales: {{
                        x: {{
                            display: true,
                            title: {{
                                display: true,
                                text: 'Benchmark Run (ID)'
                            }}
                        }},
                        y: {{
                            display: true,
                            title: {{
                                display: true,
                                text: 'Average Score'
                            }},
                            min: 0,
                            max: 1
                        }}
                    }}
                }}
            }});
        }}
        
        function displayInsights(insights) {{
            const insightsList = document.getElementById('insightsList');
            
            if (!insights || insights.length === 0) {{
                insightsList.innerHTML = '<div style="color: #718096; font-style: italic;">No insights available. Run more benchmarks to generate analytics.</div>';
                return;
            }}
            
            const insightsHtml = insights.map(insight => 
                `<div style="margin-bottom: 8px; padding: 8px; background: white; border-radius: 4px; border-left: 3px solid #667eea;">
                    <div style="font-size: 13px; line-height: 1.4;">${{insight}}</div>
                </div>`
            ).join('');
            
            insightsList.innerHTML = insightsHtml;
        }}
        
        // Check for existing jobs on page load
        window.addEventListener('load', async () => {{
            try {{
                const response = await fetch('/jobs');
                const jobs = await response.json();
                
                // Find running jobs
                const runningJobs = Object.entries(jobs).filter(([id, job]) => 
                    job.status === 'running'
                );
                
                if (runningJobs.length > 0) {{
                    const [jobId, jobData] = runningJobs[0];
                    currentJobId = jobId;
                    document.getElementById('benchmarkStatus').textContent = '🏃 Resuming benchmark...';
                    document.getElementById('progressBar').style.display = 'block';
                    document.getElementById('runBenchmarkBtn').disabled = true;
                    document.getElementById('runBenchmarkBtn').textContent = '⏳ Running...';
                    startPolling();
                }}
            }} catch (error) {{
                console.log('No existing jobs found');
            }}
        }});
    </script>
</body>
</html>
"""
    return html


# ── API Endpoints ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """
    Interactive benchmark dashboard.
    Displays leaderboard, difficulty breakdown, and error taxonomy charts.
    """
    leaderboard = get_leaderboard_data()
    error_taxonomy = get_error_taxonomy_data()
    return generate_dashboard_html(leaderboard, error_taxonomy)


@app.get("/leaderboard", response_class=JSONResponse)
async def leaderboard_json() -> Dict[str, Any]:
    """
    JSON endpoint: Benchmark leaderboard.
    Returns rankings sorted by average score.
    """
    data = get_leaderboard_data()
    if data:
        return data
    return {
        "message": "No benchmark results yet",
        "instructions": "Run: python run_benchmark.py",
        "rankings": [],
    }


@app.get("/error_taxonomy", response_class=JSONResponse)
async def error_taxonomy_json() -> Dict[str, Any]:
    """
    JSON endpoint: Error taxonomy and classification metrics.
    Returns error rates by category across all evaluated models.
    """
    data = get_error_taxonomy_data()
    if data:
        return data
    return {
        "message": "No error taxonomy data yet",
        "instructions": "Run: python run_benchmark.py",
        "global_error_rates": {},
    }


@app.get("/health", response_class=JSONResponse)
async def health() -> Dict[str, str]:
    """
    Health check endpoint.
    Returns 200 if service is running.
    """
    return {"status": "ok", "service": APP_TITLE}


# ── Benchmark Execution API ─────────────────────────────────────────────────

@app.post("/run-benchmark", response_class=JSONResponse)
async def run_benchmark(background_tasks: BackgroundTasks) -> Dict[str, str]:
    """
    Start a new benchmark execution in the background.
    Returns job ID for tracking progress.
    """
    job_id = str(uuid.uuid4())
    
    # Initialize job
    jobs[job_id] = {
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "total_tasks": 0,
        "completed_tasks": 0,
        "current_model": "",
        "current_task": "",
        "results": None,
        "error": None
    }
    
    # Add background task
    background_tasks.add_task(run_benchmark_background, job_id)
    
    return {"job_id": job_id}


@app.get("/status/{job_id}", response_class=JSONResponse)
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get the current status of a benchmark job.
    Returns progress information and current task.
    """
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(
            status_code=404,
            content={"status": "not_found", "error": "Job not found"}
        )
    
    # Return copy without sensitive data
    response = {
        "status": job["status"],
        "total_tasks": job.get("total_tasks", 0),
        "completed_tasks": job.get("completed_tasks", 0),
        "current_model": job.get("current_model", ""),
        "current_task": job.get("current_task", ""),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "failed_at": job.get("failed_at")
    }
    
    if job["status"] == "failed":
        response["error"] = job.get("error", "Unknown error")
    
    return response


@app.get("/results/{job_id}", response_class=JSONResponse)
async def get_job_results(job_id: str) -> Dict[str, Any]:
    """
    Get the results of a completed benchmark job.
    Returns detailed results for all models and tasks.
    """
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(
            status_code=404,
            content={"status": "not_found", "error": "Job not found"}
        )
    
    if job["status"] != "completed":
        return JSONResponse(
            status_code=400,
            content={"status": "not_completed", "error": "Job not completed yet"}
        )
    
    return {
        "job_id": job_id,
        "status": job["status"],
        "completed_at": job.get("completed_at"),
        "results": job.get("results", [])
    }


@app.get("/jobs", response_class=JSONResponse)
async def list_jobs() -> Dict[str, Any]:
    """
    List all benchmark jobs (for debugging and monitoring).
    """
    return {
        "jobs": {
            job_id: {
                "status": job["status"],
                "created_at": job.get("created_at"),
                "total_tasks": job.get("total_tasks", 0),
                "completed_tasks": job.get("completed_tasks", 0)
            }
            for job_id, job in jobs.items()
        }
    }


@app.delete("/jobs/{job_id}", response_class=JSONResponse)
async def delete_job(job_id: str) -> Dict[str, str]:
    """
    Delete a completed or failed job from memory.
    """
    if job_id not in jobs:
        return JSONResponse(
            status_code=404,
            content={"error": "Job not found"}
        )
    
    job = jobs[job_id]
    if job["status"] == "running":
        return JSONResponse(
            status_code=400,
            content={"error": "Cannot delete running job"}
        )
    
    del jobs[job_id]
    return {"message": "Job deleted successfully"}


# ── Database API Endpoints ───────────────────────────────────────────────────

@app.get("/api/results", response_class=JSONResponse)
async def get_db_results(limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """
    Get benchmark results from database with pagination.
    Returns persistent results across all benchmark runs.
    """
    from database import SessionLocal
    from sqlalchemy import desc
    
    db = SessionLocal()
    try:
        # Query results with pagination
        results = db.query(BenchmarkRun)\
                   .order_by(desc(BenchmarkRun.created_at))\
                   .offset(offset)\
                   .limit(limit)\
                   .all()
        
        # Convert to JSON-serializable format
        results_data = []
        for result in results:
            results_data.append({
                "id": result.id,
                "run_id": result.run_id,
                "model_name": result.model_name,
                "model_id": result.model_id,
                "task_id": result.task_id,
                "task_difficulty": result.task_difficulty,
                "episode_score": result.episode_score,
                "total_reward": result.total_reward,
                "steps_taken": result.steps_taken,
                "solved": result.solved,
                "duration_seconds": result.duration_seconds,
                "created_at": result.created_at.isoformat() if result.created_at else None,
                "error_category": result.error_category,
                "status": result.status
            })
        
        # Get total count
        total_count = db.query(BenchmarkRun).count()
        
        return {
            "results": results_data,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Database query failed: {str(e)}"}
        )
    finally:
        db.close()


@app.get("/api/leaderboard", response_class=JSONResponse)
async def get_persistent_leaderboard() -> Dict[str, Any]:
    """
    Get leaderboard from database with historical data.
    Aggregates results across all benchmark runs.
    """
    from database import SessionLocal
    from sqlalchemy import func, desc, Integer
    
    db = SessionLocal()
    try:
        # Query aggregated results by model
        leaderboard_data = db.query(
            BenchmarkRun.model_name,
            BenchmarkRun.model_id,
            func.avg(BenchmarkRun.episode_score).label("average_score"),
            func.count(BenchmarkRun.id).label("total_tasks"),
            func.sum(func.cast(BenchmarkRun.solved, Integer)).label("tasks_solved"),
            func.avg(BenchmarkRun.duration_seconds).label("avg_duration")
        ).group_by(BenchmarkRun.model_name, BenchmarkRun.model_id)\
         .order_by(desc("average_score"))\
         .all()
        
        # Get difficulty breakdown
        difficulty_data = db.query(
            BenchmarkRun.model_name,
            BenchmarkRun.task_difficulty,
            func.avg(BenchmarkRun.episode_score).label("avg_score")
        ).group_by(BenchmarkRun.model_name, BenchmarkRun.task_difficulty)\
         .all()
        
        # Build difficulty breakdown dict
        difficulty_breakdown = {}
        for model, difficulty, avg_score in difficulty_data:
            if model not in difficulty_breakdown:
                difficulty_breakdown[model] = {}
            difficulty_breakdown[model][difficulty] = float(avg_score)
        
        # Format leaderboard
        rankings = []
        for model_name, model_id, avg_score, total_tasks, tasks_solved, avg_duration in leaderboard_data:
            rankings.append({
                "model_name": model_name,
                "model_id": model_id,
                "average_score": float(avg_score),
                "total_tasks": int(total_tasks),
                "tasks_solved": int(tasks_solved),
                "solve_rate": float(tasks_solved) / float(total_tasks) if total_tasks > 0 else 0.0,
                "avg_duration": float(avg_duration),
                "difficulty_breakdown": difficulty_breakdown.get(model_name, {})
            })
        
        return {
            "rankings": rankings,
            "total_models": len(rankings),
            "generated_at": datetime.now().isoformat(),
            "source": "database"
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Leaderboard query failed: {str(e)}"}
        )
    finally:
        db.close()


@app.get("/api/runs", response_class=JSONResponse)
async def get_benchmark_runs() -> Dict[str, Any]:
    """
    Get list of all benchmark runs with summaries.
    """
    from database import SessionLocal
    from sqlalchemy import desc
    
    db = SessionLocal()
    try:
        runs = db.query(BenchmarkSummary)\
                .order_by(desc(BenchmarkSummary.started_at))\
                .all()
        
        runs_data = []
        for run in runs:
            runs_data.append({
                "run_id": run.run_id,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "total_tasks": run.total_tasks,
                "completed_tasks": run.completed_tasks,
                "average_score": run.average_score,
                "total_duration": run.total_duration
            })
        
        return {
            "runs": runs_data,
            "total_runs": len(runs_data)
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Runs query failed: {str(e)}"}
        )
    finally:
        db.close()


@app.get("/api/run/{run_id}/results", response_class=JSONResponse)
async def get_run_results(run_id: str) -> Dict[str, Any]:
    """
    Get detailed results for a specific benchmark run.
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Get run summary
        summary = db.query(BenchmarkSummary).filter(BenchmarkSummary.run_id == run_id).first()
        if not summary:
            return JSONResponse(
                status_code=404,
                content={"error": "Run not found"}
            )
        
        # Get run results
        results = db.query(BenchmarkRun).filter(BenchmarkRun.run_id == run_id).all()
        
        # Format results
        results_data = []
        for result in results:
            results_data.append({
                "model_name": result.model_name,
                "task_id": result.task_id,
                "task_difficulty": result.task_difficulty,
                "episode_score": result.episode_score,
                "solved": result.solved,
                "duration_seconds": result.duration_seconds,
                "error_category": result.error_category,
                "status": result.status
            })
        
        return {
            "run_id": run_id,
            "summary": {
                "status": summary.status,
                "started_at": summary.started_at.isoformat() if summary.started_at else None,
                "completed_at": summary.completed_at.isoformat() if summary.completed_at else None,
                "total_tasks": summary.total_tasks,
                "completed_tasks": summary.completed_tasks,
                "average_score": summary.average_score,
                "total_duration": summary.total_duration
            },
            "results": results_data,
            "total_results": len(results_data)
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Run results query failed: {str(e)}"}
        )
    finally:
        db.close()


# ── Analytics API Endpoints ───────────────────────────────────────────────────

@app.get("/api/analytics/model-comparison", response_class=JSONResponse)
async def get_model_comparison_analytics() -> Dict[str, Any]:
    """
    Get comprehensive model comparison analytics with time-series data and insights.
    
    Returns:
        - timeseries: Model performance data across runs
        - insights: AI-generated performance insights
        - summary: Analytics metadata
    """
    try:
        from analytics import analytics_engine
        
        # Get model comparison data
        comparison_data = analytics_engine.get_model_comparison_data()
        
        # Generate full insights
        analytics_response = analytics_engine.generate_full_insights(comparison_data)
        
        return analytics_response
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Analytics generation failed: {str(e)}"}
        )


@app.get("/api/analytics/timeseries", response_class=JSONResponse)
async def get_model_timeseries() -> Dict[str, Any]:
    """
    Get raw time-series data for model performance.
    
    Returns:
        Dictionary mapping model names to their performance over time
    """
    try:
        from analytics import analytics_engine
        
        comparison_data = analytics_engine.get_model_comparison_data()
        
        return {
            "timeseries": comparison_data,
            "summary": {
                "total_models": len(comparison_data),
                "total_data_points": sum(len(data) for data in comparison_data.values()),
                "generated_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Time-series data fetch failed: {str(e)}"}
        )


@app.get("/api/analytics/insights", response_class=JSONResponse)
async def get_model_insights() -> Dict[str, Any]:
    """
    Get AI-generated insights for model performance.
    
    Returns:
        List of performance insights and trends
    """
    try:
        from analytics import analytics_engine
        
        comparison_data = analytics_engine.get_model_comparison_data()
        insights_response = analytics_engine.generate_full_insights(comparison_data)
        
        return {
            "insights": insights_response["insights"],
            "summary": insights_response["summary"]
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Insights generation failed: {str(e)}"}
        )


@app.get("/api/analytics/model/{model_name}", response_class=JSONResponse)
async def get_model_analytics(model_name: str) -> Dict[str, Any]:
    """
    Get detailed analytics for a specific model.
    
    Args:
        model_name: Name of the model to analyze
        
    Returns:
        Detailed performance data and insights for the specified model
    """
    try:
        from analytics import analytics_engine
        
        comparison_data = analytics_engine.get_model_comparison_data()
        
        if model_name not in comparison_data:
            return JSONResponse(
                status_code=404,
                content={"error": f"Model '{model_name}' not found in analytics data"}
            )
        
        model_data = comparison_data[model_name]
        model_insights = analytics_engine.generate_model_insights(model_name, model_data)
        
        # Calculate additional metrics
        scores = [dp["score"] for dp in model_data]
        from statistics import mean, variance
        
        return {
            "model_name": model_name,
            "timeseries": model_data,
            "insights": model_insights,
            "metrics": {
                "total_runs": len(model_data),
                "average_score": mean(scores),
                "variance": variance(scores),
                "best_score": max(scores),
                "worst_score": min(scores),
                "latest_score": scores[-1] if scores else None
            },
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Model analytics failed: {str(e)}"}
        )


# ── OpenEnv Core API ───────────────────────────────────────────────────────

@app.post("/reset", response_class=JSONResponse)
async def reset(task_id: Optional[str] = Body(None, embed=True)) -> Dict[str, Any]:
    """Reset the environment for a specific task."""
    try:
        obs = env.reset(task_id=task_id)
        return obs.model_dump()
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})


@app.post("/step", response_class=JSONResponse)
async def step(query: str = Body(..., embed=True)) -> Dict[str, Any]:
    """Execute a SQL action and return the result."""
    try:
        action = SQLAction(query=query)
        obs, reward, done, info = env.step(action)
        return {
            "observation": obs.model_dump(),
            "reward": reward.model_dump(),
            "done": done,
            "info": info
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=400, content={"detail": str(e)})


@app.get("/state", response_class=JSONResponse)
async def get_state() -> Dict[str, Any]:
    """Get the current environment state (including ground truth for debugging)."""
    state = env.state()
    return state.model_dump()


@app.get("/tasks", response_class=JSONResponse)
async def list_tasks() -> Dict[str, Any]:
    """List all available environment tasks."""
    return {
        "tasks": [
            {
                "id": t["id"],
                "difficulty": t["difficulty"],
                "description": t["expected_description"]
            }
            for t in TASKS
        ]
    }


# ── Main Handler ───────────────────────────────────────────────────────────

def main():
    """Main entry point for starting the server."""
    import uvicorn

    print(f"\n{'='*70}")
    print(f"🎯 {APP_TITLE} Dashboard")
    print(f"{'='*70}")
    print(f"📂 Output directory: {OUTPUT_DIR.absolute()}")
    print(f"🔗 Server:          http://localhost:{PORT}")
    print(f"📊 Dashboard:       http://localhost:{PORT}")
    print(f"📋 API:             http://localhost:{PORT}/docs")
    print(f"💾 Leaderboard:     http://localhost:{PORT}/leaderboard")
    print(f"🐛 Error Taxonomy:  http://localhost:{PORT}/error_taxonomy")
    print(f"{'='*70}\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
