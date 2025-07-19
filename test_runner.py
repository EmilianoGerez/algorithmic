#!/usr / bin / env python3
"""
Test runner script for the algorithmic trading system.

This script provides convenient commands for running different types of tests
and quality checks during development.
"""

import os
import shlex
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description=""):
    """Run a shell command and handle errors."""
    print(f"\n{'=' * 50}")
    print(f"Running: {description or cmd}")
    print(f"{'=' * 50}")

    try:
        # Use shlex.split for secure command parsing
        if isinstance(cmd, str):
            cmd_list = shlex.split(cmd)
        else:
            cmd_list = cmd

        subprocess.run(cmd_list, shell=False, check=True, capture_output=False)
        print(f"✅ {description or cmd} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description or cmd} failed with exit code {e.returncode}")
        return False


def main():
    """Main test runner."""
    # Define commands and their implementations
    commands = {
        "install": lambda: _run_install_commands(),
        "format": lambda: _run_format_commands(),
        "lint": lambda: _run_lint_commands(),
        "type": lambda: _run_type_commands(),
        "security": lambda: _run_security_commands(),
        "test": lambda: _run_test_commands(),
        "unit": lambda: _run_unit_commands(),
        "integration": lambda: _run_integration_commands(),
        "coverage": lambda: _run_coverage_commands(),
        "quality": lambda: _run_quality_commands(),
        "ci": lambda: _run_ci_commands(),
    }

    if len(sys.argv) < 2:
        print("Usage: python test_runner.py <command>")
        print("\nAvailable commands:")
        for cmd in commands.keys():
            descriptions = {
                "format": "Format code with black and isort",
                "lint": "Run linting checks",
                "type": "Run type checking",
                "security": "Run security scans",
                "test": "Run all tests",
                "unit": "Run unit tests only",
                "integration": "Run integration tests only",
                "coverage": "Run tests with coverage report",
                "quality": "Run all quality checks",
                "ci": "Run full CI pipeline locally",
                "install": "Install development dependencies",
            }
            print(f"  {cmd: <12} - {descriptions.get(cmd, '')}")
        return 1

    command = sys.argv[1].lower()

    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)

    if command not in commands:
        print(f"❌ Unknown command: {command}")
        return 1

    success = commands[command]()
    return 0 if success else 1


def _run_install_commands():
    """Run install commands."""
    success = True
    success &= run_command(
        "pip install -r requirements.txt", "Installing main dependencies"
    )
    success &= run_command(
        "pip install -r dev-requirements.txt",
        "Installing dev dependencies",
    )
    success &= run_command("pre-commit install", "Installing pre-commit hooks")
    return success


def _run_format_commands():
    """Run format commands."""
    success = True
    success &= run_command("black .", "Formatting code with Black")
    success &= run_command("isort .", "Sorting imports with isort")
    return success


def _run_lint_commands():
    """Run lint commands."""
    success = True
    success &= run_command("flake8 .", "Linting with Flake8")
    success &= run_command(
        "pylint core/ tests/ --fail-under=8.0", "Linting with Pylint"
    )
    return success


def _run_type_commands():
    """Run type checking commands."""
    return run_command("mypy core/ --ignore-missing-imports", "Type checking with Mypy")


def _run_security_commands():
    """Run security commands."""
    success = True
    success &= run_command("bandit -r core/", "Security scanning with Bandit")
    success &= run_command("safety check", "Checking for known vulnerabilities")
    return success


def _run_test_commands():
    """Run test commands."""
    return run_command("pytest tests/ -v", "Running all tests")


def _run_unit_commands():
    """Run unit test commands."""
    return run_command("pytest tests/unit/ -v", "Running unit tests")


def _run_integration_commands():
    """Run integration test commands."""
    return run_command("pytest tests/integration/ -v", "Running integration tests")


def _run_coverage_commands():
    """Run coverage commands."""
    return run_command(
        "pytest tests/ --cov=core --cov-report=html "
        "--cov-report=term --cov-report=xml",
        "Running tests with coverage",
    )


def _run_quality_commands():
    """Run quality commands."""
    success = True
    success &= _run_format_commands()
    success &= _run_lint_commands()
    success &= _run_type_commands()
    success &= _run_security_commands()
    return success


def _run_ci_commands():
    """Run CI commands."""
    success = True
    success &= _run_quality_commands()
    success &= _run_test_commands()
    success &= _run_coverage_commands()
    return success


if __name__ == "__main__":
    sys.exit(main())
