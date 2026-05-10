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

    # Build premium table rows with badges, avatars, and score bars
    table_rows = ""
    if has_leaderboard:
        for i, entry in enumerate(rankings, 1):
            model_name = escape_html(entry.get('model_name', 'Unknown'))
            model_id = entry.get('model_id', 'unknown')
            easy = max(0.0, min(1.0, entry.get('easy', 0.0)))
            medium = max(0.0, min(1.0, entry.get('medium', 0.0)))
            hard = max(0.0, min(1.0, entry.get('hard', 0.0)))
            avg = max(0.0, min(1.0, entry.get('average_score', entry.get('average', 0.0))))
            
            # Rank badge class
            if i == 1:
                rank_class = "gold"
                rank_icon = "🥇"
            elif i == 2:
                rank_class = "silver"
                rank_icon = "🥈"
            elif i == 3:
                rank_class = "bronze"
                rank_icon = "🥉"
            else:
                rank_class = "other"
                rank_icon = str(i)
            
            # Score badge classes
            def get_score_class(score):
                if score >= 0.7:
                    return "high"
                elif score >= 0.4:
                    return "medium"
                return "low"
            
            # Model initials for avatar
            initials = ''.join(word[0].upper() for word in model_name.split()[:2] if word)
            if not initials:
                initials = model_id[:2].upper() if model_id else "M"
            
            # Tasks solved info
            tasks_solved_count = sum(1 for tr in entry.get('task_results', []) if tr.get('solved', False))
            total_model_tasks = len(entry.get('task_results', []))
            
            table_rows += f"""
            <tr>
                <td>
                    <div class="rank-badge {rank_class}">{rank_icon}</div>
                </td>
                <td>
                    <div class="model-info">
                        <div class="model-avatar">{initials}</div>
                        <div>
                            <div class="model-name">{model_name}</div>
                            <div class="model-meta">{tasks_solved_count}/{total_model_tasks} tasks solved</div>
                        </div>
                    </div>
                </td>
                <td style="text-align: center;">
                    <span class="score-badge {get_score_class(easy)}">{easy:.2f}</span>
                    <div class="score-bar"><div class="score-bar-fill {get_score_class(easy)}" style="width: {easy*100}%"></div></div>
                </td>
                <td style="text-align: center;">
                    <span class="score-badge {get_score_class(medium)}">{medium:.2f}</span>
                    <div class="score-bar"><div class="score-bar-fill {get_score_class(medium)}" style="width: {medium*100}%"></div></div>
                </td>
                <td style="text-align: center;">
                    <span class="score-badge {get_score_class(hard)}">{hard:.2f}</span>
                    <div class="score-bar"><div class="score-bar-fill {get_score_class(hard)}" style="width: {hard*100}%"></div></div>
                </td>
                <td style="text-align: right;">
                    <span class="score-badge {get_score_class(avg)}">{avg:.3f}</span>
                    <div class="score-bar"><div class="score-bar-fill {get_score_class(avg)}" style="width: {avg*100}%"></div></div>
                </td>
            </tr>"""
    else:
        table_rows = """
            <tr>
                <td colspan="6">
                    <div class="empty-state">
                        <div class="empty-state-title">No Benchmark Data</div>
                        <div class="empty-state-desc">Run a benchmark to see model performance rankings</div>
                    </div>
                </td>
            </tr>"""

    # Build premium chart initialization scripts with dark theme
    chart_colors = {
        'primary': 'rgba(139, 92, 246, 1)',
        'primary_alpha': 'rgba(139, 92, 246, 0.7)',
        'secondary': 'rgba(236, 72, 153, 1)',
        'secondary_alpha': 'rgba(236, 72, 153, 0.7)',
        'accent': 'rgba(6, 182, 212, 1)',
        'accent_alpha': 'rgba(6, 182, 212, 0.7)',
        'success': 'rgba(16, 185, 129, 0.7)',
        'warning': 'rgba(245, 158, 11, 0.7)',
        'error': 'rgba(239, 68, 68, 0.7)',
        'grid': 'rgba(255, 255, 255, 0.05)',
        'text': '#a1a1aa'
    }
    
    model_chart_init = ""
    if has_leaderboard:
        model_chart_init = f"""
        const modelCtx = document.getElementById('modelChart')?.getContext('2d');
        if (modelCtx) {{
            // Create gradient
            const gradient = modelCtx.createLinearGradient(0, 0, 0, 400);
            gradient.addColorStop(0, 'rgba(139, 92, 246, 0.8)');
            gradient.addColorStop(1, 'rgba(236, 72, 153, 0.4)');
            
            new Chart(modelCtx, {{
                type: 'bar',
                data: {{
                    labels: {model_names},
                    datasets: [{{
                        label: 'Average Score',
                        data: {model_scores},
                        backgroundColor: gradient,
                        borderColor: 'rgba(139, 92, 246, 0.8)',
                        borderWidth: 1,
                        borderRadius: 8,
                        borderSkipped: false,
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
                            grid: {{ color: '{chart_colors['grid']}' }},
                            ticks: {{ 
                                color: '{chart_colors['text']}',
                                callback: (val) => val.toFixed(2),
                                font: {{ family: 'JetBrains Mono' }}
                            }}
                        }},
                        y: {{
                            grid: {{ display: false }},
                            ticks: {{ 
                                color: '{chart_colors['text']}',
                                font: {{ family: 'Inter', size: 12 }}
                            }}
                        }}
                    }},
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            backgroundColor: 'rgba(18, 18, 26, 0.95)',
                            titleColor: '#fafafa',
                            bodyColor: '#a1a1aa',
                            borderColor: 'rgba(139, 92, 246, 0.3)',
                            borderWidth: 1,
                            padding: 12,
                            callbacks: {{ label: (ctx) => 'Score: ' + ctx.raw.toFixed(3) }}
                        }}
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
                            'rgba(16, 185, 129, 0.8)',
                            'rgba(245, 158, 11, 0.8)',
                            'rgba(239, 68, 68, 0.8)'
                        ],
                        borderColor: [
                            'rgba(16, 185, 129, 1)',
                            'rgba(245, 158, 11, 1)',
                            'rgba(239, 68, 68, 1)'
                        ],
                        borderWidth: 2,
                        hoverOffset: 8
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '65%',
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{ 
                                padding: 20, 
                                font: {{ size: 12, family: 'Inter', color: '{chart_colors['text']}' }},
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: 'rgba(18, 18, 26, 0.95)',
                            titleColor: '#fafafa',
                            bodyColor: '#a1a1aa',
                            borderColor: 'rgba(255, 255, 255, 0.1)',
                            borderWidth: 1,
                            padding: 12,
                            callbacks: {{ label: (ctx) => ctx.label + ': ' + ctx.raw.toFixed(2) }}
                        }}
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
                            'rgba(239, 68, 68, 0.8)',
                            'rgba(245, 158, 11, 0.8)',
                            'rgba(251, 191, 36, 0.8)',
                            'rgba(16, 185, 129, 0.8)',
                            'rgba(59, 130, 246, 0.8)',
                            'rgba(139, 92, 246, 0.8)',
                        ],
                        borderColor: [
                            'rgba(239, 68, 68, 1)',
                            'rgba(245, 158, 11, 1)',
                            'rgba(251, 191, 36, 1)',
                            'rgba(16, 185, 129, 1)',
                            'rgba(59, 130, 246, 1)',
                            'rgba(139, 92, 246, 1)',
                        ],
                        borderWidth: 2,
                        hoverOffset: 4
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'right',
                            labels: {{ 
                                padding: 15, 
                                font: {{ size: 11, family: 'Inter', color: '{chart_colors['text']}' }},
                                usePointStyle: true,
                                boxWidth: 8
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: 'rgba(18, 18, 26, 0.95)',
                            titleColor: '#fafafa',
                            bodyColor: '#a1a1aa',
                            borderColor: 'rgba(255, 255, 255, 0.1)',
                            borderWidth: 1,
                            padding: 12,
                            callbacks: {{ label: (ctx) => ctx.label + ': ' + ctx.parsed.toFixed(1) + '%' }}
                        }}
                    }}
                }}
            }});
        }}
        """

    # Calculate KPI metrics for premium cards
    avg_score = sum(max(0.0, min(1.0, r.get('average_score', r.get('average', 0.0)))) for r in rankings) / len(rankings) if rankings else 0.0
    tasks_solved = sum(sum(1 for tr in r.get('task_results', []) if tr.get('solved', False)) for r in (leaderboard.get('models', []) if leaderboard else []))
    total_tasks = len(rankings) * 6 if rankings else 0
    success_rate = (tasks_solved / total_tasks * 100) if total_tasks > 0 else 0.0
    hard_accuracy = sum(max(0.0, min(1.0, r.get('hard', 0.0))) for r in rankings) / len(rankings) if rankings else 0.0
    
    # Assemble PREMIUM HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{APP_TITLE} · AI Research Platform</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: rgba(18, 18, 26, 0.8);
            --bg-glass: rgba(255, 255, 255, 0.03);
            --border-glass: rgba(255, 255, 255, 0.08);
            --accent-primary: #8b5cf6;
            --accent-secondary: #ec4899;
            --accent-gradient: linear-gradient(135deg, #8b5cf6 0%, #ec4899 50%, #06b6d4 100%);
            --accent-glow: rgba(139, 92, 246, 0.4);
            --text-primary: #fafafa;
            --text-secondary: #a1a1aa;
            --text-muted: #71717a;
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            --info: #3b82f6;
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 24px;
            --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
            --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.5);
            --shadow-glow: 0 0 40px rgba(139, 92, 246, 0.15);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            min-height: 100vh;
            color: var(--text-primary);
            line-height: 1.6;
            overflow-x: hidden;
        }}

        /* Animated Background */
        .bg-mesh {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
        }}

        .bg-mesh::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: 
                radial-gradient(ellipse at 20% 20%, rgba(139, 92, 246, 0.15) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(236, 72, 153, 0.1) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(6, 182, 212, 0.05) 0%, transparent 70%);
            animation: meshMove 20s ease-in-out infinite;
        }}

        @keyframes meshMove {{
            0%, 100% {{ transform: translate(0, 0) rotate(0deg); }}
            33% {{ transform: translate(2%, 2%) rotate(120deg); }}
            66% {{ transform: translate(-1%, 1%) rotate(240deg); }}
        }}

        /* Floating Particles */
        .particles {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            pointer-events: none;
        }}

        .particle {{
            position: absolute;
            width: 2px;
            height: 2px;
            background: rgba(139, 92, 246, 0.3);
            border-radius: 50%;
            animation: float 15s infinite;
        }}

        @keyframes float {{
            0%, 100% {{ transform: translateY(0) translateX(0); opacity: 0; }}
            10% {{ opacity: 1; }}
            90% {{ opacity: 1; }}
            100% {{ transform: translateY(-100vh) translateX(50px); opacity: 0; }}
        }}

        /* Layout */
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px;
        }}

        /* Hero Section */
        .hero {{
            position: relative;
            background: var(--bg-glass);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border-glass);
            border-radius: var(--radius-xl);
            padding: 48px;
            margin-bottom: 32px;
            overflow: hidden;
        }}

        .hero::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(139, 92, 246, 0.5), rgba(236, 72, 153, 0.5), transparent);
        }}

        .hero-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(236, 72, 153, 0.2));
            border: 1px solid rgba(139, 92, 246, 0.3);
            border-radius: 100px;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 24px;
        }}

        .hero-badge::before {{
            content: '';
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s ease-in-out infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.6; transform: scale(1.2); }}
        }}

        .hero h1 {{
            font-size: 3rem;
            font-weight: 800;
            background: linear-gradient(135deg, #fafafa 0%, #a78bfa 50%, #ec4899 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 12px;
            letter-spacing: -0.02em;
        }}

        .hero-subtitle {{
            color: var(--text-secondary);
            font-size: 1.125rem;
            max-width: 600px;
            margin-bottom: 32px;
        }}

        .hero-meta {{
            display: flex;
            align-items: center;
            gap: 24px;
            flex-wrap: wrap;
        }}

        .hero-meta-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            color: var(--text-muted);
            font-size: 14px;
        }}

        .hero-meta-item svg {{
            width: 16px;
            height: 16px;
            opacity: 0.6;
        }}

        .status-live {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: var(--success);
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .status-live::before {{
            content: '';
            width: 6px;
            height: 6px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s ease-in-out infinite;
        }}

        /* Premium CTA Button */
        .cta-container {{
            margin-top: 32px;
            display: flex;
            align-items: center;
            gap: 24px;
            flex-wrap: wrap;
        }}

        .btn-premium {{
            position: relative;
            display: inline-flex;
            align-items: center;
            gap: 12px;
            background: var(--accent-gradient);
            border: none;
            border-radius: var(--radius-md);
            padding: 16px 32px;
            color: white;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            overflow: hidden;
            transition: all 0.3s ease;
            box-shadow: 0 4px 24px rgba(139, 92, 246, 0.4);
        }}

        .btn-premium::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
            transition: left 0.5s ease;
        }}

        .btn-premium:hover::before {{
            left: 100%;
        }}

        .btn-premium:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 32px rgba(139, 92, 246, 0.5);
        }}

        .btn-premium:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }}

        .btn-icon {{
            width: 20px;
            height: 20px;
        }}

        .btn-premium.loading .btn-icon {{
            animation: spin 1s linear infinite;
        }}

        @keyframes spin {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}

        /* Progress Bar Premium */
        .progress-container {{
            flex: 1;
            min-width: 300px;
            max-width: 500px;
        }}

        .progress-bar-bg {{
            height: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 100px;
            overflow: hidden;
            position: relative;
        }}

        .progress-bar-fill {{
            height: 100%;
            background: var(--accent-gradient);
            border-radius: 100px;
            transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }}

        .progress-bar-fill::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
            animation: shimmer 2s infinite;
        }}

        @keyframes shimmer {{
            0% {{ transform: translateX(-100%); }}
            100% {{ transform: translateX(100%); }}
        }}

        .progress-text {{
            color: var(--text-secondary);
            font-size: 13px;
            margin-top: 8px;
            font-family: 'JetBrains Mono', monospace;
        }}

        /* KPI Cards */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }}

        .kpi-card {{
            position: relative;
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-glass);
            border-radius: var(--radius-lg);
            padding: 24px;
            transition: all 0.3s ease;
            overflow: hidden;
        }}

        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--accent-gradient);
            opacity: 0;
            transition: opacity 0.3s ease;
        }}

        .kpi-card:hover {{
            transform: translateY(-4px);
            border-color: rgba(139, 92, 246, 0.3);
            box-shadow: var(--shadow-glow);
        }}

        .kpi-card:hover::before {{
            opacity: 1;
        }}

        .kpi-icon {{
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(139, 92, 246, 0.1);
            border-radius: var(--radius-sm);
            margin-bottom: 16px;
            color: var(--accent-primary);
        }}

        .kpi-label {{
            color: var(--text-muted);
            font-size: 13px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}

        .kpi-value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
        }}

        .kpi-change {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-size: 12px;
            margin-top: 8px;
            font-weight: 500;
        }}

        .kpi-change.positive {{
            color: var(--success);
        }}

        .kpi-change.negative {{
            color: var(--error);
        }}

        /* Section Headers */
        .section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
        }}

        .section-title {{
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .section-title svg {{
            width: 20px;
            height: 20px;
            color: var(--accent-primary);
        }}

        /* Main Grid */
        .main-grid {{
            display: grid;
            grid-template-columns: 1fr 380px;
            gap: 32px;
            margin-bottom: 32px;
        }}

        @media (max-width: 1200px) {{
            .main-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* Cards */
        .card {{
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-glass);
            border-radius: var(--radius-lg);
            padding: 24px;
            transition: all 0.3s ease;
        }}

        .card:hover {{
            border-color: rgba(139, 92, 246, 0.2);
        }}

        .card-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-glass);
        }}

        .card-title {{
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
        }}

        /* Leaderboard Premium */
        .leaderboard-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
        }}

        .leaderboard-table th {{
            text-align: left;
            padding: 12px 16px;
            color: var(--text-muted);
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border-glass);
        }}

        .leaderboard-table td {{
            padding: 16px;
            border-bottom: 1px solid var(--border-glass);
            transition: background 0.2s ease;
        }}

        .leaderboard-table tr:hover td {{
            background: rgba(139, 92, 246, 0.05);
        }}

        .rank-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            font-weight: 700;
            font-size: 14px;
        }}

        .rank-badge.gold {{
            background: linear-gradient(135deg, #fbbf24, #f59e0b);
            color: #000;
        }}

        .rank-badge.silver {{
            background: linear-gradient(135deg, #e5e7eb, #9ca3af);
            color: #000;
        }}

        .rank-badge.bronze {{
            background: linear-gradient(135deg, #fdba74, #ea580c);
            color: #000;
        }}

        .rank-badge.other {{
            background: rgba(255, 255, 255, 0.1);
            color: var(--text-secondary);
        }}

        .model-info {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .model-avatar {{
            width: 36px;
            height: 36px;
            border-radius: var(--radius-sm);
            background: var(--accent-gradient);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 14px;
            color: white;
        }}

        .model-name {{
            font-weight: 600;
            color: var(--text-primary);
        }}

        .model-meta {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 2px;
        }}

        .score-badge {{
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            border-radius: 100px;
            font-weight: 600;
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
        }}

        .score-badge.high {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .score-badge.medium {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--warning);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .score-badge.low {{
            background: rgba(239, 68, 68, 0.15);
            color: var(--error);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}

        /* Score Bar */
        .score-bar {{
            width: 100%;
            height: 4px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 100px;
            overflow: hidden;
            margin-top: 8px;
        }}

        .score-bar-fill {{
            height: 100%;
            border-radius: 100px;
            transition: width 0.6s ease;
        }}

        .score-bar-fill.high {{
            background: var(--success);
        }}

        .score-bar-fill.medium {{
            background: var(--warning);
        }}

        .score-bar-fill.low {{
            background: var(--error);
        }}

        /* Charts */
        .chart-container {{
            position: relative;
            height: 280px;
            margin-top: 16px;
        }}

        /* Insights Panel */
        .insights-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .insight-item {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 16px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: var(--radius-md);
            border: 1px solid var(--border-glass);
            transition: all 0.2s ease;
        }}

        .insight-item:hover {{
            background: rgba(255, 255, 255, 0.04);
            border-color: rgba(139, 92, 246, 0.2);
        }}

        .insight-icon {{
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            flex-shrink: 0;
        }}

        .insight-icon.success {{
            background: rgba(16, 185, 129, 0.2);
            color: var(--success);
        }}

        .insight-icon.warning {{
            background: rgba(245, 158, 11, 0.2);
            color: var(--warning);
        }}

        .insight-icon.error {{
            background: rgba(239, 68, 68, 0.2);
            color: var(--error);
        }}

        .insight-content {{
            flex: 1;
        }}

        .insight-title {{
            font-weight: 600;
            font-size: 14px;
            color: var(--text-primary);
            margin-bottom: 4px;
        }}

        .insight-desc {{
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.5;
        }}

        /* Skeleton Loading */
        .skeleton {{
            background: linear-gradient(90deg, rgba(255, 255, 255, 0.05) 25%, rgba(255, 255, 255, 0.1) 50%, rgba(255, 255, 255, 0.05) 75%);
            background-size: 200% 100%;
            animation: skeleton-loading 1.5s infinite;
            border-radius: var(--radius-sm);
        }}

        @keyframes skeleton-loading {{
            0% {{ background-position: 200% 0; }}
            100% {{ background-position: -200% 0; }}
        }}

        .skeleton-text {{
            height: 12px;
            margin-bottom: 8px;
        }}

        .skeleton-text:last-child {{
            margin-bottom: 0;
        }}

        .skeleton-title {{
            height: 20px;
            width: 60%;
            margin-bottom: 16px;
        }}

        /* Toast Notifications */
        .toast-container {{
            position: fixed;
            top: 24px;
            right: 24px;
            z-index: 1000;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .toast {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 16px 20px;
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-glass);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            animation: toastIn 0.3s ease;
            max-width: 400px;
        }}

        @keyframes toastIn {{
            from {{ transform: translateX(100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}

        .toast-icon {{
            width: 20px;
            height: 20px;
        }}

        .toast-content {{
            flex: 1;
        }}

        .toast-title {{
            font-weight: 600;
            font-size: 14px;
            color: var(--text-primary);
        }}

        .toast-message {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 2px;
        }}

        /* Empty States */
        .empty-state {{
            text-align: center;
            padding: 48px 24px;
            color: var(--text-muted);
        }}

        .empty-state-icon {{
            width: 64px;
            height: 64px;
            margin: 0 auto 16px;
            opacity: 0.3;
        }}

        .empty-state-title {{
            font-size: 16px;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }}

        .empty-state-desc {{
            font-size: 14px;
            color: var(--text-muted);
        }}

        /* Footer */
        footer {{
            text-align: center;
            padding: 32px 24px;
            border-top: 1px solid var(--border-glass);
            margin-top: 48px;
        }}

        .footer-links {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 24px;
            flex-wrap: wrap;
        }}

        .footer-link {{
            color: var(--text-muted);
            text-decoration: none;
            font-size: 13px;
            font-weight: 500;
            transition: color 0.2s ease;
        }}

        .footer-link:hover {{
            color: var(--accent-primary);
        }}

        .footer-divider {{
            color: var(--border-glass);
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .hero {{
                padding: 32px 24px;
            }}

            .hero h1 {{
                font-size: 2rem;
            }}

            .hero-meta {{
                flex-direction: column;
                align-items: flex-start;
                gap: 12px;
            }}

            .cta-container {{
                flex-direction: column;
                align-items: stretch;
            }}

            .progress-container {{
                max-width: none;
            }}

            .kpi-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .leaderboard-table {{
                font-size: 13px;
            }}

            .leaderboard-table th,
            .leaderboard-table td {{
                padding: 12px 8px;
            }}

            .model-avatar {{
                display: none;
            }}
        }}

        @media (max-width: 480px) {{
            .kpi-grid {{
                grid-template-columns: 1fr;
            }}

            .container {{
                padding: 16px;
            }}
        }}
    </style>
</head>
<body>
    <!-- Animated Background -->
    <div class="bg-mesh"></div>
    <div class="particles" id="particles"></div>

    <div class="container">
        <!-- Premium Hero Section -->
        <div class="hero">
            <div class="hero-badge">
                <span>AI Research Platform</span>
            </div>
            <h1>{APP_TITLE}</h1>
            <p class="hero-subtitle">Professional benchmark environment for evaluating LLM capability on SQL debugging, correction, and optimization tasks</p>
            <div class="hero-meta">
                <div class="hero-meta-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    <span>Last updated: {format_timestamp(timestamp)}</span>
                </div>
                <div class="status-live">● Live System</div>
            </div>

            <!-- Premium CTA -->
            <div class="cta-container">
                <button id="runBenchmarkBtn" class="btn-premium" onclick="runBenchmark()">
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                    <span>Run Benchmark</span>
                </button>
                
                <div class="progress-container" id="progressContainer" style="display: none;">
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" id="progressFill" style="width: 0%;"></div>
                    </div>
                    <div class="progress-text" id="progressText">Initializing...</div>
                </div>
            </div>
        </div>

        <!-- KPI Cards -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                </div>
                <div class="kpi-label">Average Score</div>
                <div class="kpi-value">{avg_score:.3f}</div>
                <div class="kpi-change {'positive' if avg_score > 0.5 else 'negative'}">
                    {'↑' if avg_score > 0.5 else '↓'} {(avg_score * 100):.1f}%
                </div>
            </div>

            <div class="kpi-card">
                <div class="kpi-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                </div>
                <div class="kpi-label">Tasks Solved</div>
                <div class="kpi-value">{tasks_solved}/{total_tasks}</div>
                <div class="kpi-change {'positive' if success_rate > 50 else 'negative'}">
                    {'↑' if success_rate > 50 else '↓'} {success_rate:.1f}%
                </div>
            </div>

            <div class="kpi-card">
                <div class="kpi-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                </div>
                <div class="kpi-label">Hard Task Accuracy</div>
                <div class="kpi-value">{hard_accuracy:.2f}</div>
                <div class="kpi-change {'positive' if hard_accuracy > 0.3 else 'negative'}">
                    {'↑' if hard_accuracy > 0.3 else '↓'} {(hard_accuracy * 100):.1f}%
                </div>
            </div>

            <div class="kpi-card">
                <div class="kpi-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                </div>
                <div class="kpi-label">Models Active</div>
                <div class="kpi-value">{len(rankings)}</div>
                <div class="kpi-change positive">● Operational</div>
            </div>

            <div class="kpi-card">
                <div class="kpi-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                </div>
                <div class="kpi-label">Runtime</div>
                <div class="kpi-value">{datetime.now().strftime("%H:%M")}</div>
                <div class="kpi-change positive">UTC</div>
            </div>
        </div>

        <!-- Main Grid -->
        <div class="main-grid">
            <!-- Left Column -->
            <div class="left-column">
                <!-- Leaderboard -->
                <div class="card">
                    <div class="card-header">
                        <div class="section-title">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                            Leaderboard
                        </div>
                    </div>
                    <table class="leaderboard-table">
                        <thead>
                            <tr>
                                <th style="width: 60px;">Rank</th>
                                <th>Model</th>
                                <th style="text-align: center;">Easy</th>
                                <th style="text-align: center;">Medium</th>
                                <th style="text-align: center;">Hard</th>
                                <th style="text-align: right;">Average</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>

                <!-- Charts Grid -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 24px;">
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Model Performance</div>
                        </div>
                        {'<div class="chart-container"><canvas id="modelChart"></canvas></div>' if has_leaderboard else '<div class="empty-state"><div class="empty-state-title">No Data</div><div class="empty-state-desc">Run benchmark to see performance metrics</div></div>'}
                    </div>

                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Difficulty Analysis</div>
                        </div>
                        {'<div class="chart-container"><canvas id="difficultyChart"></canvas></div>' if has_leaderboard else '<div class="empty-state"><div class="empty-state-title">No Data</div><div class="empty-state-desc">Run benchmark to see difficulty breakdown</div></div>'}
                    </div>
                </div>
            </div>

            <!-- Right Column -->
            <div class="right-column">
                <!-- AI Insights -->
                <div class="card" style="margin-bottom: 24px;">
                    <div class="card-header">
                        <div class="section-title">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                            AI Insights
                        </div>
                    </div>
                    <div class="insights-list" id="insightsList">
                        <div class="insight-item">
                            <div class="insight-icon success">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                            </div>
                            <div class="insight-content">
                                <div class="insight-title">Schema Understanding</div>
                                <div class="insight-desc">Models show strong performance on table/column reference tasks</div>
                            </div>
                        </div>
                        <div class="insight-item">
                            <div class="insight-icon warning">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                            </div>
                            <div class="insight-content">
                                <div class="insight-title">Aggregation Challenges</div>
                                <div class="insight-desc">Complex GROUP BY and aggregate functions need improvement</div>
                            </div>
                        </div>
                        <div class="insight-item">
                            <div class="insight-icon error">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                            </div>
                            <div class="insight-content">
                                <div class="insight-title">Complex Query Reasoning</div>
                                <div class="insight-desc">Multi-constraint queries show instability in reasoning chains</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Error Taxonomy -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Error Distribution</div>
                    </div>
                    {'<div class="chart-container" style="height: 200px;"><canvas id="errorChart"></canvas></div>' if has_errors else '<div class="empty-state"><div class="empty-state-title">No Errors</div><div class="empty-state-desc">Perfect execution - no errors to analyze</div></div>'}
                </div>
            </div>
        </div>

        <!-- Toast Container -->
        <div class="toast-container" id="toastContainer"></div>

        <!-- Footer -->
        <footer>
            <div class="footer-links">
                <a href="/leaderboard" class="footer-link">API Leaderboard</a>
                <span class="footer-divider">|</span>
                <a href="/error_taxonomy" class="footer-link">Error Taxonomy</a>
                <span class="footer-divider">|</span>
                <a href="/docs" class="footer-link">Documentation</a>
                <span class="footer-divider">|</span>
                <a href="https://github.com/nareshchandu17/SQLBench-OpenEnv" class="footer-link">GitHub</a>
            </div>
        </footer>
    </div>

    <script>
        {model_chart_init}
        {difficulty_chart_init}
        {error_chart_init}
        
        // Premium JavaScript Features
        
        // Toast Notification System
        function showToast(title, message, type = 'info') {{
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = 'toast';
            
            const icons = {{
                success: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
                error: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
                warning: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
                info: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
            }};
            
            toast.innerHTML = `
                ${{icons[type]}}
                <div class="toast-content">
                    <div class="toast-title">${{title}}</div>
                    <div class="toast-message">${{message}}</div>
                </div>
            `;
            
            container.appendChild(toast);
            
            // Animate in
            requestAnimationFrame(() => {{
                toast.style.animation = 'toastIn 0.3s ease';
            }});
            
            // Remove after 5 seconds
            setTimeout(() => {{
                toast.style.animation = 'toastOut 0.3s ease';
                setTimeout(() => toast.remove(), 300);
            }}, 5000);
        }}
        
        // Particle Animation System
        function initParticles() {{
            const container = document.getElementById('particles');
            const particleCount = 30;
            
            for (let i = 0; i < particleCount; i++) {{
                const particle = document.createElement('div');
                particle.className = 'particle';
                particle.style.left = Math.random() * 100 + '%';
                particle.style.animationDuration = (15 + Math.random() * 20) + 's';
                particle.style.animationDelay = Math.random() * 15 + 's';
                particle.style.opacity = Math.random() * 0.5 + 0.2;
                container.appendChild(particle);
            }}
        }}
        
        // Initialize particles on load
        initParticles();
        
        // Benchmark execution
        let currentJobId = null;
        let pollingInterval = null;
        
        async function runBenchmark() {{
            const btn = document.getElementById('runBenchmarkBtn');
            const progressContainer = document.getElementById('progressContainer');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            
            // Premium loading state
            btn.disabled = true;
            btn.classList.add('loading');
            btn.querySelector('span').textContent = 'Initializing...';
            
            // Show progress container with animation
            progressContainer.style.display = 'block';
            progressFill.style.width = '0%';
            progressText.textContent = 'Preparing benchmark environment...';
            
            showToast('Benchmark Started', 'Initializing SQL evaluation environment', 'info');
            
            try {{
                const response = await fetch('/run-benchmark', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }}
                }});
                
                if (!response.ok) {{
                    throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                }}
                
                const data = await response.json();
                currentJobId = data.job_id;
                
                showToast('Benchmark Running', `Job ID: ${{currentJobId.substring(0, 8)}}`, 'info');
                startPolling();
                
            }} catch (error) {{
                console.error('Failed to start benchmark:', error);
                showToast('Error', `Failed to start benchmark: ${{error.message}}`, 'error');
                resetButton();
            }}
        }}
        
        function startPolling() {{
            if (pollingInterval) clearInterval(pollingInterval);
            
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
                    showToast('Connection Lost', 'Lost connection to benchmark server', 'error');
                    resetButton();
                }}
            }}, 2000);
        }}
        
        function updateProgress(data) {{
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            const btn = document.getElementById('runBenchmarkBtn');
            
            if (data.status === 'running') {{
                const progress = data.total_tasks > 0 ? 
                    (data.completed_tasks / data.total_tasks * 100) : 0;
                
                progressFill.style.width = `${{progress}}%`;
                progressText.textContent = 
                    `${{data.completed_tasks}}/${{data.total_tasks}} tasks · ${{data.current_model || 'Loading...'}} · ${{data.current_task || 'Initializing'}}`;
                
                btn.querySelector('span').textContent = `Running ${{data.completed_tasks}}/${{data.total_tasks}}`;
            }}
        }}
        
        function handleCompletion(data) {{
            const btn = document.getElementById('runBenchmarkBtn');
            const progressText = document.getElementById('progressText');
            
            if (data.status === 'completed') {{
                showToast('Benchmark Complete', 'All evaluation tasks finished successfully', 'success');
                progressText.textContent = '✓ Benchmark completed successfully';
                btn.querySelector('span').textContent = 'Completed';
                
                // Animate refresh
                setTimeout(() => {{
                    document.body.style.opacity = '0';
                    setTimeout(() => {{
                        window.location.reload();
                    }}, 300);
                }}, 2000);
                
            }} else if (data.status === 'failed') {{
                showToast('Benchmark Failed', data.error || 'An unknown error occurred', 'error');
                progressText.textContent = '✗ Benchmark failed - see error details';
                btn.querySelector('span').textContent = 'Failed';
                resetButton();
            }}
        }}
        
        function resetButton() {{
            const btn = document.getElementById('runBenchmarkBtn');
            btn.disabled = false;
            btn.classList.remove('loading');
            btn.querySelector('span').textContent = 'Run Benchmark';
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
            
            // Create chart with premium dark theme
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
                            display: false
                        }},
                        legend: {{
                            display: true,
                            position: 'top',
                            labels: {{
                                color: '#a1a1aa',
                                font: {{ family: 'Inter', size: 12 }},
                                usePointStyle: true,
                                padding: 20
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: 'rgba(18, 18, 26, 0.95)',
                            titleColor: '#fafafa',
                            bodyColor: '#a1a1aa',
                            borderColor: 'rgba(255, 255, 255, 0.1)',
                            borderWidth: 1,
                            padding: 12,
                            callbacks: {{
                                label: (ctx) => `${{ctx.dataset.label}}: ${{ctx.parsed.y.toFixed(3)}}`
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            display: true,
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{
                                color: '#71717a',
                                font: {{ family: 'JetBrains Mono', size: 11 }}
                            }},
                            title: {{
                                display: false
                            }}
                        }},
                        y: {{
                            display: true,
                            min: 0,
                            max: 1,
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{
                                color: '#71717a',
                                font: {{ family: 'JetBrains Mono', size: 11 }},
                                callback: (val) => val.toFixed(1)
                            }}
                        }}
                    }},
                    interaction: {{
                        intersect: false,
                        mode: 'index'
                    }}
                }}
            }});
        }}
        
        function displayInsights(insights) {{
            const insightsList = document.getElementById('insightsList');
            
            if (!insights || insights.length === 0) {{
                insightsList.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-title">No Insights Available</div>
                        <div class="empty-state-desc">Run more benchmarks to generate AI-powered analytics</div>
                    </div>`;
                return;
            }}
            
            // Map insights to appropriate severity levels
            const severityMap = {{
                'strong': 'success',
                'good': 'success',
                'excellent': 'success',
                'weak': 'error',
                'poor': 'error',
                'needs': 'warning',
                'improvement': 'warning',
                'challenged': 'warning'
            }};
            
            const insightsHtml = insights.map((insight, index) => {{
                const lowerInsight = insight.toLowerCase();
                let severity = 'info';
                
                // Determine severity based on keywords
                for (const [keyword, level] of Object.entries(severityMap)) {{
                    if (lowerInsight.includes(keyword)) {{
                        severity = level;
                        break;
                    }}
                }}
                
                const icons = {{
                    success: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>',
                    warning: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
                    error: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
                    info: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
                }};
                
                // Extract a title and description from the insight
                const sentences = insight.split('. ');
                const title = sentences[0].replace(/^(Strong|Weak|Poor|Good|Excellent)\s+/i, '').replace(/:/g, '');
                const description = sentences.slice(1).join('. ') || insight;
                
                return `
                    <div class="insight-item" style="animation: fadeIn 0.3s ease ${{index * 0.1}}s both;">
                        <div class="insight-icon ${{severity}}">
                            ${{icons[severity]}}
                        </div>
                        <div class="insight-content">
                            <div class="insight-title">${{title}}</div>
                            <div class="insight-desc">${{description}}</div>
                        </div>
                    </div>
                `;
            }}).join('');
            
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
