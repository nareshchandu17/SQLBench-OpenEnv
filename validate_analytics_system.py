#!/usr/bin/env python3
"""
Analytics System Validation Test
Comprehensive testing of analytics data, trend detection, and insight generation
"""

import os
import sys
import requests
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analytics import AnalyticsEngine
from database import SessionLocal, init_db
from benchmark.models import ModelPerformance, BenchmarkSummary

class AnalyticsValidationTest:
    """Comprehensive analytics validation testing suite."""
    
    def __init__(self):
        self.test_results = []
        self.analytics_engine = None
        self.validation_data = {}
        
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
    
    def test_model_comparison_data_fetch(self):
        """Test: Fetch model comparison data."""
        print("\n" + "="*60)
        print("📊 MODEL COMPARISON DATA FETCH TEST")
        print("="*60)
        
        try:
            # Test via API
            response = requests.get('http://127.0.0.1:7863/api/analytics/model-comparison', timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate structure
                required_fields = ['timeseries', 'insights', 'summary']
                structure_valid = all(field in data for field in required_fields)
                
                # Validate timeseries data
                timeseries = data.get('timeseries', {})
                models_in_timeseries = list(timeseries.keys())
                data_points_per_model = {model: len(points) for model, points in timeseries.items()}
                
                # Validate insights
                insights = data.get('insights', [])
                insights_count = len(insights)
                
                # Validate summary
                summary = data.get('summary', {})
                total_models = summary.get('total_models', 0)
                total_runs = summary.get('total_runs', 0)
                
                print(f"✅ API response structure valid: {structure_valid}")
                print(f"✅ Models in timeseries: {models_in_timeseries}")
                print(f"✅ Data points per model: {data_points_per_model}")
                print(f"✅ Insights generated: {insights_count}")
                print(f"✅ Summary: {total_models} models, {total_runs} runs")
                
                # Store for further validation
                self.validation_data['api_response'] = data
                
                success = structure_valid and len(models_in_timeseries) > 0 and insights_count > 0
                
                self.log_test("Model Comparison Data Fetch", success, {
                    "API status": response.status_code,
                    "Structure valid": structure_valid,
                    "Models found": len(models_in_timeseries),
                    "Insights generated": insights_count,
                    "Total runs": total_runs
                })
                
                return success
                
            else:
                self.log_test("Model Comparison Data Fetch", False, {
                    "API status": response.status_code,
                    "Response": response.text[:200] if response.text else "No response"
                })
                return False
                
        except Exception as e:
            self.log_test("Model Comparison Data Fetch", False, {
                "Error": str(e)
            })
            return False
    
    def test_trend_detection_accuracy(self):
        """Test: Trends are correct (improving/declining)."""
        print("\n" + "="*60)
        print("📈 TREND DETECTION ACCURACY TEST")
        print("="*60)
        
        try:
            # Initialize analytics engine
            self.analytics_engine = AnalyticsEngine()
            
            # Get model comparison data
            comparison_data = self.analytics_engine.get_model_comparison_data()
            
            if not comparison_data:
                print("❌ No comparison data available")
                return False
            
            print(f"Models with data: {list(comparison_data.keys())}")
            
            # Test trend detection for each model
            trend_results = {}
            
            for model_name, data_points in comparison_data.items():
                if len(data_points) < 2:
                    print(f"⚠️  {model_name}: Insufficient data points ({len(data_points)})")
                    continue
                
                # Calculate trend manually
                scores = [point['score'] for point in data_points]
                if len(scores) >= 2:
                    manual_trend = "improving" if scores[-1] > scores[0] else "declining" if scores[-1] < scores[0] else "stable"
                    
                    # Get engine's trend detection
                    engine_trend = self.analytics_engine._detect_trend(data_points)
                    
                    trend_results[model_name] = {
                        'manual_trend': manual_trend,
                        'engine_trend': engine_trend,
                        'first_score': scores[0],
                        'last_score': scores[-1],
                        'data_points': len(data_points)
                    }
                    
                    print(f"📊 {model_name}:")
                    print(f"   Data points: {len(data_points)}")
                    print(f"   Score range: {scores[0]:.3f} → {scores[-1]:.3f}")
                    print(f"   Manual trend: {manual_trend}")
                    print(f"   Engine trend: {engine_trend}")
                    print(f"   Match: {'✅' if manual_trend == engine_trend else '❌'}")
            
            # Validate trend detection accuracy
            accurate_trends = sum(1 for result in trend_results.values() 
                                if result['manual_trend'] == result['engine_trend'])
            total_models_with_trends = len(trend_results)
            
            if total_models_with_trends > 0:
                accuracy = (accurate_trends / total_models_with_trends) * 100
                print(f"\n📈 Trend Detection Accuracy: {accuracy:.1f}% ({accurate_trends}/{total_models_with_trends})")
                
                success = accuracy >= 80  # 80% accuracy threshold
            else:
                print("⚠️  No models with sufficient data for trend analysis")
                success = True  # Not a failure if no data
            
            self.log_test("Trend Detection Accuracy", success, {
                "Models analyzed": total_models_with_trends,
                "Accurate trends": accurate_trends,
                "Accuracy": f"{accuracy:.1f}%" if total_models_with_trends > 0 else "N/A",
                "Trend results": trend_results
            })
            
            return success
            
        except Exception as e:
            self.log_test("Trend Detection Accuracy", False, {
                "Error": str(e)
            })
            return False
    
    def test_best_model_detection(self):
        """Test: Best model detection is accurate."""
        print("\n" + "="*60)
        print("🏆 BEST MODEL DETECTION TEST")
        print("="*60)
        
        try:
            if not self.analytics_engine:
                self.analytics_engine = AnalyticsEngine()
            
            # Get model comparison data
            comparison_data = self.analytics_engine.get_model_comparison_data()
            
            if not comparison_data:
                print("❌ No comparison data available")
                return False
            
            # Calculate best model manually
            model_averages = {}
            for model_name, data_points in comparison_data.items():
                if data_points:
                    scores = [point['score'] for point in data_points]
                    model_averages[model_name] = sum(scores) / len(scores)
            
            if not model_averages:
                print("❌ No model averages calculated")
                return False
            
            # Find manual best model
            manual_best = max(model_averages.items(), key=lambda x: x[1])
            
            # Get engine's best model detection
            engine_best = self.analytics_engine._get_best_model(comparison_data)
            
            print(f"📊 Model Performance Averages:")
            for model, avg_score in sorted(model_averages.items(), key=lambda x: x[1], reverse=True):
                print(f"   {model}: {avg_score:.3f}")
            
            print(f"\n🏆 Best Model Detection:")
            print(f"   Manual best: {manual_best[0]} ({manual_best[1]:.3f})")
            print(f"   Engine best: {engine_best}")
            
            if engine_best:
                engine_best_score = model_averages.get(engine_best, 0)
                print(f"   Engine best score: {engine_best_score:.3f}")
            
            # Validate accuracy
            detection_accurate = engine_best == manual_best[0]
            
            print(f"   Accuracy: {'✅ MATCH' if detection_accurate else '❌ MISMATCH'}")
            
            self.log_test("Best Model Detection", detection_accurate, {
                "Manual best model": manual_best[0],
                "Manual best score": f"{manual_best[1]:.3f}",
                "Engine best model": engine_best,
                "Detection accurate": detection_accurate,
                "All model averages": {k: f"{v:.3f}" for k, v in model_averages.items()}
            })
            
            return detection_accurate
            
        except Exception as e:
            self.log_test("Best Model Detection", False, {
                "Error": str(e)
            })
            return False
    
    def test_insights_not_hardcoded(self):
        """Test: Insights are NOT hardcoded."""
        print("\n" + "="*60)
        print("🧠 INSIGHTS NOT HARDCODED TEST")
        print("="*60)
        
        try:
            if not self.analytics_engine:
                self.analytics_engine = AnalyticsEngine()
            
            # Get comparison data
            comparison_data = self.analytics_engine.get_model_comparison_data()
            
            if not comparison_data:
                print("❌ No comparison data available")
                return False
            
            # Generate insights multiple times to check for consistency vs hardcoding
            insight_sets = []
            
            for i in range(3):
                insights = self.analytics_engine.generate_insights(comparison_data)
                insight_sets.append(insights)
                time.sleep(0.1)  # Small delay between generations
            
            print(f"Generated {len(insight_sets)} insight sets")
            
            # Check if insights are consistent (should be) but not obviously hardcoded
            first_set = insight_sets[0]
            
            # Check consistency
            all_consistent = all(set(insights) == set(first_set) for insights in insight_sets)
            
            print(f"Insight consistency: {'✅ CONSISTENT' if all_consistent else '❌ INCONSISTENT'}")
            
            # Check for obvious hardcoded patterns
            hardcoded_indicators = []
            
            for insights in insight_sets:
                for insight in insights:
                    # Check for obviously generic/static insights
                    if insight.lower() in ["data shows trends", "models perform differently", "scores vary"]:
                        hardcoded_indicators.append(insight)
                    elif len(insight) < 20:  # Too short to be meaningful
                        hardcoded_indicators.append(insight)
            
            print(f"Potential hardcoded insights: {len(hardcoded_indicators)}")
            for insight in hardcoded_indicators:
                print(f"   ⚠️  {insight}")
            
            # Analyze insight quality
            if first_set:
                avg_insight_length = sum(len(insight) for insight in first_set) / len(first_set)
                model_mentions = sum(1 for insight in first_set if any(model in insight for model in comparison_data.keys()))
                score_mentions = sum(1 for insight in first_set if any(word in insight.lower() for word in ['score', 'performance', 'improving', 'declining']))
                
                print(f"\n📊 Insight Quality Analysis:")
                print(f"   Number of insights: {len(first_set)}")
                print(f"   Average length: {avg_insight_length:.1f} characters")
                print(f"   Model-specific mentions: {model_mentions}/{len(first_set)}")
                print(f"   Performance-related mentions: {score_mentions}/{len(first_set)}")
                
                # Display sample insights
                print(f"\n🧠 Sample Insights:")
                for i, insight in enumerate(first_set[:3], 1):
                    print(f"   {i}. {insight}")
            
            # Determine if insights are dynamic and meaningful
            dynamic_insights = (
                len(first_set) > 0 and
                avg_insight_length > 30 and
                model_mentions > 0 and
                len(hardcoded_indicators) == 0
            )
            
            self.log_test("Insights Not Hardcoded", dynamic_insights, {
                "Insight sets generated": len(insight_sets),
                "Consistency": all_consistent,
                "Average insight length": f"{avg_insight_length:.1f}" if first_set else 0,
                "Model mentions": model_mentions if first_set else 0,
                "Hardcoded indicators": len(hardcoded_indicators),
                "Dynamic insights": dynamic_insights,
                "Sample insights": first_set[:2] if first_set else []
            })
            
            return dynamic_insights
            
        except Exception as e:
            self.log_test("Insights Not Hardcoded", False, {
                "Error": str(e)
            })
            return False
    
    def test_different_run_scenarios(self):
        """Test: Different run scenarios."""
        print("\n" + "="*60)
        print("🎭 DIFFERENT RUN SCENARIOS TEST")
        print("="*60)
        
        try:
            if not self.analytics_engine:
                self.analytics_engine = AnalyticsEngine()
            
            # Test different data scenarios
            scenarios = [
                ("Full dataset", None),  # Use all available data
                ("Recent runs only", lambda data: self._filter_recent_runs(data, 3)),  # Last 3 runs
                ("Single model", lambda data: {k: v for k, v in data.items() if "Gemma" in k or "gemma" in k.lower()}),  # Single model
            ]
            
            scenario_results = {}
            
            for scenario_name, filter_func in scenarios:
                print(f"\n📊 Testing scenario: {scenario_name}")
                
                # Get comparison data
                comparison_data = self.analytics_engine.get_model_comparison_data()
                
                # Apply filter if provided
                if filter_func:
                    filtered_data = filter_func(comparison_data)
                else:
                    filtered_data = comparison_data
                
                if not filtered_data:
                    print(f"   ⚠️  No data after filtering")
                    scenario_results[scenario_name] = {"success": False, "reason": "No data"}
                    continue
                
                # Generate insights for this scenario
                insights = self.analytics_engine.generate_insights(filtered_data)
                
                # Get best model for this scenario
                best_model = self.analytics_engine._get_best_model(filtered_data)
                
                # Calculate summary stats
                total_models = len(filtered_data)
                total_data_points = sum(len(points) for points in filtered_data.values())
                
                print(f"   Models: {total_models}")
                print(f"   Data points: {total_data_points}")
                print(f"   Insights: {len(insights)}")
                print(f"   Best model: {best_model}")
                
                if insights:
                    print(f"   Sample insight: {insights[0][:100]}...")
                
                scenario_results[scenario_name] = {
                    "success": True,
                    "models": total_models,
                    "data_points": total_data_points,
                    "insights": len(insights),
                    "best_model": best_model
                }
            
            # Validate scenario handling
            successful_scenarios = sum(1 for result in scenario_results.values() if result["success"])
            total_scenarios = len(scenarios)
            
            print(f"\n📊 Scenario Test Results:")
            for scenario, result in scenario_results.items():
                status = "✅ SUCCESS" if result["success"] else "❌ FAILED"
                print(f"   {status} - {scenario}")
                if result["success"]:
                    print(f"      Models: {result['models']}, Insights: {result['insights']}")
                else:
                    print(f"      Reason: {result.get('reason', 'Unknown')}")
            
            success_rate = (successful_scenarios / total_scenarios) * 100 if total_scenarios > 0 else 0
            success = success_rate >= 80  # 80% of scenarios should work
            
            self.log_test("Different Run Scenarios", success, {
                "Successful scenarios": f"{successful_scenarios}/{total_scenarios}",
                "Success rate": f"{success_rate:.1f}%",
                "Scenario results": scenario_results
            })
            
            return success
            
        except Exception as e:
            self.log_test("Different Run Scenarios", False, {
                "Error": str(e)
            })
            return False
    
    def test_missing_data_handling(self):
        """Test: Missing data handling."""
        print("\n" + "="*60)
        print("🔍 MISSING DATA HANDLING TEST")
        print("="*60)
        
        try:
            if not self.analytics_engine:
                self.analytics_engine = AnalyticsEngine()
            
            # Test scenarios with missing data
            missing_data_scenarios = [
                ("Empty data", {}),
                ("Single model", {"Test Model": [{"score": 0.8, "run_id": "run_1", "timestamp": "2024-01-01"}]}),
                ("Model with single data point", {"Model A": [{"score": 0.7, "run_id": "run_1", "timestamp": "2024-01-01"}], "Model B": []}),
                ("Models with missing timestamps", {"Model A": [{"score": 0.8, "run_id": "run_1"}], "Model B": [{"score": 0.6, "run_id": "run_2", "timestamp": "2024-01-01"}]}),
            ]
            
            missing_data_results = {}
            
            for scenario_name, test_data in missing_data_scenarios:
                print(f"\n📊 Testing missing data scenario: {scenario_name}")
                
                try:
                    # Generate insights
                    insights = self.analytics_engine.generate_insights(test_data)
                    
                    # Get best model
                    best_model = self.analytics_engine._get_best_model(test_data)
                    
                    print(f"   Insights generated: {len(insights)}")
                    print(f"   Best model detected: {best_model}")
                    
                    # Check for graceful handling
                    graceful_handling = True
                    if not test_data and len(insights) > 0:
                        print("   ⚠️  Insights generated for empty data")
                        graceful_handling = False
                    
                    if test_data and best_model and best_model not in test_data:
                        print("   ⚠️  Best model not in test data")
                        graceful_handling = False
                    
                    status = "✅ HANDLED" if graceful_handling else "❌ ISSUE"
                    print(f"   {status}")
                    
                    missing_data_results[scenario_name] = {
                        "success": graceful_handling,
                        "insights": len(insights),
                        "best_model": best_model
                    }
                    
                except Exception as e:
                    print(f"   ❌ EXCEPTION: {str(e)}")
                    missing_data_results[scenario_name] = {
                        "success": False,
                        "error": str(e)
                    }
            
            # Validate missing data handling
            successful_scenarios = sum(1 for result in missing_data_results.values() if result.get("success", False))
            total_scenarios = len(missing_data_scenarios)
            
            print(f"\n📊 Missing Data Test Results:")
            for scenario, result in missing_data_results.items():
                status = "✅ HANDLED" if result.get("success", False) else "❌ ISSUE"
                print(f"   {status} - {scenario}")
                if result.get("error"):
                    print(f"      Error: {result['error']}")
            
            success_rate = (successful_scenarios / total_scenarios) * 100 if total_scenarios > 0 else 0
            success = success_rate >= 75  # 75% of missing data scenarios should be handled gracefully
            
            self.log_test("Missing Data Handling", success, {
                "Successful scenarios": f"{successful_scenarios}/{total_scenarios}",
                "Success rate": f"{success_rate:.1f}%",
                "Scenario results": missing_data_results
            })
            
            return success
            
        except Exception as e:
            self.log_test("Missing Data Handling", False, {
                "Error": str(e)
            })
            return False
    
    def test_graph_data_matches_db(self):
        """Test: Graph data matches database."""
        print("\n" + "="*60)
        print("📊 GRAPH DATA MATCHES DB TEST")
        print("="*60)
        
        try:
            # Get data from API (graph data)
            api_response = requests.get('http://127.0.0.1:7863/api/analytics/model-comparison', timeout=10)
            
            if api_response.status_code != 200:
                print(f"❌ API request failed: {api_response.status_code}")
                return False
            
            api_data = api_response.json()
            api_timeseries = api_data.get('timeseries', {})
            
            # Get data directly from database
            db = SessionLocal()
            try:
                # Get model performance data
                db_performances = db.query(ModelPerformance).all()
                
                # Organize by model
                db_data = defaultdict(list)
                for perf in db_performances:
                    db_data[perf.model_name].append({
                        'score': perf.average_score,
                        'run_id': perf.run_id,
                        'timestamp': perf.created_at.isoformat() if perf.created_at else None
                    })
                
                db.close()
                
                print(f"📊 Data Comparison:")
                print(f"   API models: {len(api_timeseries)}")
                print(f"   DB models: {len(db_data)}")
                
                # Compare data consistency
                consistency_issues = []
                
                for model_name in api_timeseries:
                    api_points = api_timeseries[model_name]
                    db_points = db_data.get(model_name, [])
                    
                    if len(api_points) != len(db_points):
                        consistency_issues.append(f"{model_name}: API {len(api_points)} vs DB {len(db_points)} points")
                    
                    # Check if scores match approximately
                    if api_points and db_points:
                        api_scores = [p['score'] for p in api_points]
                        db_scores = [p['score'] for p in db_points]
                        
                        if len(api_scores) == len(db_scores):
                            for i, (api_score, db_score) in enumerate(zip(api_scores, db_scores)):
                                if abs(api_score - db_score) > 0.001:  # Small tolerance for floating point
                                    consistency_issues.append(f"{model_name} point {i}: API {api_score} vs DB {db_score}")
                
                # Check for models in DB but not in API
                db_only_models = set(db_data.keys()) - set(api_timeseries.keys())
                if db_only_models:
                    consistency_issues.append(f"Models only in DB: {list(db_only_models)}")
                
                # Check for models in API but not in DB
                api_only_models = set(api_timeseries.keys()) - set(db_data.keys())
                if api_only_models:
                    consistency_issues.append(f"Models only in API: {list(api_only_models)}")
                
                print(f"\n🔍 Consistency Check:")
                if consistency_issues:
                    print(f"   ⚠️  Issues found: {len(consistency_issues)}")
                    for issue in consistency_issues[:5]:  # Show first 5 issues
                        print(f"      - {issue}")
                    if len(consistency_issues) > 5:
                        print(f"      ... and {len(consistency_issues) - 5} more")
                else:
                    print(f"   ✅ No consistency issues found")
                
                # Overall consistency assessment
                total_models = len(api_timeseries) + len(db_data)
                issue_rate = (len(consistency_issues) / total_models) * 100 if total_models > 0 else 0
                
                consistent = issue_rate <= 10  # Allow up to 10% issues due to timing differences
                
                self.log_test("Graph Data Matches DB", consistent, {
                    "API models": len(api_timeseries),
                    "DB models": len(db_data),
                    "Consistency issues": len(consistency_issues),
                    "Issue rate": f"{issue_rate:.1f}%",
                    "Sample issues": consistency_issues[:3]
                })
                
                return consistent
                
            except Exception as e:
                db.close()
                print(f"❌ Database query failed: {e}")
                return False
                
        except Exception as e:
            self.log_test("Graph Data Matches DB", False, {
                "Error": str(e)
            })
            return False
    
    def test_insights_meaningfulness(self):
        """Test: Insights are meaningful."""
        print("\n" + "="*60)
        print("🧠 INSIGHTS MEANINGFULNESS TEST")
        print("="*60)
        
        try:
            # Get insights from API
            response = requests.get('http://127.0.0.1:7863/api/analytics/model-comparison', timeout=10)
            
            if response.status_code != 200:
                print(f"❌ API request failed: {response.status_code}")
                return False
            
            data = response.json()
            insights = data.get('insights', [])
            
            if not insights:
                print("❌ No insights generated")
                return False
            
            print(f"🧠 Analyzing {len(insights)} insights for meaningfulness...")
            
            # Analyze insight quality
            quality_metrics = {
                'total_insights': len(insights),
                'avg_length': 0,
                'model_specific': 0,
                'performance_related': 0,
                'trend_related': 0,
                'numeric_values': 0,
                'actionable': 0
            }
            
            model_names = ['llama', 'gemma', 'dolphin', 'mistral']
            performance_words = ['score', 'performance', 'improving', 'declining', 'better', 'worse', 'trend']
            trend_words = ['trend', 'improving', 'declining', 'increasing', 'decreasing']
            
            for insight in insights:
                # Length
                quality_metrics['avg_length'] += len(insight)
                
                # Model specificity
                if any(model in insight.lower() for model in model_names):
                    quality_metrics['model_specific'] += 1
                
                # Performance related
                if any(word in insight.lower() for word in performance_words):
                    quality_metrics['performance_related'] += 1
                
                # Trend related
                if any(word in insight.lower() for word in trend_words):
                    quality_metrics['trend_related'] += 1
                
                # Numeric values
                import re
                if re.search(r'\d+\.\d+', insight):  # Decimal numbers
                    quality_metrics['numeric_values'] += 1
                
                # Actionable insights
                actionable_words = ['should', 'recommend', 'consider', 'best', 'avoid', 'focus']
                if any(word in insight.lower() for word in actionable_words):
                    quality_metrics['actionable'] += 1
            
            # Calculate averages
            if quality_metrics['total_insights'] > 0:
                quality_metrics['avg_length'] = quality_metrics['avg_length'] / quality_metrics['total_insights']
            
            # Display insights
            print(f"\n📊 Insight Quality Metrics:")
            print(f"   Total insights: {quality_metrics['total_insights']}")
            print(f"   Average length: {quality_metrics['avg_length']:.1f} characters")
            print(f"   Model-specific: {quality_metrics['model_specific']}/{quality_metrics['total_insights']}")
            print(f"   Performance-related: {quality_metrics['performance_related']}/{quality_metrics['total_insights']}")
            print(f"   Trend-related: {quality_metrics['trend_related']}/{quality_metrics['total_insights']}")
            print(f"   Contains numbers: {quality_metrics['numeric_values']}/{quality_metrics['total_insights']}")
            print(f"   Actionable: {quality_metrics['actionable']}/{quality_metrics['total_insights']}")
            
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
            if quality_metrics['numeric_values'] > 0:
                meaningfulness_score += 1
            
            meaningful = meaningfulness_score >= 3  # At least 3 of 4 criteria
            
            print(f"\n🎯 Meaningfulness Assessment:")
            print(f"   Score: {meaningfulness_score}/4")
            print(f"   Meaningful: {'✅ YES' if meaningful else '❌ NO'}")
            
            self.log_test("Insights Meaningfulness", meaningful, {
                "Total insights": quality_metrics['total_insights'],
                "Average length": f"{quality_metrics['avg_length']:.1f}",
                "Model-specific ratio": f"{quality_metrics['model_specific']}/{quality_metrics['total_insights']}",
                "Performance-related ratio": f"{quality_metrics['performance_related']}/{quality_metrics['total_insights']}",
                "Meaningfulness score": f"{meaningfulness_score}/4",
                "Sample insights": insights[:2]
            })
            
            return meaningful
            
        except Exception as e:
            self.log_test("Insights Meaningfulness", False, {
                "Error": str(e)
            })
            return False
    
    def _filter_recent_runs(self, data, max_runs):
        """Filter data to include only recent runs."""
        filtered_data = {}
        
        for model_name, data_points in data.items():
            # Sort by timestamp and take most recent
            sorted_points = sorted(data_points, key=lambda x: x.get('timestamp', ''), reverse=True)
            filtered_data[model_name] = sorted_points[:max_runs]
        
        return filtered_data
    
    def generate_validation_report(self):
        """Generate comprehensive validation report."""
        print("\n" + "="*60)
        print("📊 ANALYTICS SYSTEM VALIDATION REPORT")
        print("="*60)
        
        # Count test results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for test in self.test_results if test['status'])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"\n🎯 OVERALL VALIDATION SUMMARY:")
        print(f"   Tests passed: {passed_tests}/{total_tests}")
        print(f"   Success rate: {success_rate:.1f}%")
        
        # Test details
        print(f"\n📋 INDIVIDUAL TEST RESULTS:")
        for test in self.test_results:
            status = "✅ PASS" if test['status'] else "❌ FAIL"
            print(f"   {status} - {test['test_name']}")
            if test.get('details'):
                for key, value in test['details'].items():
                    if isinstance(value, (list, dict)):
                        print(f"      {key}: {len(value)} items")
                    else:
                        print(f"      {key}: {value}")
        
        # Overall assessment
        if success_rate >= 90:
            print(f"\n🏆 OVERALL: EXCELLENT - Analytics system fully functional")
        elif success_rate >= 75:
            print(f"\n✅ OVERALL: GOOD - Analytics system functional with minor issues")
        else:
            print(f"\n❌ OVERALL: NEEDS WORK - Analytics system has significant issues")
        
        return success_rate >= 75
    
    def run_all_tests(self):
        """Run all analytics validation tests."""
        print("🧪 ANALYTICS SYSTEM VALIDATION TEST SUITE")
        print("="*60)
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all tests
        test_results = []
        
        test_results.append(self.test_model_comparison_data_fetch())
        time.sleep(1)
        
        test_results.append(self.test_trend_detection_accuracy())
        time.sleep(1)
        
        test_results.append(self.test_best_model_detection())
        time.sleep(1)
        
        test_results.append(self.test_insights_not_hardcoded())
        time.sleep(1)
        
        test_results.append(self.test_different_run_scenarios())
        time.sleep(1)
        
        test_results.append(self.test_missing_data_handling())
        time.sleep(1)
        
        test_results.append(self.test_graph_data_matches_db())
        time.sleep(1)
        
        test_results.append(self.test_insights_meaningfulness())
        
        # Store results for reporting
        self.test_results = [
            {
                'test_name': 'Model Comparison Data Fetch',
                'status': test_results[0]
            },
            {
                'test_name': 'Trend Detection Accuracy',
                'status': test_results[1]
            },
            {
                'test_name': 'Best Model Detection',
                'status': test_results[2]
            },
            {
                'test_name': 'Insights Not Hardcoded',
                'status': test_results[3]
            },
            {
                'test_name': 'Different Run Scenarios',
                'status': test_results[4]
            },
            {
                'test_name': 'Missing Data Handling',
                'status': test_results[5]
            },
            {
                'test_name': 'Graph Data Matches DB',
                'status': test_results[6]
            },
            {
                'test_name': 'Insights Meaningfulness',
                'status': test_results[7]
            }
        ]
        
        return self.generate_validation_report()

def main():
    """Run comprehensive analytics validation test."""
    analytics_test = AnalyticsValidationTest()
    success = analytics_test.run_all_tests()
    
    print(f"\n🏁 Analytics validation test complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
