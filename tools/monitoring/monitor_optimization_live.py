#!/usr/bin/env python3
"""
Real-time Optimization Performance Monitor
Tracks optimization progress and displays live performance metrics.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


class OptimizationMonitor:
    """Real-time monitoring of optimization performance."""

    def __init__(self, results_dir: str = "results"):
        self.results_dir = Path(results_dir)
        self.last_update = {}
        self.performance_history = []

    def get_latest_metrics(self, phase_dir: str) -> dict[str, Any]:
        """Get the latest performance metrics from a phase directory."""
        phase_path = self.results_dir / phase_dir

        if not phase_path.exists():
            return {}

        # Check for the most recent result files
        result_files = sorted(
            phase_path.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True
        )

        for result_file in result_files:
            try:
                # Check if file was modified since last check
                mtime = result_file.stat().st_mtime
                if (
                    result_file.name in self.last_update
                    and mtime <= self.last_update[result_file.name]
                ):
                    continue

                self.last_update[result_file.name] = mtime

                with open(result_file) as f:
                    data = json.load(f)

                # Extract metrics
                metrics = {}
                if "metrics" in data:
                    metrics.update(data["metrics"])
                if "best_value" in data:
                    metrics["best_score"] = data["best_value"]
                if "best_params" in data:
                    metrics["best_params"] = data["best_params"]

                # Add metadata
                metrics["timestamp"] = datetime.now().isoformat()
                metrics["phase"] = phase_dir
                metrics["file"] = result_file.name

                return metrics

            except Exception:
                continue

        return {}

    def monitor_all_phases(self, duration_minutes: int = 60, update_interval: int = 30):
        """Monitor all optimization phases for a specified duration."""

        phases = ["phase1_random", "phase2_random", "phase3_bayesian"]
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        print(f"🔍 Starting optimization monitoring for {duration_minutes} minutes...")
        print(f"Update interval: {update_interval} seconds")
        print("=" * 70)

        while time.time() < end_time:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n⏰ Update at {current_time}")
            print("-" * 50)

            # Check each phase
            phase_metrics = {}
            for phase in phases:
                metrics = self.get_latest_metrics(phase)
                if metrics:
                    phase_metrics[phase] = metrics

                    # Display current performance
                    print(f"\n📊 {phase.replace('_', ' ').title()}:")

                    # Key metrics
                    if "best_score" in metrics:
                        print(f"  Best Score: {metrics['best_score']:.6f}")

                    if "total_pnl" in metrics:
                        print(f"  Total PnL: {metrics['total_pnl']}")

                    if "sharpe_ratio" in metrics:
                        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.4f}")

                    if "win_rate" in metrics:
                        print(f"  Win Rate: {metrics['win_rate']:.2%}")

                    if "total_trades" in metrics:
                        print(f"  Total Trades: {metrics['total_trades']}")

                    # Best parameters (abbreviated)
                    if "best_params" in metrics:
                        params = metrics["best_params"]
                        key_params = ["risk_per_trade", "tp_rr", "zone_min_strength"]
                        param_str = ", ".join(
                            [
                                f"{k}={params.get(k, 'N/A')}"
                                for k in key_params
                                if k in params
                            ]
                        )
                        if param_str:
                            print(f"  Key Params: {param_str}")
                else:
                    print(f"\n📊 {phase.replace('_', ' ').title()}: No new data")

            # Store history
            if phase_metrics:
                self.performance_history.append(
                    {"timestamp": current_time, "phases": phase_metrics}
                )

            # Performance comparison
            if len(self.performance_history) >= 2:
                self.show_performance_trends()

            # Wait for next update
            time.sleep(update_interval)

        print(
            f"\n✅ Monitoring completed. Total updates: {len(self.performance_history)}"
        )
        return self.performance_history

    def show_performance_trends(self):
        """Show performance trends across recent updates."""
        if len(self.performance_history) < 2:
            return

        print("\n📈 Performance Trends (last 2 updates):")

        current = self.performance_history[-1]["phases"]
        previous = self.performance_history[-2]["phases"]

        for phase in current:
            if phase in previous:
                curr_score = current[phase].get("best_score", 0)
                prev_score = previous[phase].get("best_score", 0)

                if prev_score != 0:
                    change = ((curr_score - prev_score) / abs(prev_score)) * 100
                    trend_icon = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                    print(f"  {phase}: {trend_icon} {change:+.2f}%")

    def export_performance_data(
        self, output_file: str = "optimization_monitor_data.json"
    ):
        """Export collected performance data."""
        output_path = Path(output_file)

        with open(output_path, "w") as f:
            json.dump(self.performance_history, f, indent=2)

        print(f"📁 Performance data exported to: {output_path}")
        return output_path

    def generate_performance_chart(
        self, output_file: str = "optimization_progress.png"
    ):
        """Generate a performance chart (requires matplotlib)."""
        try:
            import matplotlib.pyplot as plt

            if not self.performance_history:
                print("No performance data to chart")
                return

            # Extract data for charting
            timestamps = []
            phase_data = {
                "phase1_random": [],
                "phase2_random": [],
                "phase3_bayesian": [],
            }

            for entry in self.performance_history:
                timestamps.append(entry["timestamp"])

                for phase in phase_data:
                    if phase in entry["phases"]:
                        score = entry["phases"][phase].get("best_score", None)
                        phase_data[phase].append(score)
                    else:
                        phase_data[phase].append(None)

            # Create chart
            plt.figure(figsize=(12, 6))

            for phase, scores in phase_data.items():
                if any(s is not None for s in scores):
                    # Filter out None values
                    filtered_timestamps = [
                        t
                        for t, s in zip(timestamps, scores, strict=False)
                        if s is not None
                    ]
                    filtered_scores = [s for s in scores if s is not None]

                    plt.plot(
                        filtered_timestamps,
                        filtered_scores,
                        marker="o",
                        label=phase.replace("_", " ").title(),
                    )

            plt.title("Optimization Performance Progress")
            plt.xlabel("Time")
            plt.ylabel("Best Score")
            plt.legend()
            plt.xticks(rotation=45)
            plt.tight_layout()

            plt.savefig(output_file)
            plt.close()

            print(f"📈 Performance chart saved: {output_file}")

        except ImportError:
            print("Matplotlib not available. Install with: pip install matplotlib")
        except Exception as e:
            print(f"Failed to generate chart: {e}")


def start_live_monitoring():
    """Start live monitoring of optimization progress."""

    monitor = OptimizationMonitor()

    print("🚀 Live Optimization Performance Monitor")
    print("=" * 50)
    print("This will monitor optimization progress in real-time")
    print("Press Ctrl+C to stop monitoring early")

    try:
        # Monitor for 2 hours with updates every 30 seconds
        history = monitor.monitor_all_phases(duration_minutes=120, update_interval=30)

        # Export data
        monitor.export_performance_data()

        # Generate chart if possible
        monitor.generate_performance_chart()

        return history

    except KeyboardInterrupt:
        print("\n⏹️ Monitoring stopped by user")

        # Still export any collected data
        if monitor.performance_history:
            monitor.export_performance_data()
            monitor.generate_performance_chart()

        return monitor.performance_history


if __name__ == "__main__":
    start_live_monitoring()
