#!/usr/bin/env python3
"""
Optimization Performance Dashboard
Comprehensive view of optimization performance data including:
- Phase-by-phase metrics comparison
- Parameter evolution tracking
- Performance visualization
- Trade-level analysis
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class OptimizationDashboard:
    """Comprehensive optimization performance dashboard."""

    def __init__(self, results_dir: str = "results"):
        self.results_dir = Path(results_dir)

    def load_all_phase_data(self) -> dict[str, Any]:
        """Load data from all optimization phases."""
        phases = {
            "phase1": "phase1_random",
            "phase2": "phase2_random",
            "phase3": "phase3_bayesian",
        }

        data = {}
        for phase_key, phase_dir in phases.items():
            phase_path = self.results_dir / phase_dir
            if phase_path.exists():
                data[phase_key] = self.load_phase_data(phase_path)
            else:
                print(f"⚠️ Phase directory not found: {phase_path}")
                data[phase_key] = {}

        return data

    def load_phase_data(self, phase_path: Path) -> dict[str, Any]:
        """Load all data from a specific phase directory."""
        phase_data = {}

        # Load different types of files
        file_types = {
            "study": "*study*.json",
            "results": "*result*.json",
            "validation": "*validation*.json",
            "metrics": "*metrics*.json",
            "trades": "*trades*.json",
        }

        for data_type, pattern in file_types.items():
            files = list(phase_path.glob(pattern))
            if files:
                try:
                    with open(files[0]) as f:
                        phase_data[data_type] = json.load(f)
                except Exception as e:
                    print(f"⚠️ Failed to load {data_type} from {files[0]}: {e}")

        return phase_data

    def create_performance_summary(self, phase_data: dict[str, Any]) -> pd.DataFrame:
        """Create comprehensive performance summary across phases."""

        summary_rows = []

        for phase_name, data in phase_data.items():
            if not data:
                continue

            row = {
                "Phase": phase_name,
                "Method": "Random" if "random" in phase_name else "Bayesian",
            }

            # Extract study metrics
            if "study" in data:
                study = data["study"]
                row["Best_Score"] = study.get("best_value", "N/A")

                if "trials" in study:
                    trials = study["trials"]
                    row["Total_Trials"] = len(trials)
                    row["Completed_Trials"] = len(
                        [t for t in trials if t.get("state") == "COMPLETE"]
                    )
                    row["Failed_Trials"] = len(
                        [t for t in trials if t.get("state") == "FAIL"]
                    )
                    row["Pruned_Trials"] = len(
                        [t for t in trials if t.get("state") == "PRUNED"]
                    )

                    # Calculate success rate
                    if row["Total_Trials"] > 0:
                        row["Success_Rate"] = (
                            row["Completed_Trials"] / row["Total_Trials"]
                        )

            # Extract trading metrics
            metrics_sources = ["results", "validation", "metrics"]
            for source in metrics_sources:
                if source in data:
                    source_data = data[source]

                    # Look for metrics in different places
                    metrics_dict = {}
                    if "metrics" in source_data:
                        metrics_dict = source_data["metrics"]
                    elif "validation_metrics" in source_data:
                        metrics_dict = source_data["validation_metrics"]
                    else:
                        metrics_dict = source_data

                    # Extract key trading metrics
                    trading_metrics = {
                        "Total_PnL": "total_pnl",
                        "Sharpe_Ratio": "sharpe_ratio",
                        "Win_Rate": "win_rate",
                        "Total_Trades": "total_trades",
                        "Max_Drawdown": "max_drawdown",
                        "Profit_Factor": "profit_factor",
                        "Avg_Trade_PnL": "avg_trade_pnl",
                    }

                    for display_name, metric_key in trading_metrics.items():
                        if metric_key in metrics_dict:
                            row[display_name] = metrics_dict[metric_key]
                        # Also try with _mean suffix for aggregated metrics
                        elif f"{metric_key}_mean" in metrics_dict:
                            row[display_name] = metrics_dict[f"{metric_key}_mean"]

            summary_rows.append(row)

        return pd.DataFrame(summary_rows)

    def analyze_parameter_evolution(self, phase_data: dict[str, Any]) -> pd.DataFrame:
        """Analyze how parameters evolved across phases."""

        param_rows = []

        for phase_name, data in phase_data.items():
            if not data or "study" not in data:
                continue

            study = data["study"]
            if "best_params" in study:
                params = study["best_params"]

                row = {"Phase": phase_name}
                row.update(params)
                param_rows.append(row)

        return pd.DataFrame(param_rows)

    def calculate_optimization_efficiency(
        self, phase_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Calculate optimization efficiency metrics."""

        efficiency = {}

        total_trials = 0
        total_time = 0
        best_scores = []

        for _phase_name, data in phase_data.items():
            if not data:
                continue

            phase_trials = 0
            if "study" in data and "trials" in data["study"]:
                phase_trials = len(data["study"]["trials"])
                total_trials += phase_trials

            if "study" in data and "best_value" in data["study"]:
                best_scores.append(data["study"]["best_value"])

        efficiency["total_trials"] = total_trials
        efficiency["total_time_estimated"] = total_time

        if len(best_scores) >= 2:
            efficiency["total_improvement"] = best_scores[-1] - best_scores[0]
            efficiency["improvement_per_trial"] = (
                efficiency["total_improvement"] / total_trials
                if total_trials > 0
                else 0
            )

            # Calculate convergence rate
            improvements = [
                best_scores[i] - best_scores[i - 1] for i in range(1, len(best_scores))
            ]
            efficiency["convergence_rate"] = (
                np.mean(improvements) if improvements else 0
            )

        return efficiency

    def generate_dashboard_report(self, output_file: str = "optimization_dashboard.md"):
        """Generate comprehensive dashboard report."""

        print("📊 Generating Optimization Performance Dashboard...")
        print("=" * 60)

        # Load all data
        phase_data = self.load_all_phase_data()

        # Create performance summary
        summary_df = self.create_performance_summary(phase_data)
        param_evolution_df = self.analyze_parameter_evolution(phase_data)
        efficiency_metrics = self.calculate_optimization_efficiency(phase_data)

        # Generate report
        report_lines = [
            "# 🚀 Optimization Performance Dashboard",
            f"**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 📊 Executive Summary",
            "",
        ]

        # Key metrics summary
        if not summary_df.empty:
            best_phase = (
                summary_df.loc[summary_df["Best_Score"].idxmax()]
                if "Best_Score" in summary_df.columns
                else None
            )
            if best_phase is not None:
                report_lines.extend(
                    [
                        f"- **Best Performing Phase:** {best_phase['Phase']} (Score: {best_phase['Best_Score']:.6f})",
                        f"- **Total Trials Completed:** {efficiency_metrics.get('total_trials', 'N/A')}",
                        f"- **Overall Improvement:** {efficiency_metrics.get('total_improvement', 'N/A'):.6f}",
                        f"- **Improvement per Trial:** {efficiency_metrics.get('improvement_per_trial', 'N/A'):.8f}",
                        "",
                    ]
                )

        # Performance by phase
        if not summary_df.empty:
            report_lines.extend(
                [
                    "## 📈 Performance by Phase",
                    "",
                    summary_df.to_string(index=False),
                    "",
                    "### Key Insights:",
                    "",
                ]
            )

            # Generate insights
            if "Best_Score" in summary_df.columns:
                scores = summary_df["Best_Score"].dropna()
                if len(scores) >= 2:
                    total_improvement = scores.iloc[-1] - scores.iloc[0]
                    report_lines.append(
                        f"- Total score improvement: {total_improvement:+.6f}"
                    )

                    for i in range(1, len(scores)):
                        phase_improvement = scores.iloc[i] - scores.iloc[i - 1]
                        phase_name = summary_df.iloc[i]["Phase"]
                        report_lines.append(
                            f"- {phase_name} improvement: {phase_improvement:+.6f}"
                        )

            # Success rate analysis
            if "Success_Rate" in summary_df.columns:
                avg_success_rate = summary_df["Success_Rate"].mean()
                report_lines.append(f"- Average success rate: {avg_success_rate:.1%}")

            report_lines.append("")

        # Parameter evolution
        if not param_evolution_df.empty:
            report_lines.extend(
                [
                    "## 🔧 Parameter Evolution",
                    "",
                    param_evolution_df.to_string(index=False),
                    "",
                    "### Parameter Insights:",
                    "",
                ]
            )

            # Analyze parameter changes
            numeric_columns = param_evolution_df.select_dtypes(
                include=[np.number]
            ).columns
            numeric_columns = [col for col in numeric_columns if col != "Phase"]

            for col in numeric_columns[:5]:  # Show top 5 parameters
                if len(param_evolution_df) >= 2:
                    initial_value = param_evolution_df[col].iloc[0]
                    final_value = param_evolution_df[col].iloc[-1]
                    change = final_value - initial_value
                    report_lines.append(
                        f"- {col}: {initial_value:.4f} → {final_value:.4f} (Δ{change:+.4f})"
                    )

            report_lines.append("")

        # Efficiency analysis
        report_lines.extend(
            [
                "## ⚡ Optimization Efficiency",
                "",
                f"- **Total Trials:** {efficiency_metrics.get('total_trials', 'N/A')}",
                f"- **Convergence Rate:** {efficiency_metrics.get('convergence_rate', 'N/A'):.8f}",
                f"- **Improvement per Trial:** {efficiency_metrics.get('improvement_per_trial', 'N/A'):.8f}",
                "",
            ]
        )

        # Recommendations
        report_lines.extend(
            [
                "## 💡 Recommendations",
                "",
                "Based on the optimization performance analysis:",
                "",
            ]
        )

        # Generate recommendations based on data
        if not summary_df.empty and "Best_Score" in summary_df.columns:
            best_method = summary_df.loc[summary_df["Best_Score"].idxmax()]["Method"]
            report_lines.append(f"- **Best performing method:** {best_method}")

            if "Pruned_Trials" in summary_df.columns:
                total_pruned = summary_df["Pruned_Trials"].sum()
                total_completed = summary_df["Completed_Trials"].sum()
                if total_pruned > 0:
                    pruning_rate = total_pruned / (total_pruned + total_completed)
                    if pruning_rate > 0.3:
                        report_lines.append(
                            f"- **High pruning rate** ({pruning_rate:.1%}): Consider adjusting pruning thresholds"
                        )
                    else:
                        report_lines.append(
                            f"- **Effective pruning** ({pruning_rate:.1%}): Good balance of exploration vs efficiency"
                        )

        report_lines.extend(
            [
                "- Consider increasing trials for the best-performing phase",
                "- Monitor parameter convergence for potential early stopping",
                "- Validate results with out-of-sample data",
                "",
            ]
        )

        # Write report
        output_path = Path(output_file)
        with open(output_path, "w") as f:
            f.write("\n".join(report_lines))

        print(f"✅ Dashboard report generated: {output_path}")

        # Display summary in console
        if not summary_df.empty:
            print("\n📊 Performance Summary:")
            print(
                summary_df[
                    ["Phase", "Best_Score", "Total_Trials", "Success_Rate"]
                ].to_string(index=False)
            )

        return phase_data, summary_df, param_evolution_df, efficiency_metrics


def create_optimization_dashboard():
    """Create comprehensive optimization dashboard."""

    dashboard = OptimizationDashboard()

    print("🚀 Optimization Performance Dashboard")
    print("=" * 50)

    # Generate comprehensive report
    phase_data, summary_df, param_evolution_df, efficiency_metrics = (
        dashboard.generate_dashboard_report()
    )

    # Export data for further analysis
    if not summary_df.empty:
        summary_df.to_csv("optimization_performance_summary.csv", index=False)
        print(
            "📁 Performance summary exported to: optimization_performance_summary.csv"
        )

    if not param_evolution_df.empty:
        param_evolution_df.to_csv("optimization_parameter_evolution.csv", index=False)
        print(
            "📁 Parameter evolution exported to: optimization_parameter_evolution.csv"
        )

    return phase_data, summary_df, param_evolution_df, efficiency_metrics


if __name__ == "__main__":
    create_optimization_dashboard()
