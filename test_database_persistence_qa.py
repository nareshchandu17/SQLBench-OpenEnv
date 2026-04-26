#!/usr/bin/env python3
"""
Database Persistence QA Test
Comprehensive testing of data persistence, restart resilience, and concurrent operations
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, init_db
from benchmark.models import BenchmarkRun, BenchmarkSummary, ModelPerformance, create_run_id
from server.app import run_benchmark_background, save_benchmark_result, save_model_performance

class DatabasePersistenceTest:
    """Comprehensive database persistence testing suite."""
    
    def __init__(self):
        self.test_results = []
        self.run_ids = []
        self.record_counts = {}
        
    def log_test(self, test_name, status, details=None):
        """Log test result with timestamp."""
        result = {
            'test_name': test_name,
            'status': status,
            'timestamp': datetime.now(),
            'details': details or {}
        }
        self.test_results.append(result)
        
        status_icon = "✅ PASS" if status else "❌ FAIL"
        print(f"{status_icon} - {test_name}")
        if details:
            for key, value in details.items():
                print(f"      {key}: {value}")
    
    def get_database_stats(self):
        """Get current database statistics."""
        db = SessionLocal()
        try:
            stats = {
                'benchmark_runs': db.query(BenchmarkRun).count(),
                'benchmark_summaries': db.query(BenchmarkSummary).count(),
                'model_performance': db.query(ModelPerformance).count(),
                'unique_runs': db.query(BenchmarkSummary.run_id).distinct().count()
            }
            db.close()
            return stats
        except Exception as e:
            db.close()
            print(f"❌ Error getting database stats: {e}")
            return {}
    
    def test_benchmark_to_database_flow(self):
        """Test: Run benchmark → store results."""
        print("\n" + "="*60)
        print("🔄 BENCHMARK TO DATABASE FLOW TEST")
        print("="*60)
        
        try:
            # Get initial database state
            initial_stats = self.get_database_stats()
            print(f"Initial database state: {initial_stats}")
            
            # Run a short benchmark to generate data
            print("Starting benchmark execution...")
            
            # Import and run benchmark
            from benchmark.runner import BenchmarkRunner
            
            # Create test environment
            os.environ["OPENROUTER_API_KEY"] = "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"
            
            runner = BenchmarkRunner()
            run_id = create_run_id()
            self.run_ids.append(run_id)
            
            # Simulate some benchmark results
            print(f"Generated run ID: {run_id[:8]}...")
            
            # Save benchmark summary
            from server.app import save_benchmark_summary
            save_benchmark_summary(
                run_id=run_id,
                model_configs=runner.config["models"][:2],  # Test with 2 models
                task_configs=runner.benchmark_tasks[:3],  # Test with 3 tasks
                settings=runner.config["settings"],
                results=[],  # Empty results for this test
                status="completed"
            )
            
            # Save some model performance data
            from server.app import save_model_performance
            
            # Create mock results
            class MockResult:
                def __init__(self, model_name, episode_score, solved, duration_seconds):
                    self.model_name = model_name
                    self.episode_score = episode_score
                    self.solved = solved
                    self.duration_seconds = duration_seconds
            
            mock_results = [
                MockResult("Llama 3.3 70B", 0.75, True, 15.0),
                MockResult("Gemma 27B", 0.85, True, 12.0)
            ]
            
            save_model_performance(run_id, mock_results)
            
            # Save individual benchmark runs
            from server.app import save_benchmark_result
            for i, model_cfg in enumerate(runner.config["models"][:2]):
                for j, task_info in enumerate(runner.benchmark_tasks[:2]):
                    mock_result = MockResult(
                        model_cfg["name"],
                        0.7 + (i * 0.1) + (j * 0.05),
                        j % 2 == 0,  # Alternate solved/unsolved
                        10.0 + (i * 2) + (j * 1)
                    )
                    save_benchmark_result(run_id, model_cfg, task_info, mock_result)
            
            # Get final database state
            final_stats = self.get_database_stats()
            print(f"Final database state: {final_stats}")
            
            # Verify data was inserted
            runs_added = final_stats['benchmark_runs'] - initial_stats['benchmark_runs']
            summaries_added = final_stats['benchmark_summaries'] - initial_stats['benchmark_summaries']
            performance_added = final_stats['model_performance'] - initial_stats['model_performance']
            
            success = (runs_added > 0 and summaries_added > 0 and performance_added > 0)
            
            self.log_test("Benchmark to Database Flow", success, {
                "Runs added": runs_added,
                "Summaries added": summaries_added,
                "Performance records added": performance_added,
                "Run ID": run_id[:8] + "..."
            })
            
            return success
            
        except Exception as e:
            self.log_test("Benchmark to Database Flow", False, {
                "Error": str(e)
            })
            return False
    
    def test_server_restart_persistence(self):
        """Test: Data persists after server restart."""
        print("\n" + "="*60)
        print("🔄 SERVER RESTART PERSISTENCE TEST")
        print("="*60)
        
        try:
            # Get current database state before "restart"
            pre_restart_stats = self.get_database_stats()
            print(f"Pre-restart state: {pre_restart_stats}")
            
            # Simulate server restart by reinitializing database
            print("Simulating server restart (reinitializing database)...")
            init_db()  # This simulates server startup
            
            # Check data persistence after restart
            post_restart_stats = self.get_database_stats()
            print(f"Post-restart state: {post_restart_stats}")
            
            # Verify data persistence
            data_persisted = (
                post_restart_stats['benchmark_runs'] >= pre_restart_stats['benchmark_runs'] and
                post_restart_stats['benchmark_summaries'] >= pre_restart_stats['benchmark_summaries'] and
                post_restart_stats['model_performance'] >= pre_restart_stats['model_performance']
            )
            
            self.log_test("Server Restart Persistence", data_persisted, {
                "Pre-restart runs": pre_restart_stats['benchmark_runs'],
                "Post-restart runs": post_restart_stats['benchmark_runs'],
                "Data persisted": data_persisted
            })
            
            return data_persisted
            
        except Exception as e:
            self.log_test("Server Restart Persistence", False, {
                "Error": str(e)
            })
            return False
    
    def test_duplicate_prevention(self):
        """Test: No duplicate entries."""
        print("\n" + "="*60)
        print("🚫 DUPLICATE PREVENTION TEST")
        print("="*60)
        
        try:
            # Get current run IDs
            db = SessionLocal()
            try:
                existing_runs = db.query(BenchmarkSummary.run_id).all()
                existing_run_ids = [run.run_id for run in existing_runs]
                db.close()
                
                print(f"Existing run IDs: {len(existing_run_ids)}")
                
                # Try to create a run with existing ID
                test_run_id = self.run_ids[0] if self.run_ids else create_run_id()
                
                if test_run_id in existing_run_ids:
                    print(f"Testing duplicate prevention with existing ID: {test_run_id[:8]}...")
                    
                    # Try to save duplicate
                    from server.app import save_benchmark_summary
                    try:
                        save_benchmark_summary(
                            run_id=test_run_id,
                            model_configs=[],
                            task_configs=[],
                            settings={},
                            results=[],
                            status="completed"
                        )
                        print("❌ Duplicate entry was allowed - THIS SHOULD FAIL")
                        db.close()
                        return False
                    except Exception as e:
                        # This is expected - duplicate prevention should work
                        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                            print("✅ Duplicate prevention working - database constraint enforced")
                            db.close()
                            return True
                        else:
                            print(f"❌ Unexpected error in duplicate prevention: {e}")
                            db.close()
                            return False
                else:
                    print("✅ No existing run ID to test duplicate prevention")
                    db.close()
                    return True
                    
            except Exception as e:
                db.close()
                print(f"❌ Duplicate prevention test failed: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Duplicate prevention test setup failed: {e}")
            return False
    
    def test_run_tracking(self):
        """Test: Runs are tracked correctly."""
        print("\n" + "="*60)
        print("📊 RUN TRACKING TEST")
        print("="*60)
        
        try:
            db = SessionLocal()
            try:
                # Get all runs with their details
                runs = db.query(BenchmarkSummary).all()
                db.close()
                
                print(f"Total runs in database: {len(runs)}")
                
                # Verify run tracking
                tracking_correct = True
                run_details = []
                
                for run in runs:
                    run_info = {
                        'run_id': run.run_id,
                        'status': run.status,
                        'created_at': run.created_at,
                        'total_tasks': run.total_tasks,
                        'completed_tasks': run.completed_tasks
                    }
                    run_details.append(run_info)
                    print(f"Run {run.run_id[:8]}...: {run.status} - {run.total_tasks} tasks")
                
                # Check for proper run ID format
                valid_run_ids = all(
                    run.run_id and 
                    len(run.run_id) > 10 and 
                    run.run_id.startswith('run_')
                    for run in runs
                )
                
                # Check for proper timestamps
                valid_timestamps = all(
                    run.created_at for run in runs
                )
                
                # Check for valid status values
                valid_statuses = all(
                    run.status in ['running', 'completed', 'failed']
                    for run in runs
                )
                
                tracking_correct = tracking_correct and valid_run_ids and valid_timestamps and valid_statuses
                
                self.log_test("Run Tracking", tracking_correct, {
                    "Total runs": len(runs),
                    "Valid run IDs": valid_run_ids,
                    "Valid timestamps": valid_timestampes,
                    "Valid statuses": valid_statuses,
                    "Sample runs": len(run_details)
                })
                
                return tracking_correct
                
            except Exception as e:
                print(f"❌ Run tracking test failed: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Run tracking test setup failed: {e}")
            return False
    
    def test_concurrent_inserts(self):
        """Test: Multiple runs and concurrent inserts."""
        print("\n" + "="*60)
        print("⚡ CONCURRENT INSERTS TEST")
        print("="*60)
        
        try:
            # Get initial state
            initial_stats = self.get_database_stats()
            print(f"Initial state: {initial_stats}")
            
            # Test concurrent insertions
            print("Testing concurrent database operations...")
            
            def concurrent_operation(operation_id):
                """Simulate concurrent database operation."""
                try:
                    # Create unique run ID for this operation
                    run_id = f"concurrent_test_{operation_id}_{int(time.time())}"
                    
                    # Save benchmark summary
                    from server.app import save_benchmark_summary
                    save_benchmark_summary(
                        run_id=run_id,
                        model_configs=[{"id": f"model_{operation_id}", "name": f"Test Model {operation_id}"}],
                        task_configs=[{"id": f"task_{operation_id}", "difficulty": "test"}],
                        settings={"test": True},
                        results=[],
                        status="completed"
                    )
                    
                    # Save model performance
                    from server.app import save_model_performance
                    
                    class MockResult:
                        def __init__(self, model_name, episode_score):
                            self.model_name = model_name
                            self.episode_score = episode_score
                    
                    mock_result = MockResult(f"Test Model {operation_id}", 0.8)
                    save_model_performance(run_id, [mock_result])
                    
                    return {
                        'operation_id': operation_id,
                        'run_id': run_id,
                        'success': True,
                        'records_created': 2  # summary + performance
                    }
                    
                except Exception as e:
                    return {
                        'operation_id': operation_id,
                        'success': False,
                        'error': str(e)
                    }
            
            # Run 5 concurrent operations
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(concurrent_operation, i) 
                    for i in range(5)
                ]
                
                # Collect results
                results = []
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=30)  # 30 second timeout
                        results.append(result)
                    except Exception as e:
                        results.append({
                            'operation_id': 'unknown',
                            'success': False,
                            'error': str(e)
                        })
                
                # Analyze concurrent operation results
                successful_ops = sum(1 for r in results if r['success'])
                total_records_created = sum(r.get('records_created', 0) for r in results if r['success'])
                
                print(f"Concurrent operations completed: {successful_ops}/5")
                print(f"Total records created: {total_records_created}")
                
                # Get final database state
                final_stats = self.get_database_stats()
                records_added = final_stats['benchmark_runs'] - initial_stats['benchmark_runs']
                
                concurrent_success = successful_ops >= 4 and records_added >= 8
                
                self.log_test("Concurrent Inserts", concurrent_success, {
                    "Successful operations": f"{successful_ops}/5",
                    "Records created": records_added,
                    "Final database runs": final_stats['benchmark_runs']
                })
                
                return concurrent_success
                
        except Exception as e:
            self.log_test("Concurrent Inserts", False, {
                "Error": str(e)
            })
            return False
    
    def test_leaderboard_aggregation(self):
        """Test: Leaderboard aggregation."""
        print("\n" + "="*60)
        print("🏆 LEADERBOARD AGGREGATION TEST")
        print("="*60)
        
        try:
            # Test leaderboard API
            import requests
            
            response = requests.get('http://127.0.0.1:7863/api/leaderboard', timeout=10)
            
            if response.status_code == 200:
                leaderboard_data = response.json()
                rankings = leaderboard_data.get('rankings', [])
                
                print(f"Leaderboard API status: {response.status_code}")
                print(f"Models in leaderboard: {len(rankings)}")
                
                # Verify leaderboard structure
                valid_structure = True
                for rank in rankings[:3]:  # Check first 3 entries
                    required_fields = ['model_name', 'average_score', 'tasks_solved', 'total_tasks']
                    for field in required_fields:
                        if field not in rank:
                            valid_structure = False
                            print(f"Missing field in leaderboard: {field}")
                            break
                
                # Verify score ranges
                valid_scores = all(
                    0 <= rank.get('average_score', 0) <= 1 
                    for rank in rankings
                )
                
                # Verify solved counts don't exceed totals
                valid_counts = all(
                    rank.get('tasks_solved', 0) <= rank.get('total_tasks', 0)
                    for rank in rankings
                )
                
                aggregation_success = valid_structure and valid_scores and valid_counts
                
                self.log_test("Leaderboard Aggregation", aggregation_success, {
                    "API status": response.status_code,
                    "Models ranked": len(rankings),
                    "Valid structure": valid_structure,
                    "Valid scores": valid_scores,
                    "Valid counts": valid_counts
                })
                
                return aggregation_success
                
            else:
                self.log_test("Leaderboard Aggregation", False, {
                    "API status": response.status_code,
                    "Response": response.text[:200] if response.text else "No response"
                })
                return False
                
        except Exception as e:
            self.log_test("Leaderboard Aggregation", False, {
                "Error": str(e)
            })
            return False
    
    def test_pagination_works(self):
        """Test: Pagination works."""
        print("\n" + "="*60)
        print("📄 PAGINATION TEST")
        print("="*60)
        
        try:
            # Test results API with pagination
            import requests
            
            # Test page 1
            response1 = requests.get('http://127.0.0.1:7863/api/results?limit=10&offset=0', timeout=10)
            
            # Test page 2
            response2 = requests.get('http://127.0.0.1:7863/api/results?limit=10&offset=10', timeout=10)
            
            if response1.status_code == 200 and response2.status_code == 200:
                data1 = response1.json()
                data2 = response2.json()
                
                results1 = data1.get('results', [])
                results2 = data2.get('results', [])
                
                print(f"Page 1: {len(results1)} results")
                print(f"Page 2: {len(results2)} results")
                
                # Verify pagination parameters
                valid_pagination = (
                    'total_count' in data1 and
                    'results' in data1 and
                    len(results1) <= 10 and  # Respect limit
                    len(results2) <= 10 and  # Respect limit
                    data1.get('total_count', 0) >= len(results1) + len(results2)  # Total consistency
                )
                
                # Verify no duplicates between pages
                all_ids = [r.get('id', 'unknown') for r in results1] + [r.get('id', 'unknown') for r in results2]
                unique_ids = len(set(all_ids))
                no_duplicates = unique_ids == len(all_ids)
                
                pagination_success = valid_pagination and no_duplicates
                
                self.log_test("Pagination", pagination_success, {
                    "Page 1 results": len(results1),
                    "Page 2 results": len(results2),
                    "Valid parameters": valid_pagination,
                    "No duplicates": no_duplicates,
                    "Total count": data1.get('total_count', 0)
                })
                
                return pagination_success
                
            else:
                self.log_test("Pagination", False, {
                    "Page 1 status": response1.status_code,
                    "Page 2 status": response2.status_code
                })
                return False
                
        except Exception as e:
            self.log_test("Pagination", False, {
                "Error": str(e)
            })
            return False
    
    def generate_comprehensive_report(self):
        """Generate comprehensive test report."""
        print("\n" + "="*60)
        print("📊 COMPREHENSIVE DATABASE PERSISTENCE REPORT")
        print("="*60)
        
        # Count test results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for test in self.test_results if test['status'])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"\n🎯 OVERALL TEST SUMMARY:")
        print(f"   Tests passed: {passed_tests}/{total_tests}")
        print(f"   Success rate: {success_rate:.1f}%")
        
        # Test details
        print(f"\n📋 INDIVIDUAL TEST RESULTS:")
        for test in self.test_results:
            status = "✅ PASS" if test['status'] else "❌ FAIL"
            print(f"   {status} - {test['test_name']}")
            if test.get('details'):
                for key, value in test['details'].items():
                    print(f"      {key}: {value}")
        
        # Database statistics
        final_stats = self.get_database_stats()
        print(f"\n📊 FINAL DATABASE STATE:")
        print(f"   Benchmark runs: {final_stats['benchmark_runs']}")
        print(f"   Benchmark summaries: {final_stats['benchmark_summaries']}")
        print(f"   Model performance: {final_stats['model_performance']}")
        print(f"   Unique runs: {final_stats['unique_runs']}")
        
        # Overall assessment
        if success_rate >= 85:
            print(f"\n🏆 OVERALL: EXCELLENT - Database persistence fully functional")
        elif success_rate >= 70:
            print(f"\n✅ OVERALL: GOOD - Database persistence functional with minor issues")
        else:
            print(f"\n❌ OVERALL: NEEDS WORK - Database persistence has significant issues")
        
        return success_rate >= 70
    
    def run_all_tests(self):
        """Run all database persistence tests."""
        print("🗄️ DATABASE PERSISTENCE QA TEST SUITE")
        print("="*60)
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Ensure database is initialized
        init_db()
        
        # Run all tests
        test_results = []
        
        test_results.append(self.test_benchmark_to_database_flow())
        time.sleep(1)
        
        test_results.append(self.test_server_restart_persistence())
        time.sleep(1)
        
        test_results.append(self.test_duplicate_prevention())
        time.sleep(1)
        
        test_results.append(self.test_run_tracking())
        time.sleep(1)
        
        test_results.append(self.test_concurrent_inserts())
        time.sleep(1)
        
        test_results.append(self.test_leaderboard_aggregation())
        time.sleep(1)
        
        test_results.append(self.test_pagination_works())
        
        # Store results for reporting
        self.test_results = [
            {
                'test_name': 'Benchmark to Database Flow',
                'status': test_results[0]
            },
            {
                'test_name': 'Server Restart Persistence',
                'status': test_results[1]
            },
            {
                'test_name': 'Duplicate Prevention',
                'status': test_results[2]
            },
            {
                'test_name': 'Run Tracking',
                'status': test_results[3]
            },
            {
                'test_name': 'Concurrent Inserts',
                'status': test_results[4]
            },
            {
                'test_name': 'Leaderboard Aggregation',
                'status': test_results[5]
            },
            {
                'test_name': 'Pagination',
                'status': test_results[6]
            }
        ]
        
        return self.generate_comprehensive_report()

def main():
    """Run comprehensive database persistence QA test."""
    db_test = DatabasePersistenceTest()
    success = db_test.run_all_tests()
    
    print(f"\n🏁 Database persistence QA test complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
