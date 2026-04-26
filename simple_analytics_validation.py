#!/usr/bin/env python3
"""
Simple Analytics System Validation Test
Focus on core analytics functionality validation
"""

import os
import sys
import requests
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analytics import AnalyticsEngine
from database import SessionLocal
from benchmark.models import ModelPerformance

def test_analytics_api_response():
    """Test analytics API response structure and content."""
    print("📊 Analytics API Response Test")
    print("-" * 40)
    
    try:
        # Test model comparison API
        response = requests.get('http://127.0.0.1:7863/api/analytics/model-comparison', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Validate structure
            required_fields = ['timeseries', 'insights', 'summary']
            structure_valid = all(field in data for field in required_fields)
            
            # Get details
            timeseries = data.get('timeseries', {})
            insights = data.get('insights', [])
            summary = data.get('summary', {})
            
            models = list(timeseries.keys())
            total_runs = summary.get('total_runs', 0)
            
            print(f"✅ API response structure valid: {structure_valid}")
            print(f"✅ Models in timeseries: {len(models)}")
            print(f"✅ Insights generated: {len(insights)}")
            print(f"✅ Total runs: {total_runs}")
            
            # Show sample data
            if models:
                model_name = models[0]
                model_data = timeseries[model_name]
                print(f"✅ Sample model data: {model_name}")
                print(f"   Data points: {len(model_data)}")
                if model_data:
                    print(f"   Latest score: {model_data[-1].get('score', 'N/A')}")
            
            # Show sample insights
            if insights:
                print(f"✅ Sample insights:")
                for i, insight in enumerate(insights[:3], 1):
                    print(f"   {i}. {insight}")
            
            return structure_valid and len(models) > 0 and len(insights) > 0
            
        else:
            print(f"❌ API request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_trend_detection():
    """Test trend detection functionality."""
    print("\n📈 Trend Detection Test")
    print("-" * 40)
    
    try:
        analytics = AnalyticsEngine()
        
        # Test with different score patterns
        test_cases = [
            ([0.5, 0.6, 0.7, 0.8], "improving"),
            ([0.8, 0.7, 0.6, 0.5], "declining"),
            ([0.6, 0.65, 0.6, 0.65], "stable"),
            ([0.5], "stable"),  # Single point
            ([], "stable")  # Empty
        ]
        
        results = []
        
        for scores, expected_trend in test_cases:
            detected_trend = analytics.calculate_trend(scores)
            match = detected_trend == expected_trend
            
            print(f"Scores: {scores}")
            print(f"Expected: {expected_trend}, Detected: {detected_trend}, Match: {'✅' if match else '❌'}")
            
            results.append(match)
        
        accuracy = sum(results) / len(results) * 100
        print(f"\n📊 Trend Detection Accuracy: {accuracy:.1f}%")
        
        return accuracy >= 80
        
    except Exception as e:
        print(f"❌ Trend detection test failed: {e}")
        return False

def test_consistency_calculation():
    """Test consistency calculation."""
    print("\n🎯 Consistency Calculation Test")
    print("-" * 40)
    
    try:
        analytics = AnalyticsEngine()
        
        # Test with different score patterns
        test_cases = [
            ([0.5, 0.5, 0.5, 0.5], "highly consistent"),  # Perfect consistency
            ([0.5, 0.51, 0.49, 0.5], "consistent"),  # Low variance
            ([0.5, 0.6, 0.4, 0.7], "moderately variable"),  # Medium variance
            ([0.5, 0.8, 0.2, 0.9], "highly variable"),  # High variance
            ([0.5], "highly consistent"),  # Single point
        ]
        
        results = []
        
        for scores, expected_consistency in test_cases:
            variance, detected_consistency = analytics.calculate_consistency(scores)
            match = detected_consistency == expected_consistency
            
            print(f"Scores: {scores}")
            print(f"Variance: {variance:.4f}")
            print(f"Expected: {expected_consistency}, Detected: {detected_consistency}, Match: {'✅' if match else '❌'}")
            
            results.append(match)
        
        accuracy = sum(results) / len(results) * 100
        print(f"\n📊 Consistency Calculation Accuracy: {accuracy:.1f}%")
        
        return accuracy >= 80
        
    except Exception as e:
        print(f"❌ Consistency test failed: {e}")
        return False

def test_insight_generation():
    """Test insight generation."""
    print("\n🧠 Insight Generation Test")
    print("-" * 40)
    
    try:
        analytics = AnalyticsEngine()
        
        # Test with sample data
        sample_data = {
            "Model A": [
                {"score": 0.5, "run_id": "run_1", "timestamp": "2024-01-01"},
                {"score": 0.7, "run_id": "run_2", "timestamp": "2024-01-02"},
                {"score": 0.6, "run_id": "run_3", "timestamp": "2024-01-03"}
            ],
            "Model B": [
                {"score": 0.8, "run_id": "run_1", "timestamp": "2024-01-01"},
                {"score": 0.9, "run_id": "run_2", "timestamp": "2024-01-02"},
                {"score": 0.85, "run_id": "run_3", "timestamp": "2024-01-03"}
            ]
        }
        
        # Generate insights
        full_insights = analytics.generate_full_insights(sample_data)
        
        insights = full_insights.get('insights', [])
        summary = full_insights.get('summary', {})
        
        print(f"✅ Insights generated: {len(insights)}")
        print(f"✅ Summary: {summary}")
        
        # Validate insights
        valid_insights = True
        for insight in insights:
            if len(insight) < 20:  # Too short to be meaningful
                valid_insights = False
                print(f"❌ Insight too short: {insight}")
        
        if valid_insights:
            print("✅ All insights have meaningful length")
        
        # Show sample insights
        if insights:
            print(f"\n🧠 Generated Insights:")
            for i, insight in enumerate(insights[:3], 1):
                print(f"   {i}. {insight}")
        
        return len(insights) > 0 and valid_insights
        
    except Exception as e:
        print(f"❌ Insight generation test failed: {e}")
        return False

def test_database_consistency():
    """Test database consistency with analytics data."""
    print("\n🗄️ Database Consistency Test")
    print("-" * 40)
    
    try:
        # Get data from analytics engine
        analytics = AnalyticsEngine()
        analytics_data = analytics.get_model_comparison_data()
        
        # Get data directly from database
        db = SessionLocal()
        try:
            db_performances = db.query(ModelPerformance).all()
            
            # Count records
            analytics_total = sum(len(data) for data in analytics_data.values())
            db_total = len(db_performances)
            
            print(f"Analytics total records: {analytics_total}")
            print(f"Database total records: {db_total}")
            
            # Check model consistency
            analytics_models = set(analytics_data.keys())
            db_models = set(perf.model_name for perf in db_performances)
            
            print(f"Analytics models: {analytics_models}")
            print(f"Database models: {db_models}")
            
            model_consistency = analytics_models == db_models
            record_consistency = analytics_total == db_total
            
            print(f"✅ Model consistency: {model_consistency}")
            print(f"✅ Record consistency: {record_consistency}")
            
            return model_consistency and record_consistency
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Database consistency test failed: {e}")
        return False

def test_insight_meaningfulness():
    """Test if insights are meaningful and not hardcoded."""
    print("\n🎯 Insight Meaningfulness Test")
    print("-" * 40)
    
    try:
        # Get insights from API
        response = requests.get('http://127.0.0.1:7863/api/analytics/model-comparison', timeout=10)
        
        if response.status_code != 200:
            print(f"❌ API request failed: {response.status_code}")
            return False
        
        data = response.json()
        insights = data.get('insights', [])
        
        if not insights:
            print("❌ No insights found")
            return False
        
        print(f"🧠 Analyzing {len(insights)} insights...")
        
        # Analyze insight quality
        quality_metrics = {
            'total_insights': len(insights),
            'avg_length': 0,
            'model_specific': 0,
            'performance_related': 0,
            'contains_numbers': 0,
            'emoji_usage': 0
        }
        
        model_names = ['llama', 'gemma', 'dolphin', 'mistral']
        performance_words = ['score', 'performance', 'improving', 'declining', 'trend']
        
        for insight in insights:
            # Length
            quality_metrics['avg_length'] += len(insight)
            
            # Model specificity
            if any(model in insight.lower() for model in model_names):
                quality_metrics['model_specific'] += 1
            
            # Performance related
            if any(word in insight.lower() for word in performance_words):
                quality_metrics['performance_related'] += 1
            
            # Numeric values
            import re
            if re.search(r'\d+\.\d+', insight):
                quality_metrics['contains_numbers'] += 1
            
            # Emoji usage (indicates dynamic formatting)
            if any(char in insight for char in ['📈', '📉', '🏆', '⚠️', '🎯']):
                quality_metrics['emoji_usage'] += 1
        
        # Calculate averages
        if quality_metrics['total_insights'] > 0:
            quality_metrics['avg_length'] = quality_metrics['avg_length'] / quality_metrics['total_insights']
        
        print(f"\n📊 Quality Metrics:")
        print(f"   Total insights: {quality_metrics['total_insights']}")
        print(f"   Average length: {quality_metrics['avg_length']:.1f} characters")
        print(f"   Model-specific: {quality_metrics['model_specific']}/{quality_metrics['total_insights']}")
        print(f"   Performance-related: {quality_metrics['performance_related']}/{quality_metrics['total_insights']}")
        print(f"   Contains numbers: {quality_metrics['contains_numbers']}/{quality_metrics['total_insights']}")
        print(f"   Emoji usage: {quality_metrics['emoji_usage']}/{quality_metrics['total_insights']}")
        
        # Show sample insights
        print(f"\n🧠 Sample Insights:")
        for i, insight in enumerate(insights[:3], 1):
            print(f"   {i}. {insight}")
        
        # Determine meaningfulness
        meaningfulness_score = 0
        if quality_metrics['avg_length'] > 40:
            meaningfulness_score += 1
        if quality_metrics['model_specific'] >= quality_metrics['total_insights'] * 0.5:
            meaningfulness_score += 1
        if quality_metrics['performance_related'] >= quality_metrics['total_insights'] * 0.5:
            meaningfulness_score += 1
        if quality_metrics['contains_numbers'] > 0:
            meaningfulness_score += 1
        if quality_metrics['emoji_usage'] > 0:
            meaningfulness_score += 1
        
        meaningful = meaningfulness_score >= 3  # At least 3 of 5 criteria
        
        print(f"\n🎯 Meaningfulness Score: {meaningfulness_score}/5")
        print(f"   Meaningful: {'✅ YES' if meaningful else '❌ NO'}")
        
        return meaningful
        
    except Exception as e:
        print(f"❌ Insight meaningfulness test failed: {e}")
        return False

def generate_validation_report(test_results):
    """Generate validation report."""
    print("\n" + "="*60)
    print("📊 ANALYTICS VALIDATION REPORT")
    print("="*60)
    
    # Count results
    passed = sum(1 for result in test_results if result)
    total = len(test_results)
    success_rate = (passed / total) * 100 if total > 0 else 0
    
    print(f"\n🎯 VALIDATION SUMMARY:")
    print(f"   Tests passed: {passed}/{total}")
    print(f"   Success rate: {success_rate:.1f}%")
    
    # Test names
    test_names = [
        "Analytics API Response",
        "Trend Detection", 
        "Consistency Calculation",
        "Insight Generation",
        "Database Consistency",
        "Insight Meaningfulness"
    ]
    
    print(f"\n📋 TEST RESULTS:")
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {name}")
    
    # Overall assessment
    if success_rate >= 90:
        print(f"\n🏆 OVERALL: EXCELLENT - Analytics system fully functional")
    elif success_rate >= 75:
        print(f"\n✅ OVERALL: GOOD - Analytics system functional with minor issues")
    else:
        print(f"\n❌ OVERALL: NEEDS WORK - Analytics system has significant issues")
    
    return success_rate >= 75

def main():
    """Run simple analytics validation test."""
    print("🧪 SIMPLE ANALYTICS VALIDATION TEST")
    print("="*60)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run tests
    test_results = []
    
    test_results.append(test_analytics_api_response())
    test_results.append(test_trend_detection())
    test_results.append(test_consistency_calculation())
    test_results.append(test_insight_generation())
    test_results.append(test_database_consistency())
    test_results.append(test_insight_meaningfulness())
    
    # Generate report
    success = generate_validation_report(test_results)
    
    print(f"\n🏁 Analytics validation complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
