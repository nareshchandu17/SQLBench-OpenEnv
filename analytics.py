"""
analytics.py

Research-grade analytics engine for AI benchmarking platform.
Provides model comparison insights, trend detection, and performance analytics.
"""

import json
import statistics
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from datetime import datetime

from database import SessionLocal
from benchmark.models import ModelPerformance, BenchmarkSummary


class AnalyticsEngine:
    """Advanced analytics engine for model performance insights."""
    
    def __init__(self):
        self.insight_templates = {
            "improving": "📈 {model} shows consistent improvement across runs (score: {first:.3f} → {last:.3f})",
            "declining": "📉 {model} performance is declining (score: {first:.3f} → {last:.3f})",
            "stable": "➡️ {model} performance is stable (avg: {avg:.3f}, variance: {variance:.3f})",
            "best_overall": "🏆 {model} is the best performing model overall (avg: {score:.3f})",
            "most_consistent": "🎯 {model} shows highest consistency (variance: {variance:.3f})",
            "high_variance": "⚠️ {model} shows high performance variance (variance: {variance:.3f}) - may be unstable",
            "rate_limited": "🚫 {model} appears affected by rate limiting (inconsistent scores)",
            "outlier": "🔍 {model} has outlier performance in run {run_id} (score: {score:.3f})"
        }
    
    def get_model_comparison_data(self) -> Dict[str, List[Dict]]:
        """
        Get time-series data for model comparison across runs.
        
        Returns:
            Dict mapping model names to list of performance data points
        """
        db = SessionLocal()
        try:
            # Query all model performance data ordered by timestamp
            data = db.query(ModelPerformance)\
                   .order_by(ModelPerformance.created_at)\
                   .all()
            
            # Group by model name
            result = defaultdict(list)
            
            for row in data:
                result[row.model_name].append({
                    "run_id": row.run_id,
                    "score": row.average_score,
                    "timestamp": row.created_at.isoformat() if row.created_at else None,
                    "solve_rate": row.solve_rate,
                    "tasks_solved": row.tasks_solved,
                    "total_tasks": row.total_tasks
                })
            
            return dict(result)
            
        except Exception as e:
            print(f"Error fetching model comparison data: {e}")
            return {}
        finally:
            db.close()
    
    def calculate_trend(self, scores: List[float]) -> str:
        """
        Calculate performance trend from score series.
        
        Args:
            scores: List of scores in chronological order
            
        Returns:
            Trend string: "improving", "declining", or "stable"
        """
        if len(scores) < 2:
            return "stable"
        
        # Simple linear regression to determine trend
        first_half = scores[:len(scores)//2] if len(scores) >= 4 else scores[:1]
        second_half = scores[len(scores)//2:] if len(scores) >= 4 else scores[1:]
        
        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)
        
        # Determine trend with threshold
        threshold = 0.02  # 2% change threshold
        if second_avg > first_avg + threshold:
            return "improving"
        elif second_avg < first_avg - threshold:
            return "declining"
        else:
            return "stable"
    
    def calculate_consistency(self, scores: List[float]) -> Tuple[float, str]:
        """
        Calculate performance consistency using variance.
        
        Args:
            scores: List of scores
            
        Returns:
            Tuple of (variance, consistency_level)
        """
        if len(scores) < 2:
            return 0.0, "highly consistent"
        
        variance = statistics.variance(scores)
        
        if variance < 0.001:
            consistency = "highly consistent"
        elif variance < 0.01:
            consistency = "consistent"
        elif variance < 0.05:
            consistency = "moderately variable"
        else:
            consistency = "highly variable"
        
        return variance, consistency
    
    def detect_outliers(self, scores: List[float]) -> List[int]:
        """
        Detect outlier scores using IQR method.
        
        Args:
            scores: List of scores
            
        Returns:
            List of outlier indices
        """
        if len(scores) < 4:
            return []
        
        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        
        # Calculate IQR
        q1_idx = n // 4
        q3_idx = 3 * n // 4
        q1 = sorted_scores[q1_idx]
        q3 = sorted_scores[q3_idx]
        iqr = q3 - q1
        
        # Outlier thresholds
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        # Find outliers
        outliers = []
        for i, score in enumerate(scores):
            if score < lower_bound or score > upper_bound:
                outliers.append(i)
        
        return outliers
    
    def generate_model_insights(self, model_name: str, data_points: List[Dict]) -> List[str]:
        """
        Generate insights for a specific model.
        
        Args:
            model_name: Name of the model
            data_points: List of performance data points
            
        Returns:
            List of insight strings
        """
        if not data_points:
            return []
        
        insights = []
        scores = [dp["score"] for dp in data_points]
        
        # Trend analysis
        trend = self.calculate_trend(scores)
        if trend in ["improving", "declining"]:
            insights.append(self.insight_templates[trend].format(
                model=model_name,
                first=scores[0],
                last=scores[-1]
            ))
        
        # Consistency analysis
        variance, consistency = self.calculate_consistency(scores)
        if variance > 0.05:  # High variance
            insights.append(self.insight_templates["high_variance"].format(
                model=model_name,
                variance=variance
            ))
        elif variance < 0.001:  # Very consistent
            insights.append(self.insight_templates["most_consistent"].format(
                model=model_name,
                variance=variance
            ))
        elif trend == "stable":
            insights.append(self.insight_templates["stable"].format(
                model=model_name,
                avg=statistics.mean(scores),
                variance=variance
            ))
        
        # Outlier detection
        outliers = self.detect_outliers(scores)
        for outlier_idx in outliers[:2]:  # Limit to top 2 outliers
            insights.append(self.insight_templates["outlier"].format(
                model=model_name,
                run_id=data_points[outlier_idx]["run_id"][:8],
                score=scores[outlier_idx]
            ))
        
        # Rate limiting detection (inconsistent performance with low solve rates)
        solve_rates = [dp.get("solve_rate", 0) for dp in data_points]
        avg_solve_rate = statistics.mean(solve_rates)
        if variance > 0.02 and avg_solve_rate < 0.5:
            insights.append(self.insight_templates["rate_limited"].format(model=model_name))
        
        return insights
    
    def generate_comparative_insights(self, all_data: Dict[str, List[Dict]]) -> List[str]:
        """
        Generate comparative insights across all models.
        
        Args:
            all_data: Dictionary of all model performance data
            
        Returns:
            List of comparative insight strings
        """
        insights = []
        
        if not all_data:
            return insights
        
        # Calculate average scores for all models
        model_averages = {}
        for model_name, data_points in all_data.items():
            if data_points:
                scores = [dp["score"] for dp in data_points]
                model_averages[model_name] = statistics.mean(scores)
        
        if not model_averages:
            return insights
        
        # Best performing model
        best_model = max(model_averages.items(), key=lambda x: x[1])
        insights.append(self.insight_templates["best_overall"].format(
            model=best_model[0],
            score=best_model[1]
        ))
        
        # Performance gaps
        if len(model_averages) > 1:
            scores = list(model_averages.values())
            max_score = max(scores)
            min_score = min(scores)
            gap = max_score - min_score
            
            if gap > 0.2:  # Significant performance gap
                insights.append(f"📊 Significant performance gap detected: {gap:.3f} points between best and worst models")
            elif gap < 0.05:  # Very close performance
                insights.append("🤝 Models show very similar performance levels")
        
        return insights
    
    def generate_full_insights(self, comparison_data: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """
        Generate complete analytics insights.
        
        Args:
            comparison_data: Model comparison time-series data
            
        Returns:
            Complete analytics response with timeseries and insights
        """
        # Generate individual model insights
        model_insights = {}
        for model_name, data_points in comparison_data.items():
            model_insights[model_name] = self.generate_model_insights(model_name, data_points)
        
        # Generate comparative insights
        comparative_insights = self.generate_comparative_insights(comparison_data)
        
        # Flatten all insights
        all_insights = []
        for model_name, insights in model_insights.items():
            all_insights.extend(insights)
        all_insights.extend(comparative_insights)
        
        # Sort insights by relevance (simple heuristic)
        priority_keywords = ["🏆", "📈", "📉", "⚠️", "🚫"]
        prioritized_insights = []
        other_insights = []
        
        for insight in all_insights:
            if any(keyword in insight for keyword in priority_keywords):
                prioritized_insights.append(insight)
            else:
                other_insights.append(insight)
        
        final_insights = prioritized_insights + other_insights[:3]  # Limit total insights
        
        return {
            "timeseries": comparison_data,
            "insights": final_insights,
            "summary": {
                "total_models": len(comparison_data),
                "total_runs": sum(len(data) for data in comparison_data.values()),
                "date_range": self._get_date_range(comparison_data),
                "generated_at": datetime.now().isoformat()
            }
        }
    
    def _get_date_range(self, comparison_data: Dict[str, List[Dict]]) -> Dict[str, str]:
        """Get date range of the data."""
        all_timestamps = []
        for data_points in comparison_data.values():
            for dp in data_points:
                if dp.get("timestamp"):
                    all_timestamps.append(dp["timestamp"])
        
        if not all_timestamps:
            return {"start": None, "end": None}
        
        return {
            "start": min(all_timestamps),
            "end": max(all_timestamps)
        }


# Global analytics engine instance
analytics_engine = AnalyticsEngine()
