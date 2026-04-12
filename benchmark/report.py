"""
benchmark/report.py

Generates model failure analysis and insights from benchmark results.
Transforms raw error taxonomy into actionable research insights.

This report helps model developers understand where their models struggle,
turning the benchmark into a research evaluation platform.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple


def load_taxonomy() -> Dict[str, Any]:
    """Load error taxonomy JSON with safety fallback."""
    taxonomy_path = Path(__file__).parent.parent / "benchmark_output" / "error_taxonomy.json"
    
    if not taxonomy_path.exists():
        return None
    
    try:
        with open(taxonomy_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading taxonomy: {e}")
        return None


def load_leaderboard() -> Dict[str, Any]:
    """Load leaderboard JSON for score integration."""
    leaderboard_path = Path(__file__).parent.parent / "benchmark_output" / "leaderboard.json"
    
    if not leaderboard_path.exists():
        return None
    
    try:
        with open(leaderboard_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def get_model_score(model_id: str, leaderboard: Dict) -> float:
    """Extract average score for a model from leaderboard."""
    if not leaderboard:
        return 0.0
    
    for entry in leaderboard.get("rankings", []):
        if entry.get("model_id") == model_id:
            return entry.get("average_score", 0.0)
    
    return 0.0


def analyze_error_pattern(errors: Dict[str, float]) -> Tuple[str, str]:
    """
    Identify dominant weakness and a brief insight.
    Returns (weakness_type, insight)
    """
    # Filter out success and low-value errors
    relevant = {k: v for k, v in errors.items() 
                if k != "success" and v > 0.0}
    
    if not relevant:
        return ("none", "Model performs well — no systematic failures detected")
    
    # Find dominant error
    dominant = max(relevant, key=relevant.get)
    percentage = relevant[dominant] * 100
    
    insights = {
        "syntax_error": f"Model struggles with SQL syntax (e.g., missing commas, invalid keywords). {percentage:.0f}% of failures are syntax-related.",
        "reference_error": f"Model frequently references non-existent tables/columns. This suggests poor schema understanding. {percentage:.0f}% of failures.",
        "join_error": f"Model has difficulty with JOIN operations ({percentage:.0f}% of failures). May struggle with multi-table queries or join conditions.",
        "aggregation_error": f"Model struggles with GROUP BY and aggregate functions ({percentage:.0f}% of failures). Complex aggregations may be problematic.",
        "logic_error": f"Model produces structurally valid but semantically incorrect queries ({percentage:.0f}% of failures). Needs better semantic understanding.",
        "ordering_error": f"Model struggles with ORDER BY clauses ({percentage:.0f}% of failures). May not understand result ordering requirements.",
    }
    
    return (dominant, insights.get(dominant, f"Primary failure mode: {dominant}"))


def get_comparative_strength(errors: Dict[str, float]) -> str:
    """Identify what this model does better than others."""
    best_category = max(errors, key=lambda k: errors[k] if k != "success" else -1)
    
    if best_category == "success":
        success_rate = errors.get("success", 0.0)
        if success_rate > 0.5:
            return "Strong success rate"
        elif success_rate > 0.1:
            return "Moderate success performance"
    
    return "Consistent attempt rate"


def generate_model_report(model_id: str, model_data: Dict, score: float) -> str:
    """Generate detailed report for a single model."""
    model_name = model_data.get("model_name", model_id)
    error_rates = model_data.get("error_rates", {})
    total_attempts = model_data.get("total_attempts", 0)
    
    # Analyze error patterns
    dominant_error, insight = analyze_error_pattern(error_rates)
    strength = get_comparative_strength(error_rates)
    
    # Build report
    lines = [
        f"\n{'='*70}",
        f"Model: {model_name}",
        f"{'='*70}",
        f"Leaderboard Score:     {score:.3f}",
        f"Total Attempts:        {total_attempts}",
        f"Primary Weakness:      {dominant_error}",
        f"",
        "Error Distribution:",
        "─" * 70,
    ]
    
    # Show all error categories with visual bar
    for category in ["syntax_error", "reference_error", "join_error", 
                     "aggregation_error", "logic_error", "ordering_error", "success"]:
        rate = error_rates.get(category, 0.0)
        percentage = rate * 100
        bar_length = int(percentage / 5)  # 5% per character
        bar = "█" * bar_length + "░" * (20 - bar_length)
        lines.append(f"{category:20} {bar} {percentage:5.1f}%")
    
    # Add insights
    lines.extend([
        "",
        "Insight:",
        "─" * 70,
        insight,
        "",
        "Recommendations:",
        "─" * 70,
    ])
    
    # Generate recommendations based on failure modes
    recommendations = []
    if error_rates.get("syntax_error", 0) > 0.1:
        recommendations.append("• Improve SQL syntax validation and error recovery")
    if error_rates.get("reference_error", 0) > 0.1:
        recommendations.append("• Better schema understanding — provide clearer table/column information")
    if error_rates.get("join_error", 0) > 0.2:
        recommendations.append("• Add more JOIN examples to training data")
    if error_rates.get("aggregation_error", 0) > 0.15:
        recommendations.append("• Enhance GROUP BY and aggregate function understanding")
    if error_rates.get("logic_error", 0) > 0.3:
        recommendations.append("• Focus on semantic SQL correctness beyond syntax")
    if error_rates.get("success", 0) > 0.5:
        recommendations.append("• This model shows promise — consider using as baseline")
    
    if not recommendations:
        recommendations.append("• Model performs consistently — monitor for edge cases")
    
    lines.extend(recommendations)
    
    return "\n".join(lines)


def generate_comparative_analysis(taxonomy: Dict) -> str:
    """Generate cross-model comparative analysis."""
    models = taxonomy.get("models", {})
    leaderboard = load_leaderboard()
    
    if not models:
        return ""
    
    lines = [
        f"\n{'='*70}",
        "CROSS-MODEL COMPARATIVE ANALYSIS",
        f"{'='*70}",
        "",
    ]
    
    # Failure mode frequencies across all models
    failure_counts = {
        "syntax_error": 0,
        "reference_error": 0,
        "join_error": 0,
        "aggregation_error": 0,
        "logic_error": 0,
        "ordering_error": 0,
    }
    
    total_models = 0
    for model_id, model_data in models.items():
        total_models += 1
        error_rates = model_data.get("error_rates", {})
        for error_type in failure_counts:
            if error_rates.get(error_type, 0) > 0.1:  # 10% threshold
                failure_counts[error_type] += 1
    
    if total_models > 0:
        lines.append("Most Common Failure Modes (% of models affected):")
        lines.append("─" * 70)
        
        sorted_failures = sorted(failure_counts.items(), 
                                key=lambda x: x[1], reverse=True)
        for error_type, count in sorted_failures:
            if count > 0:
                percentage = (count / total_models) * 100
                lines.append(f"{error_type:25} {percentage:5.1f}% of models struggle here")
    
    # Overall trend
    lines.append("")
    lines.append("Industry Insight:")
    lines.append("─" * 70)
    
    if failure_counts["join_error"] > total_models * 0.5:
        lines.append("• JOINs are a systematic weakness across all tested models")
    if failure_counts["aggregation_error"] > total_models * 0.5:
        lines.append("• Aggregation is challenging for language models")
    if failure_counts["logic_error"] > total_models * 0.7:
        lines.append("• Semantic SQL understanding needs improvement across the board")
    
    lines.append("")
    lines.append("Recommendation for Deployment:")
    lines.append("─" * 70)
    lines.append("• Deploy queries with high JOIN/aggregation count with extra validation")
    lines.append("• Consider ensemble approach combining models with complementary strengths")
    lines.append("")
    
    return "\n".join(lines)


def save_report(report_content: str) -> None:
    """Save report to file."""
    report_path = Path(__file__).parent.parent / "benchmark_output" / "model_analysis_report.txt"
    
    Path(report_path).parent.mkdir(exist_ok=True)
    
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"✓ Report saved to: {report_path}")
    except IOError as e:
        print(f"Warning: Could not save report: {e}")


def main():
    """Generate and display model analysis report."""
    taxonomy = load_taxonomy()
    leaderboard = load_leaderboard()
    
    if not taxonomy:
        print("Error: Could not load error_taxonomy.json")
        print("Run: python run_benchmark.py")
        return
    
    # Build full report
    report_lines = [
        "╔" + "═" * 68 + "╗",
        "║" + " " * 15 + "MODEL ERROR ANALYSIS REPORT" + " " * 25 + "║",
        "╚" + "═" * 68 + "╝",
        "",
        "This report analyzes SQL query error patterns to help model developers",
        "understand strengths, weaknesses, and areas for improvement.",
        "",
        f"Benchmark: {taxonomy.get('benchmark', 'Unknown')}",
        f"Timestamp: {taxonomy.get('timestamp', 'Unknown')}",
        "",
    ]
    
    # Per-model analysis
    models = taxonomy.get("models", {})
    for model_id in sorted(models.keys()):
        model_data = models[model_id]
        score = get_model_score(model_id, leaderboard)
        model_report = generate_model_report(model_id, model_data, score)
        report_lines.append(model_report)
    
    # Comparative analysis
    comparative = generate_comparative_analysis(taxonomy)
    if comparative:
        report_lines.append(comparative)
    
    # Footer
    report_lines.extend([
        f"{'='*70}",
        "End of Report",
        "",
    ])
    
    full_report = "\n".join(report_lines)
    
    # Display report
    print(full_report)
    
    # Save to file
    save_report(full_report)


if __name__ == "__main__":
    main()
