#!/usr/bin/env python3
"""
Simple Database Persistence Test
Focus on core functionality validation
"""

import os
import sys
import requests
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, init_db
from benchmark.models import BenchmarkRun, BenchmarkSummary, ModelPerformance

def test_database_connection():
    """Test basic database connection and table creation."""
    print("🗄️ Database Connection Test")
    print("-" * 40)
    
    try:
        # Initialize database
        init_db()
        print("✅ Database initialized successfully")
        
        # Test connection
        db = SessionLocal()
        try:
            # Test basic query
            run_count = db.query(BenchmarkRun).count()
            summary_count = db.query(BenchmarkSummary).count()
            performance_count = db.query(ModelPerformance).count()
            
            print(f"✅ Database connection successful")
            print(f"   Benchmark runs: {run_count}")
            print(f"   Summaries: {summary_count}")
            print(f"   Performance records: {performance_count}")
            
            db.close()
            return True
            
        except Exception as e:
            print(f"❌ Database query failed: {e}")
            db.close()
            return False
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

def test_api_endpoints():
    """Test key API endpoints."""
    print("\n🌐 API Endpoints Test")
    print("-" * 40)
    
    base_url = "http://127.0.0.1:7863"
    endpoints = [
        ("/health", "Health Check"),
        ("/api/results", "Results API"),
        ("/api/leaderboard", "Leaderboard API"),
        ("/api/analytics/timeseries", "Analytics API"),
        ("/jobs", "Jobs API")
    ]
    
    passed = 0
    total = len(endpoints)
    
    for endpoint, name in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            
            if response.status_code == 200:
                print(f"✅ {name}: {response.status_code}")
                passed += 1
            else:
                print(f"❌ {name}: {response.status_code}")
                
        except Exception as e:
            print(f"❌ {name}: Error - {str(e)[:100]}")
    
    success_rate = (passed / total) * 100 if total > 0 else 0
    print(f"\n📊 API Test Results: {passed}/{total} ({success_rate:.1f}%)")
    
    return success_rate >= 80

def test_data_persistence():
    """Test that data persists across operations."""
    print("\n💾 Data Persistence Test")
    print("-" * 40)
    
    try:
        # Check current database state
        db = SessionLocal()
        try:
            initial_runs = db.query(BenchmarkRun).count()
            db.close()
            
            print(f"Initial benchmark runs: {initial_runs}")
            
            # Test via API that data is accessible
            response = requests.get("http://127.0.0.1:7863/api/results", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                total_results = data.get('total_count', 0)
                
                print(f"✅ API data access successful")
                print(f"   Total results via API: {total_results}")
                print(f"   Database consistency: {'✅ MATCH' if total_results == initial_runs else '❌ MISMATCH'}")
                
                return total_results > 0
            else:
                print(f"❌ API access failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Data persistence test failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def generate_test_report(db_test, api_test, persistence_test):
    """Generate final test report."""
    print("\n" + "="*60)
    print("📊 SIMPLE PERSISTENCE TEST REPORT")
    print("="*60)
    
    # Count results
    tests = [
        ("Database Connection", db_test),
        ("API Endpoints", api_test),
        ("Data Persistence", persistence_test)
    ]
    
    passed = sum(1 for test in tests if test)
    total = len(tests)
    success_rate = (passed / total) * 100 if total > 0 else 0
    
    print(f"\n🎯 TEST SUMMARY:")
    print(f"   Tests passed: {passed}/{total}")
    print(f"   Success rate: {success_rate:.1f}%")
    
    # Individual test results
    for test_name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {test_name}")
    
    # Overall assessment
    if success_rate >= 80:
        print(f"\n🏆 OVERALL: EXCELLENT - Database persistence fully functional")
    elif success_rate >= 60:
        print(f"\n✅ OVERALL: GOOD - Database persistence functional with minor issues")
    else:
        print(f"\n❌ OVERALL: NEEDS WORK - Database persistence has significant issues")
    
    return success_rate >= 60

def main():
    """Run simple database persistence test."""
    print("🗄️ SIMPLE DATABASE PERSISTENCE TEST")
    print("="*60)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run tests
    db_test = test_database_connection()
    api_test = test_api_endpoints()
    persistence_test = test_data_persistence()
    
    # Generate report
    success = generate_test_report(db_test, api_test, persistence_test)
    
    print(f"\n🏁 Simple persistence test complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
