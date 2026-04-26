"""
benchmark/models.py

ORM models for benchmark result persistence.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text, Boolean, Index
from sqlalchemy.sql import func
from datetime import datetime
from database import Base


class BenchmarkRun(Base):
    """Individual benchmark run result for a specific model and task."""
    __tablename__ = "benchmark_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True)  # UUID for grouping runs
    model_name = Column(String, index=True)
    model_id = Column(String, index=True)  # Internal model identifier
    task_id = Column(String, index=True)
    task_difficulty = Column(String, index=True)
    
    # Performance metrics
    episode_score = Column(Float, index=True)
    total_reward = Column(Float)
    steps_taken = Column(Integer)
    solved = Column(Boolean, default=False, index=True)
    
    # Timing information
    duration_seconds = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Error information
    error_category = Column(String, index=True)
    api_errors = Column(Text)  # JSON string of API errors
    status = Column(String, default="completed", index=True)  # completed, failed, rate_limited
    
    # Additional metadata
    extra_data = Column(Text)  # JSON string for additional data


class BenchmarkSummary(Base):
    """Aggregated summary for each benchmark run."""
    __tablename__ = "benchmark_summaries"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, unique=True, index=True)
    
    # Run metadata
    started_at = Column(DateTime, index=True)
    completed_at = Column(DateTime, index=True)
    status = Column(String, index=True)  # running, completed, failed
    
    # Configuration snapshot
    models_config = Column(Text)  # JSON string of models configuration
    tasks_config = Column(Text)   # JSON string of tasks configuration
    settings = Column(Text)       # JSON string of benchmark settings
    
    # Aggregated metrics
    total_tasks = Column(Integer)
    completed_tasks = Column(Integer)
    average_score = Column(Float)
    total_duration = Column(Float)
    
    # Error summary
    error_summary = Column(Text)  # JSON string of error taxonomy
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ModelPerformance(Base):
    """Model performance per benchmark run for analytics."""
    __tablename__ = "model_performance"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True)  # Links to BenchmarkSummary
    model_name = Column(String, index=True)
    model_id = Column(String, index=True)
    
    # Performance metrics for this model in this run
    average_score = Column(Float, index=True)
    tasks_solved = Column(Integer)
    total_tasks = Column(Integer)
    solve_rate = Column(Float)
    
    # Timing
    avg_duration = Column(Float)
    total_duration = Column(Float)
    
    # Difficulty breakdown
    easy_avg = Column(Float)
    medium_avg = Column(Float)
    hard_avg = Column(Float)
    
    # Error analysis
    error_categories = Column(Text)  # JSON string of error distribution
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Unique constraint to prevent duplicates
    __table_args__ = (
        Index('idx_run_model', 'run_id', 'model_name', unique=True),
    )


class LeaderboardView(Base):
    """Materialized view for leaderboard queries (optional optimization)."""
    __tablename__ = "leaderboard_view"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, index=True)
    model_id = Column(String, index=True)
    
    # Performance metrics
    average_score = Column(Float, index=True)
    tasks_solved = Column(Integer)
    total_tasks = Column(Integer)
    
    # Difficulty breakdown
    easy_avg = Column(Float)
    medium_avg = Column(Float)
    hard_avg = Column(Float)
    
    # Timing
    avg_duration = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow, index=True)


# Helper functions for database operations
def create_run_id():
    """Generate a unique run ID."""
    import uuid
    return str(uuid.uuid4())


def serialize_errors(errors):
    """Serialize error list to JSON string."""
    import json
    return json.dumps(errors) if errors else None


def deserialize_errors(error_string):
    """Deserialize JSON string to error list."""
    import json
    return json.loads(error_string) if error_string else []


def serialize_extra_data(data):
    """Serialize extra data dict to JSON string."""
    import json
    return json.dumps(data) if data else None


def deserialize_extra_data(extra_data_string):
    """Deserialize JSON string to extra data dict."""
    import json
    return json.loads(extra_data_string) if extra_data_string else None
