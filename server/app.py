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
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from env.environment import SQLQueryEnv
from env.models import SQLAction
from env.tasks import TASKS, TASK_INDEX

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
