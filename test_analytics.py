#!/usr/bin/env python3
"""
Test the research-grade analytics layer for model comparison insights.
"""

import requests
import time
import json

BASE_URL = "http://127.0.0.1:7863"

def test_analytics_api():
    """Test analytics API endpoints."""
    print("=" * 60)
    print("  Analytics API Test")
    print("=" * 60)
    
    # Test 1: Model Comparison Analytics
    print("1. Testing model comparison analytics...")
    try:
        response = requests.get(f"{BASE_URL}/api/analytics/model-comparison")
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Analytics API working")
        print(f"   Timeseries models: {len(data.get('timeseries', {}))}")
        print(f"   Insights generated: {len(data.get('insights', []))}")
        print(f"   Summary: {data.get('summary', {})}")
        
        if data.get('insights'):
            print("   Sample insights:")
            for insight in data['insights'][:3]:
                print(f"     • {insight}")
        
    except Exception as e:
        print(f"❌ Model comparison API failed: {e}")
        return False
    
    # Test 2: Time Series Data
    print("\n2. Testing time series data...")
    try:
        response = requests.get(f"{BASE_URL}/api/analytics/timeseries")
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Time series API working")
        print(f"   Models tracked: {data['summary']['total_models']}")
        print(f"   Data points: {data['summary']['total_data_points']}")
        
        # Show sample data
        timeseries = data.get('timeseries', {})
        if timeseries:
            model_name = list(timeseries.keys())[0]
            model_data = timeseries[model_name]
            print(f"   Sample {model_name} data:")
            for point in model_data[:2]:
                print(f"     Run {point['run_id'][:8]}: Score {point['score']:.3f}")
        
    except Exception as e:
        print(f"❌ Time series API failed: {e}")
        return False
    
    # Test 3: Insights Only
    print("\n3. Testing insights generation...")
    try:
        response = requests.get(f"{BASE_URL}/api/analytics/insights")
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Insights API working")
        print(f"   Total insights: {len(data.get('insights', []))}")
        
        if data.get('insights'):
            print("   Generated insights:")
            for insight in data['insights']:
                print(f"     • {insight}")
        
    except Exception as e:
        print(f"❌ Insights API failed: {e}")
        return False
    
    # Test 4: Individual Model Analytics
    print("\n4. Testing individual model analytics...")
    try:
        # First get available models
        response = requests.get(f"{BASE_URL}/api/analytics/timeseries")
        response.raise_for_status()
        timeseries = response.json().get('timeseries', {})
        
        if timeseries:
            model_name = list(timeseries.keys())[0]
            
            response = requests.get(f"{BASE_URL}/api/analytics/model/{model_name}")
            response.raise_for_status()
            data = response.json()
            
            print(f"✅ Model analytics API working")
            print(f"   Model: {data['model_name']}")
            print(f"   Total runs: {data['metrics']['total_runs']}")
            print(f"   Average score: {data['metrics']['average_score']:.3f}")
            print(f"   Variance: {data['metrics']['variance']:.3f}")
            print(f"   Best score: {data['metrics']['best_score']:.3f}")
            print(f"   Model insights: {len(data.get('insights', []))}")
        else:
            print("⚠ No model data available for individual analytics test")
        
    except Exception as e:
        print(f"❌ Model analytics API failed: {e}")
        return False
    
    return True

def test_analytics_engine():
    """Test the analytics engine directly."""
    print("\n" + "=" * 60)
    print("  Analytics Engine Test")
    print("=" * 60)
    
    try:
        from analytics import analytics_engine
        
        # Test data retrieval
        print("1. Testing data retrieval...")
        comparison_data = analytics_engine.get_model_comparison_data()
        
        print(f"✅ Retrieved data for {len(comparison_data)} models")
        for model_name, data_points in comparison_data.items():
            print(f"   {model_name}: {len(data_points)} data points")
        
        # Test insight generation
        print("\n2. Testing insight generation...")
        insights_response = analytics_engine.generate_full_insights(comparison_data)
        
        print(f"✅ Generated {len(insights_response['insights'])} insights")
        print("   Sample insights:")
        for insight in insights_response['insights'][:3]:
            print(f"     • {insight}")
        
        # Test analytics components
        print("\n3. Testing analytics components...")
        for model_name, data_points in comparison_data.items():
            if len(data_points) >= 2:
                scores = [dp['score'] for dp in data_points]
                
                # Trend calculation
                trend = analytics_engine.calculate_trend(scores)
                variance, consistency = analytics_engine.calculate_consistency(scores)
                outliers = analytics_engine.detect_outliers(scores)
                
                print(f"   {model_name}:")
                print(f"     Trend: {trend}")
                print(f"     Consistency: {consistency} (variance: {variance:.3f})")
                print(f"     Outliers: {len(outliers)}")
                
                break  # Just test first model
        
        return True
        
    except Exception as e:
        print(f"❌ Analytics engine test failed: {e}")
        return False

def test_database_schema():
    """Test database schema for analytics."""
    print("\n" + "=" * 60)
    print("  Database Schema Test")
    print("=" * 60)
    
    try:
        from database import SessionLocal
        from benchmark.models import ModelPerformance, BenchmarkSummary
        
        db = SessionLocal()
        
        # Test ModelPerformance table
        print("1. Testing ModelPerformance table...")
        performance_count = db.query(ModelPerformance).count()
        print(f"✅ ModelPerformance table accessible ({performance_count} records)")
        
        # Test BenchmarkSummary table  
        print("2. Testing BenchmarkSummary table...")
        summary_count = db.query(BenchmarkSummary).count()
        print(f"✅ BenchmarkSummary table accessible ({summary_count} records)")
        
        # Test data relationships
        if performance_count > 0:
            sample = db.query(ModelPerformance).first()
            print(f"   Sample record: {sample.model_name} | {sample.run_id[:8]} | {sample.average_score:.3f}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Database schema test failed: {e}")
        return False

def create_sample_data():
    """Create sample analytics data for testing."""
    print("\n" + "=" * 60)
    print("  Creating Sample Analytics Data")
    print("=" * 60)
    
    try:
        from database import SessionLocal
        from benchmark.models import ModelPerformance
        from datetime import datetime, timedelta
        import uuid
        
        db = SessionLocal()
        
        # Sample data
        models = [
            "Llama 3.3 70B",
            "Gemma 27B", 
            "Dolphin Mistral 24B"
        ]
        
        base_scores = [0.65, 0.78, 0.42]
        
        # Create 3 runs worth of data
        for run_idx in range(3):
            run_id = str(uuid.uuid4())
            
            for i, model_name in enumerate(models):
                # Add some variance to scores
                base_score = base_scores[i]
                variance = 0.05 * (run_idx - 1)  # Trend up/down
                noise = 0.02 * (hash(f"{run_id}{model_name}") % 10 - 5) / 10
                
                score = max(0.0, min(1.0, base_score + variance + noise))
                
                performance = ModelPerformance(
                    run_id=run_id,
                    model_name=model_name,
                    model_id=model_name.lower().replace(' ', '-'),
                    average_score=score,
                    tasks_solved=int(score * 6),  # Assuming 6 tasks
                    total_tasks=6,
                    solve_rate=score,
                    avg_duration=10.0 + run_idx * 2,
                    total_duration=(10.0 + run_idx * 2) * 6,
                    created_at=datetime.now() - timedelta(hours=run_idx)
                )
                
                db.add(performance)
        
        db.commit()
        db.close()
        
        print("✅ Sample analytics data created")
        print(f"   Created {len(models) * 3} model performance records")
        
        return True
        
    except Exception as e:
        print(f"❌ Sample data creation failed: {e}")
        return False

if __name__ == "__main__":
    print("🧠 Testing Research-Grade Analytics Layer")
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print("✅ Server is running")
    except Exception:
        print(f"❌ Server not running at {BASE_URL}")
        print("   Start with: python -c \"from server.app import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=7862)\"")
        exit(1)
    
    # Create sample data if needed
    schema_ok = test_database_schema()
    if schema_ok:
        # Check if we have data
        from database import SessionLocal
        from benchmark.models import ModelPerformance
        db = SessionLocal()
        count = db.query(ModelPerformance).count()
        db.close()
        
        if count == 0:
            print("\n⚠ No analytics data found, creating sample data...")
            create_sample_data()
    
    # Run tests
    engine_ok = test_analytics_engine()
    api_ok = test_analytics_api()
    
    print("\n" + "=" * 60)
    print("  Test Summary")
    print("=" * 60)
    
    results = [
        ("Analytics Engine", engine_ok),
        ("Analytics API", api_ok),
    ]
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name:<20} {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print(f"\n🎉 All analytics tests passed!")
        print(f"   📊 Time-series visualization ready")
        print(f"   🧠 AI-generated insights working")
        print(f"   📈 Model comparison analytics complete")
        print(f"\n   Access: http://127.0.0.1:7862")
        print(f"   Click: 📈 Load Analytics")
    else:
        print(f"\n❌ Some tests failed. Check analytics implementation.")
