"""
Generate seed/demo benchmark data for visualizing rich analytics.
Creates 8-10 historical benchmark runs with realistic performance trends.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from database import SessionLocal
from benchmark.models import BenchmarkResult, ModelPerformance


def generate_seed_data():
    """Generate 10 historical benchmark runs with realistic data."""
    db = SessionLocal()
    
    try:
        # Models to simulate
        models = [
            "gpt-4o",
            "claude-3-sonnet", 
            "llama-3.1-70b",
            "gemini-pro",
            "mistral-large",
            "command-r-plus"
        ]
        
        # Base scores with some models performing better than others
        base_scores = {
            "gpt-4o": 0.85,
            "claude-3-sonnet": 0.82,
            "llama-3.1-70b": 0.78,
            "gemini-pro": 0.75,
            "mistral-large": 0.73,
            "command-r-plus": 0.70
        }
        
        # Tasks
        tasks = [
            "fix_syntax_simple",
            "fix_table_name",
            "fix_join_logic",
            "fix_aggregate_logic",
            "multi_constraint_query",
            "ecommerce_supply_chain"
        ]
        
        print("🌱 Generating seed benchmark data...")
        
        # Generate 10 runs over the last 30 days
        for run_idx in range(10):
            run_date = datetime.now() - timedelta(days=30 - run_idx * 3)
            run_id = f"seed_run_{run_idx:03d}_{run_date.strftime('%Y%m%d')}"
            
            # Each model gets slightly different scores with improvement trend
            for model in models:
                base = base_scores[model]
                # Add slight improvement over time + random variance
                improvement = run_idx * 0.01  # Small improvement per run
                variance = random.uniform(-0.05, 0.05)
                
                easy_score = min(1.0, max(0.0, base + 0.1 + improvement + variance))
                medium_score = min(1.0, max(0.0, base + improvement + variance))
                hard_score = min(1.0, max(0.0, base - 0.15 + improvement + variance))
                avg_score = (easy_score + medium_score + hard_score) / 3
                
                # Create model performance entry
                performance = ModelPerformance(
                    run_id=run_id,
                    model_name=model,
                    timestamp=run_date,
                    easy_score=easy_score,
                    medium_score=medium_score,
                    hard_score=hard_score,
                    average_score=avg_score,
                    tasks_solved=random.randint(3, 6),
                    total_tasks=6,
                    avg_execution_time=random.uniform(2.0, 8.0),
                    error_count=random.randint(0, 3),
                    error_breakdown=json.dumps({
                        "syntax_errors": random.randint(0, 2),
                        "logic_errors": random.randint(0, 2),
                        "timeout_errors": random.randint(0, 1)
                    })
                )
                db.add(performance)
                
                # Create detailed task results for each task
                for task_idx, task in enumerate(tasks):
                    # Determine difficulty
                    if task_idx < 2:
                        difficulty = "easy"
                        base_task_score = easy_score
                    elif task_idx < 4:
                        difficulty = "medium"
                        base_task_score = medium_score
                    else:
                        difficulty = "hard"
                        base_task_score = hard_score
                    
                    # Task success varies by difficulty
                    task_variance = random.uniform(-0.2, 0.2)
                    task_score = min(1.0, max(0.0, base_task_score + task_variance))
                    solved = task_score > 0.6
                    
                    result = BenchmarkResult(
                        run_id=run_id,
                        model_name=model,
                        task_id=task,
                        task_difficulty=difficulty,
                        solved=solved,
                        score=task_score,
                        execution_time=random.uniform(1.5, 10.0),
                        token_usage=random.randint(500, 3000),
                        error_type=None if solved else random.choice(["syntax", "logic", "timeout"]),
                        error_message=None if solved else "Sample error for demo",
                        timestamp=run_date
                    )
                    db.add(result)
            
            print(f"  ✓ Generated run {run_idx + 1}/10: {run_id}")
        
        db.commit()
        print(f"\n✅ Seed data generated successfully!")
        print(f"   • {len(models)} models")
        print(f"   • 10 historical benchmark runs")
        print(f"   • {len(models) * len(tasks) * 10} total task results")
        
    except Exception as e:
        print(f"❌ Error generating seed data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def check_existing_data():
    """Check if there's already benchmark data in the database."""
    db = SessionLocal()
    try:
        count = db.query(BenchmarkResult).count()
        return count > 0
    finally:
        db.close()


if __name__ == "__main__":
    if check_existing_data():
        print("⚠️  Database already contains benchmark data.")
        response = input("   Overwrite with seed data? (yes/no): ")
        if response.lower() != "yes":
            print("   Skipping seed data generation.")
            exit(0)
    
    generate_seed_data()
