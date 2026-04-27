"""
Logging configuration for SQLBench-OpenEnv
Provides structured logging for debugging and monitoring
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    enable_console: bool = True
) -> None:
    """
    Setup logging configuration for the benchmark
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
        enable_console: Whether to enable console output
    """
    
    # Create logs directory if needed
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(exist_ok=True, parents=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name"""
    return logging.getLogger(name)

def log_benchmark_start(model_count: int, task_count: int) -> None:
    """Log benchmark start information"""
    logger = get_logger("benchmark")
    logger.info(f"Starting benchmark: {model_count} models × {task_count} tasks")

def log_benchmark_complete(duration: float, results_count: int) -> None:
    """Log benchmark completion"""
    logger = get_logger("benchmark")
    logger.info(f"Benchmark completed in {duration:.1f}s with {results_count} results")

def log_model_start(model_name: str) -> None:
    """Log model evaluation start"""
    logger = get_logger("benchmark")
    logger.info(f"Evaluating model: {model_name}")

def log_task_result(task_id: str, difficulty: str, score: float, solved: bool) -> None:
    """Log individual task result"""
    logger = get_logger("benchmark")
    status = "SOLVED" if solved else f"score={score:.3f}"
    logger.info(f"Task {task_id} [{difficulty}]: {status}")

def log_api_error(model_name: str, error: str) -> None:
    """Log API errors"""
    logger = get_logger("api")
    logger.warning(f"API error for {model_name}: {error}")

def log_rate_limit(model_name: str, retry_count: int) -> None:
    """Log rate limiting events"""
    logger = get_logger("api")
    logger.info(f"Rate limit for {model_name}, retry {retry_count}")

# Default setup for immediate use
if __name__ == "__main__":
    # Example usage
    setup_logging(level="DEBUG", log_file="logs/benchmark.log")
    
    logger = get_logger("test")
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
