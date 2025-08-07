#!/usr/bin/env python3
"""
QuantBT Terminal User Interface (TUI)
Interactive shell interface for managing all trading tools and services.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Confirm, Prompt
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class QuantBTTUI:
    """Terminal User Interface for QuantBT tools and services."""

    def __init__(self):
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None
        self.current_path = Path.cwd()
        self.config_dir = self.current_path / "configs"
        self.data_dir = self.current_path / "data"
        self.results_dir = self.current_path / "results"

    def print(self, text: str, style: str = ""):
        """Print text with optional styling."""
        if self.console:
            self.console.print(text, style=style)
        else:
            print(text)

    def clear_screen(self):
        """Clear the terminal screen."""
        os.system("cls" if os.name == "nt" else "clear")

    def show_header(self):
        """Show the main header."""
        if self.console:
            header = Panel.fit(
                "[bold blue]🚀 QuantBT Trading Platform[/bold blue]\n"
                "[dim]Interactive Terminal Interface[/dim]",
                border_style="blue",
            )
            self.console.print(header)
        else:
            print("=" * 60)
            print("🚀 QuantBT Trading Platform")
            print("Interactive Terminal Interface")
            print("=" * 60)

    def show_main_menu(self) -> str:
        """Show main menu and get user choice."""
        self.clear_screen()
        self.show_header()

        if self.console:
            table = Table(title="Main Menu", border_style="cyan")
            table.add_column("Option", style="cyan", no_wrap=True)
            table.add_column("Description", style="white")

            menu_items = [
                ("1", "📊 Data Management", "Fetch, validate, and manage market data"),
                ("2", "🎯 Backtesting", "Run backtests and walk-forward analysis"),
                ("3", "🧠 Optimization", "Parameter optimization and tuning"),
                ("4", "📈 Analysis & Reports", "Performance analysis and dashboards"),
                ("5", "📉 Visualization", "Charts and plots"),
                ("6", "📡 Monitoring", "Live monitoring and system status"),
                ("7", "⚙️  Configuration", "Manage configs and settings"),
                ("8", "🛠️  Tools & Utilities", "Debug tools and cleanup"),
                ("9", "📚 Help & Documentation", "Guides and examples"),
                ("0", "🚪 Exit", "Exit the application"),
            ]

            for option, title, desc in menu_items:
                table.add_row(option, f"[bold]{title}[/bold]", desc)

            self.console.print(table)
        else:
            print("\n📋 Main Menu:")
            print("1. 📊 Data Management - Fetch, validate, and manage market data")
            print("2. 🎯 Backtesting - Run backtests and walk-forward analysis")
            print("3. 🧠 Optimization - Parameter optimization and tuning")
            print("4. 📈 Analysis & Reports - Performance analysis and dashboards")
            print("5. 📉 Visualization - Charts and plots")
            print("6. 📡 Monitoring - Live monitoring and system status")
            print("7. ⚙️  Configuration - Manage configs and settings")
            print("8. 🛠️  Tools & Utilities - Debug tools and cleanup")
            print("9. 📚 Help & Documentation - Guides and examples")
            print("0. 🚪 Exit - Exit the application")

        return input("\nEnter your choice (0-9): ").strip()

    def data_management_menu(self):
        """Data management submenu."""
        while True:
            self.clear_screen()
            self.show_header()

            if self.console:
                table = Table(title="📊 Data Management", border_style="green")
                table.add_column("Option", style="green", no_wrap=True)
                table.add_column("Action", style="white")

                table.add_row("1", "📥 Fetch Binance Data")
                table.add_row("2", "✅ Validate Data Files")
                table.add_row("3", "📋 Data File Information")
                table.add_row("4", "📂 Browse Data Directory")
                table.add_row("5", "🗂️  List Available Data")
                table.add_row("0", "← Back to Main Menu")

                self.console.print(table)
            else:
                print("\n📊 Data Management:")
                print("1. 📥 Fetch Binance Data")
                print("2. ✅ Validate Data Files")
                print("3. 📋 Data File Information")
                print("4. 📂 Browse Data Directory")
                print("5. 🗂️  List Available Data")
                print("0. ← Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.fetch_binance_data()
            elif choice == "2":
                self.validate_data_files()
            elif choice == "3":
                self.show_data_info()
            elif choice == "4":
                self.browse_data_directory()
            elif choice == "5":
                self.list_available_data()
            else:
                self.print("❌ Invalid choice!", "red")
                input("Press Enter to continue...")

    def fetch_binance_data(self):
        """Interactive Binance data fetching."""
        self.clear_screen()
        self.print("📥 Fetch Binance Data", "bold green")

        # Get parameters interactively
        symbol = input("Enter symbol (e.g., BTCUSDT): ").strip().upper()
        if not symbol:
            symbol = "BTCUSDT"

        interval = input("Enter interval (1m, 5m, 1h, 1d) [5m]: ").strip()
        if not interval:
            interval = "5m"

        days = input("Enter number of days [7]: ").strip()
        if not days:
            days = "7"

        self.print(
            f"\n🔄 Fetching {symbol} {interval} data for {days} days...", "yellow"
        )

        # Check if fetch script exists
        fetch_script = self.current_path / "scripts" / "fetch_binance_klines.py"
        if fetch_script.exists():
            cmd = f"python3 {fetch_script} --symbol {symbol} --interval {interval} --days {days}"
            self.run_command(cmd)
        else:
            # Fallback to CLI command
            cmd = f"python3 quantbt_simple.py data fetch {symbol} {interval} --days {days}"
            self.run_command(cmd)

        input("\nPress Enter to continue...")

    def backtesting_menu(self):
        """Backtesting submenu."""
        while True:
            self.clear_screen()
            self.show_header()

            if self.console:
                table = Table(title="🎯 Backtesting", border_style="blue")
                table.add_column("Option", style="blue", no_wrap=True)
                table.add_column("Action", style="white")

                table.add_row("1", "🚀 Quick Backtest")
                table.add_row("2", "⚙️  Custom Backtest")
                table.add_row("3", "🔄 Walk-Forward Analysis")
                table.add_row("4", "📊 Batch Backtesting")
                table.add_row("5", "🎯 Live Trading Mode")
                table.add_row("6", "📈 View Recent Results")
                table.add_row("0", "← Back to Main Menu")

                self.console.print(table)
            else:
                print("\n🎯 Backtesting:")
                print("1. 🚀 Quick Backtest")
                print("2. ⚙️  Custom Backtest")
                print("3. 🔄 Walk-Forward Analysis")
                print("4. 📊 Batch Backtesting")
                print("5. 🎯 Live Trading Mode")
                print("6. 📈 View Recent Results")
                print("0. ← Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.quick_backtest()
            elif choice == "2":
                self.custom_backtest()
            elif choice == "3":
                self.walk_forward_analysis()
            elif choice == "6":
                self.view_recent_results()
            else:
                self.print("❌ Invalid choice!", "red")
                input("Press Enter to continue...")

    def quick_backtest(self):
        """Run a quick backtest with default settings."""
        self.clear_screen()
        self.print("🚀 Quick Backtest", "bold blue")

        # List available configs
        configs = (
            list(self.config_dir.glob("*.yaml")) if self.config_dir.exists() else []
        )

        if not configs:
            self.print("❌ No config files found!", "red")
            input("Press Enter to continue...")
            return

        self.print("\nAvailable configurations:")
        for i, config in enumerate(configs, 1):
            print(f"{i}. {config.name}")

        choice = input(
            f"\nSelect config (1-{len(configs)}) or Enter for default: "
        ).strip()

        if choice.isdigit() and 1 <= int(choice) <= len(configs):
            config_file = configs[int(choice) - 1]
        else:
            config_file = configs[0]  # Default to first config

        # Ask about plotting
        plot = input("Generate plot? (y/N): ").strip().lower() == "y"

        self.print(f"\n🔄 Running backtest with {config_file.name}...", "yellow")

        cmd = f"python3 quantbt_simple.py backtest run --config {config_file}"
        if plot:
            cmd += " --plot"

        self.run_command(cmd)
        input("\nPress Enter to continue...")

    def optimization_menu(self):
        """Optimization submenu."""
        while True:
            self.clear_screen()
            self.show_header()

            if self.console:
                table = Table(title="🧠 Optimization", border_style="magenta")
                table.add_column("Option", style="magenta", no_wrap=True)
                table.add_column("Action", style="white")

                table.add_row("1", "⚡ Ultra Fast Optimization")
                table.add_row("2", "🎯 3-Phase Optimization")
                table.add_row("3", "🧠 Bayesian Optimization")
                table.add_row("4", "📊 Production Optimization")
                table.add_row("5", "📈 View Optimization Status")
                table.add_row("6", "🛑 Stop Running Optimization")
                table.add_row("0", "← Back to Main Menu")

                self.console.print(table)
            else:
                print("\n🧠 Optimization:")
                print("1. ⚡ Ultra Fast Optimization")
                print("2. 🎯 3-Phase Optimization")
                print("3. 🧠 Bayesian Optimization")
                print("4. 📊 Production Optimization")
                print("5. 📈 View Optimization Status")
                print("6. 🛑 Stop Running Optimization")
                print("0. ← Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.ultra_fast_optimization()
            elif choice == "2":
                self.three_phase_optimization()
            elif choice == "5":
                self.view_optimization_status()
            else:
                self.print("❌ Invalid choice!", "red")
                input("Press Enter to continue...")

    def ultra_fast_optimization(self):
        """Run ultra fast optimization."""
        self.clear_screen()
        self.print("⚡ Ultra Fast Optimization", "bold magenta")

        trials = input("Number of trials [50]: ").strip()
        if not trials:
            trials = "50"

        self.print(
            f"\n🔄 Running ultra fast optimization with {trials} trials...", "yellow"
        )

        # Check if optimization script exists
        opt_script = (
            self.current_path
            / "tools"
            / "optimization"
            / "run_ultra_fast_optimization.py"
        )
        if opt_script.exists():
            cmd = f"python3 {opt_script} --trials {trials}"
        else:
            cmd = f"python3 quantbt_simple.py optimize quick --trials {trials}"

        self.run_command(cmd)
        input("\nPress Enter to continue...")

    def three_phase_optimization(self):
        """Run 3-phase optimization."""
        self.clear_screen()
        self.print("🎯 3-Phase Optimization", "bold magenta")

        n1 = input("Phase 1 trials [25]: ").strip() or "25"
        n2 = input("Phase 2 trials [25]: ").strip() or "25"
        n3 = input("Phase 3 trials [50]: ").strip() or "50"

        self.print(f"\n🔄 Running 3-phase optimization ({n1}/{n2}/{n3})...", "yellow")

        opt_script = (
            self.current_path / "tools" / "optimization" / "run_3phase_optimization.py"
        )
        if opt_script.exists():
            cmd = f"python3 {opt_script} --n1 {n1} --n2 {n2} --n3 {n3}"
        else:
            cmd = f"python3 quantbt_simple.py optimize 3phase --n1 {n1} --n2 {n2} --n3 {n3}"

        self.run_command(cmd)
        input("\nPress Enter to continue...")

    def monitoring_menu(self):
        """Monitoring submenu."""
        while True:
            self.clear_screen()
            self.show_header()

            if self.console:
                table = Table(title="📡 Monitoring", border_style="yellow")
                table.add_column("Option", style="yellow", no_wrap=True)
                table.add_column("Action", style="white")

                table.add_row("1", "💻 System Status")
                table.add_row("2", "🔄 Optimization Monitor")
                table.add_row("3", "📊 Live Performance")
                table.add_row("4", "📈 Resource Usage")
                table.add_row("5", "🎯 Trading Status")
                table.add_row("0", "← Back to Main Menu")

                self.console.print(table)
            else:
                print("\n📡 Monitoring:")
                print("1. 💻 System Status")
                print("2. 🔄 Optimization Monitor")
                print("3. 📊 Live Performance")
                print("4. 📈 Resource Usage")
                print("5. 🎯 Trading Status")
                print("0. ← Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.show_system_status()
            elif choice == "2":
                self.optimization_monitor()
            else:
                self.print("❌ Invalid choice!", "red")
                input("Press Enter to continue...")

    def show_system_status(self):
        """Show comprehensive system status."""
        self.clear_screen()
        self.print("💻 System Status", "bold yellow")

        cmd = "python3 quantbt_simple.py monitor system"
        self.run_command(cmd)

        input("\nPress Enter to continue...")

    def configuration_menu(self):
        """Configuration management submenu."""
        while True:
            self.clear_screen()
            self.show_header()

            if self.console:
                table = Table(title="⚙️ Configuration", border_style="cyan")
                table.add_column("Option", style="cyan", no_wrap=True)
                table.add_column("Action", style="white")

                table.add_row("1", "📋 List Configurations")
                table.add_row("2", "✅ Validate Config")
                table.add_row("3", "📝 Create New Config")
                table.add_row("4", "📂 Browse Config Directory")
                table.add_row("5", "🔧 Edit Configuration")
                table.add_row("0", "← Back to Main Menu")

                self.console.print(table)
            else:
                print("\n⚙️ Configuration:")
                print("1. 📋 List Configurations")
                print("2. ✅ Validate Config")
                print("3. 📝 Create New Config")
                print("4. 📂 Browse Config Directory")
                print("5. 🔧 Edit Configuration")
                print("0. ← Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                self.list_configurations()
            elif choice == "2":
                self.validate_configuration()
            elif choice == "4":
                self.browse_config_directory()
            else:
                self.print("❌ Invalid choice!", "red")
                input("Press Enter to continue...")

    def list_configurations(self):
        """List all available configurations."""
        self.clear_screen()
        self.print("📋 Available Configurations", "bold cyan")

        cmd = "python3 quantbt_simple.py config list"
        self.run_command(cmd)

        input("\nPress Enter to continue...")

    def run_command(self, command: str) -> bool:
        """Run a shell command and display output."""
        try:
            if self.console:
                with self.console.status(f"[yellow]Running: {command}[/yellow]"):
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        cwd=self.current_path,
                    )
            else:
                print(f"Running: {command}")
                result = subprocess.run(
                    command, shell=True, text=True, cwd=self.current_path
                )

            if result.returncode == 0:
                if hasattr(result, "stdout") and result.stdout:
                    print(result.stdout)
                self.print("✅ Command completed successfully!", "green")
                return True
            else:
                if hasattr(result, "stderr") and result.stderr:
                    self.print(f"❌ Error: {result.stderr}", "red")
                else:
                    self.print("❌ Command failed!", "red")
                return False

        except Exception as e:
            self.print(f"❌ Error running command: {e}", "red")
            return False

    def validate_data_files(self):
        """Validate data files interactively."""
        self.clear_screen()
        self.print("✅ Validate Data Files", "bold green")

        # List data files
        if self.data_dir.exists():
            data_files = list(self.data_dir.glob("*.csv"))
            if data_files:
                self.print("\nAvailable data files:")
                for i, file in enumerate(data_files, 1):
                    print(f"{i}. {file.name}")

                choice = input(
                    f"\nSelect file to validate (1-{len(data_files)}) or 'all': "
                ).strip()

                if choice.lower() == "all":
                    for file in data_files:
                        self.print(f"\n🔍 Validating {file.name}...", "yellow")
                        cmd = f"python3 quantbt_simple.py data validate {file}"
                        self.run_command(cmd)
                elif choice.isdigit() and 1 <= int(choice) <= len(data_files):
                    file = data_files[int(choice) - 1]
                    self.print(f"\n🔍 Validating {file.name}...", "yellow")
                    cmd = f"python3 quantbt_simple.py data validate {file}"
                    self.run_command(cmd)
                else:
                    self.print("❌ Invalid choice!", "red")
            else:
                self.print("❌ No CSV files found in data directory!", "red")
        else:
            self.print("❌ Data directory not found!", "red")

        input("\nPress Enter to continue...")

    def show_data_info(self):
        """Show data file information."""
        self.clear_screen()
        self.print("📋 Data File Information", "bold green")

        if self.data_dir.exists():
            data_files = list(self.data_dir.glob("*.csv"))
            if data_files:
                self.print("\nAvailable data files:")
                for i, file in enumerate(data_files, 1):
                    print(f"{i}. {file.name}")

                choice = input(
                    f"\nSelect file for info (1-{len(data_files)}): "
                ).strip()

                if choice.isdigit() and 1 <= int(choice) <= len(data_files):
                    file = data_files[int(choice) - 1]
                    self.print(f"\n📊 Information for {file.name}...", "yellow")
                    cmd = f"python3 quantbt_simple.py data info {file}"
                    self.run_command(cmd)
                else:
                    self.print("❌ Invalid choice!", "red")
            else:
                self.print("❌ No CSV files found in data directory!", "red")
        else:
            self.print("❌ Data directory not found!", "red")

        input("\nPress Enter to continue...")

    def browse_data_directory(self):
        """Browse data directory contents."""
        self.clear_screen()
        self.print("📂 Data Directory Contents", "bold green")

        if self.data_dir.exists():
            files = list(self.data_dir.iterdir())
            if files:
                if self.console:
                    table = Table(title=f"Files in {self.data_dir}")
                    table.add_column("Name", style="cyan")
                    table.add_column("Type", style="green")
                    table.add_column("Size", style="yellow")
                    table.add_column("Modified", style="blue")

                    for file in sorted(files):
                        if file.is_file():
                            size = file.stat().st_size
                            size_str = (
                                f"{size:,} bytes"
                                if size < 1024 * 1024
                                else f"{size / (1024 * 1024):.1f} MB"
                            )
                            modified = datetime.fromtimestamp(
                                file.stat().st_mtime
                            ).strftime("%Y-%m-%d %H:%M")
                            table.add_row(file.name, "File", size_str, modified)
                        else:
                            table.add_row(file.name, "Directory", "-", "-")

                    self.console.print(table)
                else:
                    for file in sorted(files):
                        if file.is_file():
                            size = file.stat().st_size
                            size_str = (
                                f"{size:,} bytes"
                                if size < 1024 * 1024
                                else f"{size / (1024 * 1024):.1f} MB"
                            )
                            print(f"📄 {file.name} ({size_str})")
                        else:
                            print(f"📁 {file.name}/")
            else:
                self.print("📂 Directory is empty", "yellow")
        else:
            self.print("❌ Data directory not found!", "red")

        input("\nPress Enter to continue...")

    def browse_config_directory(self):
        """Browse configuration directory contents."""
        self.clear_screen()
        self.print("📂 Configuration Directory Contents", "bold cyan")

        if self.config_dir.exists():
            configs = list(self.config_dir.glob("*.yaml"))
            if configs:
                if self.console:
                    table = Table(title=f"Configurations in {self.config_dir}")
                    table.add_column("Name", style="cyan")
                    table.add_column("Size", style="yellow")
                    table.add_column("Modified", style="blue")

                    for config in sorted(configs):
                        size = config.stat().st_size
                        size_str = f"{size:,} bytes"
                        modified = datetime.fromtimestamp(
                            config.stat().st_mtime
                        ).strftime("%Y-%m-%d %H:%M")
                        table.add_row(config.name, size_str, modified)

                    self.console.print(table)
                else:
                    for config in sorted(configs):
                        size = config.stat().st_size
                        print(f"⚙️  {config.name} ({size:,} bytes)")
            else:
                self.print("📂 No YAML configuration files found", "yellow")
        else:
            self.print("❌ Configuration directory not found!", "red")

        input("\nPress Enter to continue...")

    def list_available_data(self):
        """List all available data with details."""
        self.clear_screen()
        self.print("🗂️  Available Data Files", "bold green")

        if self.data_dir.exists():
            csv_files = list(self.data_dir.glob("*.csv"))
            parquet_files = list(self.data_dir.glob("*.parquet"))

            all_files = csv_files + parquet_files

            if all_files:
                if self.console:
                    table = Table(title="Market Data Files")
                    table.add_column("File", style="cyan")
                    table.add_column("Format", style="green")
                    table.add_column("Size", style="yellow")
                    table.add_column("Symbol", style="blue")
                    table.add_column("Timeframe", style="magenta")

                    for file in sorted(all_files):
                        size = file.stat().st_size
                        size_str = (
                            f"{size / (1024 * 1024):.1f} MB"
                            if size > 1024 * 1024
                            else f"{size:,} bytes"
                        )

                        # Try to extract symbol and timeframe from filename
                        name = file.stem
                        parts = name.split("_")
                        symbol = parts[0] if parts else "Unknown"
                        timeframe = parts[1] if len(parts) > 1 else "Unknown"

                        table.add_row(
                            file.name,
                            file.suffix[1:].upper(),
                            size_str,
                            symbol,
                            timeframe,
                        )

                    self.console.print(table)
                else:
                    print(f"\nFound {len(all_files)} data files:")
                    for file in sorted(all_files):
                        size = file.stat().st_size
                        size_str = (
                            f"{size / (1024 * 1024):.1f} MB"
                            if size > 1024 * 1024
                            else f"{size:,} bytes"
                        )
                        print(f"📊 {file.name} ({size_str})")
            else:
                self.print("📂 No data files found", "yellow")
        else:
            self.print("❌ Data directory not found!", "red")

        input("\nPress Enter to continue...")

    def validate_configuration(self):
        """Validate a configuration file."""
        self.clear_screen()
        self.print("✅ Validate Configuration", "bold cyan")

        if self.config_dir.exists():
            configs = list(self.config_dir.glob("*.yaml"))
            if configs:
                self.print("\nAvailable configurations:")
                for i, config in enumerate(configs, 1):
                    print(f"{i}. {config.name}")

                choice = input(
                    f"\nSelect config to validate (1-{len(configs)}): "
                ).strip()

                if choice.isdigit() and 1 <= int(choice) <= len(configs):
                    config = configs[int(choice) - 1]
                    self.print(f"\n🔍 Validating {config.name}...", "yellow")
                    cmd = f"python3 quantbt_simple.py config validate {config}"
                    self.run_command(cmd)
                else:
                    self.print("❌ Invalid choice!", "red")
            else:
                self.print("❌ No YAML configuration files found!", "red")
        else:
            self.print("❌ Configuration directory not found!", "red")

        input("\nPress Enter to continue...")

    def view_recent_results(self):
        """View recent backtest results."""
        self.clear_screen()
        self.print("📈 Recent Backtest Results", "bold blue")

        if self.results_dir.exists():
            # Look for recent result directories
            result_dirs = [
                d
                for d in self.results_dir.iterdir()
                if d.is_dir() and d.name.startswith("backtest_")
            ]
            result_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            if result_dirs:
                self.print(f"\nFound {len(result_dirs)} recent results:")
                for i, result_dir in enumerate(result_dirs[:10], 1):  # Show top 10
                    modified = datetime.fromtimestamp(
                        result_dir.stat().st_mtime
                    ).strftime("%Y-%m-%d %H:%M")
                    print(f"{i}. {result_dir.name} ({modified})")

                choice = input(
                    f"\nSelect result to view (1-{min(10, len(result_dirs))}): "
                ).strip()

                if choice.isdigit() and 1 <= int(choice) <= min(10, len(result_dirs)):
                    result_dir = result_dirs[int(choice) - 1]

                    # List files in result directory
                    files = list(result_dir.iterdir())
                    if files:
                        self.print(f"\nFiles in {result_dir.name}:")
                        for file in sorted(files):
                            if file.is_file():
                                size = file.stat().st_size
                                print(f"📄 {file.name} ({size:,} bytes)")

                                # If it's a JSON result file, show summary
                                if file.suffix == ".json" and "result" in file.name:
                                    try:
                                        import json

                                        with open(file) as f:
                                            data = json.load(f)

                                        if "total_pnl" in data:
                                            self.print(
                                                f"   💰 Total PnL: {data['total_pnl']:.2f}",
                                                "green"
                                                if data["total_pnl"] > 0
                                                else "red",
                                            )
                                        if "total_trades" in data:
                                            self.print(
                                                f"   📊 Total Trades: {data['total_trades']}"
                                            )
                                        if "win_rate" in data:
                                            self.print(
                                                f"   🎯 Win Rate: {data['win_rate']:.1%}"
                                            )
                                    except Exception:
                                        pass
                    else:
                        self.print("📂 Result directory is empty", "yellow")
                else:
                    self.print("❌ Invalid choice!", "red")
            else:
                self.print("📂 No recent results found", "yellow")
        else:
            self.print("❌ Results directory not found!", "red")

        input("\nPress Enter to continue...")

    def custom_backtest(self):
        """Run custom backtest with user inputs."""
        self.clear_screen()
        self.print("⚙️  Custom Backtest", "bold blue")

        # Select config
        configs = (
            list(self.config_dir.glob("*.yaml")) if self.config_dir.exists() else []
        )
        if not configs:
            self.print("❌ No config files found!", "red")
            input("Press Enter to continue...")
            return

        self.print("\nAvailable configurations:")
        for i, config in enumerate(configs, 1):
            print(f"{i}. {config.name}")

        config_choice = input(f"\nSelect config (1-{len(configs)}): ").strip()
        if not (config_choice.isdigit() and 1 <= int(config_choice) <= len(configs)):
            self.print("❌ Invalid config choice!", "red")
            input("Press Enter to continue...")
            return

        config_file = configs[int(config_choice) - 1]

        # Additional options
        plot = input("Generate plot? (y/N): ").strip().lower() == "y"
        save_trades = input("Save trade details? (y/N): ").strip().lower() == "y"
        verbose = input("Verbose output? (y/N): ").strip().lower() == "y"

        # Build command
        cmd = f"python3 quantbt_simple.py backtest run --config {config_file}"
        if plot:
            cmd += " --plot"
        if save_trades:
            cmd += " --save-trades"
        if verbose:
            cmd += " --verbose"

        self.print("\n🔄 Running custom backtest...", "yellow")
        self.run_command(cmd)

        input("\nPress Enter to continue...")

    def walk_forward_analysis(self):
        """Run walk-forward analysis."""
        self.clear_screen()
        self.print("🔄 Walk-Forward Analysis", "bold blue")

        # Select data file
        if self.data_dir.exists():
            data_files = list(self.data_dir.glob("*.csv"))
            if not data_files:
                self.print("❌ No CSV data files found!", "red")
                input("Press Enter to continue...")
                return

            self.print("\nAvailable data files:")
            for i, file in enumerate(data_files, 1):
                print(f"{i}. {file.name}")

            file_choice = input(f"\nSelect data file (1-{len(data_files)}): ").strip()
            if not (file_choice.isdigit() and 1 <= int(file_choice) <= len(data_files)):
                self.print("❌ Invalid file choice!", "red")
                input("Press Enter to continue...")
                return

            data_file = data_files[int(file_choice) - 1]

            # Get parameters
            folds = input("Number of folds [6]: ").strip() or "6"
            train_fraction = input("Training fraction [0.5]: ").strip() or "0.5"

            self.print(
                f"\n🔄 Running walk-forward analysis with {folds} folds...", "yellow"
            )

            cmd = f"python3 quantbt_simple.py backtest walk-forward {data_file} --folds {folds} --train-fraction {train_fraction}"
            self.run_command(cmd)
        else:
            self.print("❌ Data directory not found!", "red")

        input("\nPress Enter to continue...")

    def view_optimization_status(self):
        """View current optimization status."""
        self.clear_screen()
        self.print("📈 Optimization Status", "bold magenta")

        # Check for optimization results
        phase_dirs = ["phase1_random", "phase2_random", "phase3_bayesian"]

        if self.results_dir.exists():
            for phase in phase_dirs:
                phase_dir = self.results_dir / phase
                if phase_dir.exists():
                    files = list(phase_dir.iterdir())
                    self.print(f"\n📁 {phase}: {len(files)} files")

                    # Show recent files
                    recent_files = sorted(
                        [f for f in files if f.is_file()],
                        key=lambda x: x.stat().st_mtime,
                        reverse=True,
                    )[:3]
                    for file in recent_files:
                        modified = datetime.fromtimestamp(
                            file.stat().st_mtime
                        ).strftime("%Y-%m-%d %H:%M")
                        print(f"   📄 {file.name} ({modified})")
                else:
                    self.print(f"\n📁 {phase}: Not found", "yellow")
        else:
            self.print("❌ Results directory not found!", "red")

        # Check for running processes
        self.print("\n🔍 Checking for running optimization processes...")
        try:
            result = subprocess.run(
                "ps aux | grep -E 'optimization|optuna' | grep -v grep",
                shell=True,
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                self.print("🔄 Found running optimization processes:", "green")
                print(result.stdout)
            else:
                self.print("💤 No optimization processes currently running", "yellow")
        except Exception:
            self.print("❌ Could not check process status", "red")

        input("\nPress Enter to continue...")

    def optimization_monitor(self):
        """Monitor optimization in real-time."""
        self.clear_screen()
        self.print("🔄 Optimization Monitor", "bold yellow")

        monitor_script = (
            self.current_path / "tools" / "monitoring" / "monitor_optimization_live.py"
        )
        if monitor_script.exists():
            self.print("🚀 Starting live optimization monitor...", "green")
            cmd = f"python3 {monitor_script}"
            self.run_command(cmd)
        else:
            self.print("❌ Live monitor script not found!", "red")
            self.print("💡 Try checking optimization status instead.", "yellow")

        input("\nPress Enter to continue...")

    def help_menu(self):
        """Show help and documentation."""
        self.clear_screen()
        self.print("📚 Help & Documentation", "bold white")

        if self.console:
            table = Table(title="Available Resources")
            table.add_column("Resource", style="cyan")
            table.add_column("Description", style="white")

            table.add_row("📖 README.md", "Main project documentation")
            table.add_row("📋 ENHANCED_CLI_GUIDE.md", "Enhanced CLI guide")
            table.add_row("🎯 docs/", "Detailed documentation directory")
            table.add_row("💡 --help", "Command-line help for any command")
            table.add_row(
                "🧪 test_enhanced_cli.py", "Test and validate CLI functionality"
            )

            self.console.print(table)
        else:
            print("\n📚 Available Resources:")
            print("📖 README.md - Main project documentation")
            print("📋 ENHANCED_CLI_GUIDE.md - Enhanced CLI guide")
            print("🎯 docs/ - Detailed documentation directory")
            print("💡 --help - Command-line help for any command")
            print("🧪 test_enhanced_cli.py - Test and validate CLI functionality")

        self.print("\n🎯 Quick Tips:")
        print("• Use 'python3 quantbt_simple.py --help' for command reference")
        print("• All commands support --help for detailed usage")
        print("• Check the docs/ directory for comprehensive guides")
        print("• Use monitor system to check your environment")

        input("\nPress Enter to continue...")

    def run(self):
        """Main application loop."""
        while True:
            try:
                choice = self.show_main_menu()

                if choice == "0":
                    self.clear_screen()
                    self.print("👋 Thank you for using QuantBT! Goodbye!", "bold green")
                    break
                elif choice == "1":
                    self.data_management_menu()
                elif choice == "2":
                    self.backtesting_menu()
                elif choice == "3":
                    self.optimization_menu()
                elif choice == "4":
                    # Analysis menu
                    self.clear_screen()
                    self.print("📈 Analysis & Reports", "bold blue")
                    self.print("🔄 Generating optimization dashboard...", "yellow")
                    cmd = "python3 quantbt_simple.py analyze dashboard"
                    self.run_command(cmd)
                    input("\nPress Enter to continue...")
                elif choice == "5":
                    # Visualization menu
                    self.clear_screen()
                    self.print("📉 Visualization", "bold blue")
                    self.print("This feature will be available soon!", "yellow")
                    input("\nPress Enter to continue...")
                elif choice == "6":
                    self.monitoring_menu()
                elif choice == "7":
                    self.configuration_menu()
                elif choice == "8":
                    # Tools menu
                    self.clear_screen()
                    self.print("🛠️  Tools & Utilities", "bold blue")
                    self.print("🧹 Running cleanup...", "yellow")
                    cmd = "python3 quantbt_simple.py tools cleanup --cache"
                    self.run_command(cmd)
                    input("\nPress Enter to continue...")
                elif choice == "9":
                    self.help_menu()
                else:
                    self.print("❌ Invalid choice! Please try again.", "red")
                    input("Press Enter to continue...")

            except KeyboardInterrupt:
                self.clear_screen()
                self.print("\n👋 Goodbye!", "bold yellow")
                break
            except Exception as e:
                self.print(f"\n❌ Error: {e}", "red")
                input("Press Enter to continue...")


def main():
    """Entry point for the TUI application."""
    try:
        app = QuantBTTUI()
        app.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
