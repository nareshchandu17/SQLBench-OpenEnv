"""
Performance monitoring and metrics collection for SQLBench-OpenEnv
Tracks benchmark performance, API response times, and system metrics
"""

import time
import psutil
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime

@dataclass
class APIMetrics:
    """API call performance metrics"""
    model_name: str
    call_count: int
    total_time: float
    avg_time: float
    success_count: int
    error_count: int
    rate_limit_count: int
    
@dataclass
class SystemMetrics:
    """System resource metrics"""
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_percent: float
    
@dataclass
class BenchmarkMetrics:
    """Overall benchmark performance metrics"""
    start_time: float
    end_time: float
    total_duration: float
    models_evaluated: int
    tasks_completed: int
    total_api_calls: int
    system_metrics_start: SystemMetrics
    system_metrics_end: SystemMetrics
    api_metrics: List[APIMetrics]

class PerformanceMonitor:
    """Performance monitoring system for benchmarks"""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.api_calls: Dict[str, List[float]] = {}
        self.api_errors: Dict[str, int] = {}
        self.rate_limits: Dict[str, int] = {}
        self.models_evaluated = 0
        self.tasks_completed = 0
        
    def start_benchmark(self) -> None:
        """Start benchmark monitoring"""
        self.start_time = time.time()
        self.models_evaluated = 0
        self.tasks_completed = 0
        self.api_calls.clear()
        self.api_errors.clear()
        self.rate_limits.clear()
        
    def end_benchmark(self) -> None:
        """End benchmark monitoring"""
        self.end_time = time.time()
        
    def start_model_evaluation(self, model_name: str) -> None:
        """Track model evaluation start"""
        self.models_evaluated += 1
        if model_name not in self.api_calls:
            self.api_calls[model_name] = []
            self.api_errors[model_name] = 0
            self.rate_limits[model_name] = 0
            
    def record_api_call(self, model_name: str, duration: float, success: bool = True) -> None:
        """Record an API call with timing"""
        if model_name not in self.api_calls:
            self.api_calls[model_name] = []
            self.api_errors[model_name] = 0
            self.rate_limits[model_name] = 0
            
        self.api_calls[model_name].append(duration)
        if not success:
            self.api_errors[model_name] += 1
            
    def record_rate_limit(self, model_name: str) -> None:
        """Record a rate limit event"""
        if model_name not in self.rate_limits:
            self.rate_limits[model_name] = 0
        self.rate_limits[model_name] += 1
        
    def complete_task(self) -> None:
        """Record task completion"""
        self.tasks_completed += 1
        
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_mb=memory.used / 1024 / 1024,
            disk_percent=disk.percent
        )
        
    def get_api_metrics(self) -> List[APIMetrics]:
        """Get API performance metrics"""
        metrics = []
        
        for model_name, times in self.api_calls.items():
            if times:
                total_time = sum(times)
                avg_time = total_time / len(times)
                success_count = len(times) - self.api_errors.get(model_name, 0)
                error_count = self.api_errors.get(model_name, 0)
                rate_limit_count = self.rate_limits.get(model_name, 0)
                
                metrics.append(APIMetrics(
                    model_name=model_name,
                    call_count=len(times),
                    total_time=total_time,
                    avg_time=avg_time,
                    success_count=success_count,
                    error_count=error_count,
                    rate_limit_count=rate_limit_count
                ))
                
        return metrics
        
    def get_benchmark_metrics(self) -> BenchmarkMetrics:
        """Get complete benchmark metrics"""
        if not self.start_time or not self.end_time:
            raise ValueError("Benchmark not completed")
            
        total_duration = self.end_time - self.start_time
        start_metrics = self.get_system_metrics()
        
        return BenchmarkMetrics(
            start_time=self.start_time,
            end_time=self.end_time,
            total_duration=total_duration,
            models_evaluated=self.models_evaluated,
            tasks_completed=self.tasks_completed,
            total_api_calls=sum(len(times) for times in self.api_calls.values()),
            system_metrics_start=start_metrics,
            system_metrics_end=self.get_system_metrics(),
            api_metrics=self.get_api_metrics()
        )
        
    def save_metrics(self, output_dir: str = "benchmark_output") -> str:
        """Save metrics to JSON file"""
        Path(output_dir).mkdir(exist_ok=True)
        
        metrics = self.get_benchmark_metrics()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/performance_metrics_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(asdict(metrics), f, indent=2)
            
        return filename
        
    def print_summary(self) -> None:
        """Print performance summary"""
        if not self.start_time or not self.end_time:
            print("Benchmark not completed")
            return
            
        metrics = self.get_benchmark_metrics()
        
        print(f"\n{'='*60}")
        print(f" PERFORMANCE METRICS")
        print(f"{'='*60}")
        print(f"Total Duration: {metrics.total_duration:.1f}s")
        print(f"Models Evaluated: {metrics.models_evaluated}")
        print(f"Tasks Completed: {metrics.tasks_completed}")
        print(f"Total API Calls: {metrics.total_api_calls}")
        
        print(f"\nAPI Performance:")
        for api_metric in metrics.api_metrics:
            print(f"  {api_metric.model_name}:")
            print(f"    Calls: {api_metric.call_count}")
            print(f"    Avg Time: {api_metric.avg_time:.2f}s")
            print(f"    Success: {api_metric.success_count}")
            print(f"    Errors: {api_metric.error_count}")
            print(f"    Rate Limits: {api_metric.rate_limit_count}")
            
        print(f"\nSystem Usage:")
        print(f"  CPU: {metrics.system_metrics_end.cpu_percent:.1f}%")
        print(f"  Memory: {metrics.system_metrics_end.memory_percent:.1f}% ({metrics.system_metrics_end.memory_mb:.1f}MB)")
        print(f"  Disk: {metrics.system_metrics_end.disk_percent:.1f}%")
        print(f"{'='*60}\n")

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance"""
    return performance_monitor
