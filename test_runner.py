#!/usr/bin/env python3
"""
Test runner script for the algorithmic trading system.

This script provides convenient commands for running different types of tests
and quality checks during development.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description=""):
    """Run a shell command and handle errors."""
    print(f"\n{'='*50}")
    print(f"Running: {description or cmd}")
    print(f"{'='*50}")

    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=False)
        print(f"✅ {description or cmd} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description or cmd} failed with exit code {e.returncode}")
        return False


def main():
    """Main test runner."""
    if len(sys.argv) < 2:
        print("Usage: python test_runner.py <command>")
        print("\nAvailable commands:")
        print("  format     - Format code with black and isort")
        print("  lint       - Run linting checks")
        print("  type       - Run type checking")
        print("  security   - Run security scans")
        print("  test       - Run all tests")
        print("  unit       - Run unit tests only")
        print("  integration - Run integration tests only")
        print("  coverage   - Run tests with coverage report")
        print("  quality    - Run all quality checks")
        print("  ci         - Run full CI pipeline locally")
        print("  install    - Install development dependencies")
        return 1

    command = sys.argv[1].lower()

    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)

    success = True

    if command == "install":
        success &= run_command(
            "pip install -r requirements.txt", "Installing main dependencies"
        )
        success &= run_command(
            "pip install -r dev-requirements.txt",
            "Installing dev dependencies",
        )
        success &= run_command("pre-commit install", "Installing pre-commit hooks")

    elif command == "format":
        success &= run_command("black .", "Formatting code with Black")
        success &= run_command("isort .", "Sorting imports with isort")

    elif command == "lint":
        success &= run_command("flake8 .", "Linting with Flake8")
        success &= run_command(
            "pylint core/ tests/ --fail-under=8.0", "Linting with Pylint"
        )

    elif command == "type":
        success &= run_command(
            "mypy core/ --ignore-missing-imports", "Type checking with Mypy"
        )

    elif command == "security":
        success &= run_command("bandit -r core/", "Security scanning with Bandit")
        success &= run_command("safety check", "Checking for known vulnerabilities")

    elif command == "test":
        success &= run_command("pytest tests/ -v", "Running all tests")

    elif command == "unit":
        success &= run_command("pytest tests/unit/ -v", "Running unit tests")

    elif command == "integration":
        success &= run_command(
            "pytest tests/integration/ -v", "Running integration tests"
        )

    elif command == "coverage":
        success &= run_command(
            "pytest tests/ --cov=core --cov-report=html "
            "--cov-report=term --cov-report=xml",
            "Running tests with coverage",
        )
        print("\n📊 Coverage report generated in htmlcov/index.html")

    elif command == "quality":
        print("🔍 Running comprehensive quality checks...")
        success &= run_command("black --check .", "Checking code formatting")
        success &= run_command("isort --check-only .", "Checking import sorting")
        success &= run_command("flake8 .", "Linting with Flake8")
        success &= run_command(
            "pylint core/ tests/ --fail-under=8.0", "Linting with Pylint"
        )
        success &= run_command("mypy core/ --ignore-missing-imports", "Type checking")
        success &= run_command("bandit -r core/ -q", "Security scanning")

    elif command == "ci":
        print("🚀 Running full CI pipeline locally...")
        success &= run_command("black --check .", "Checking code formatting")
        success &= run_command("isort --check-only .", "Checking import sorting")
        success &= run_command("flake8 .", "Linting with Flake8")
        success &= run_command(
            "pylint core/ tests/ --fail-under=8.0", "Linting with Pylint"
        )
        success &= run_command("mypy core/ --ignore-missing-imports", "Type checking")
        success &= run_command("bandit -r core/ -q", "Security scanning")
        success &= run_command(
            "pytest tests/ --cov=core --cov-report=term --cov-fail-under=70",
            "Running tests with coverage",
        )

    else:
        print(f"❌ Unknown command: {command}")
        return 1

    if success:
        print(f"\n🎉 All {command} checks passed!")
        return 0
    else:
        print(f"\n💥 Some {command} checks failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
