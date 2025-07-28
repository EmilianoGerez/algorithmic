#!/usr/bin/env python3
"""
Script to validate CSV data files for backtesting compatibility.
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def validate_csv_format(filepath: str) -> bool:
    """
    Validate that a CSV file has the correct format for backtesting.

    Args:
        filepath: Path to the CSV file

    Returns:
        True if valid, False otherwise
    """
    required_columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "trade_count",
    ]

    if not Path(filepath).exists():
        print(f"Error: File {filepath} does not exist")
        return False

    try:
        with open(filepath) as file:
            reader = csv.DictReader(file)

            # Check headers
            if not reader.fieldnames:
                print("Error: File has no headers")
                return False

            missing_columns = set(required_columns) - set(reader.fieldnames)
            if missing_columns:
                print(f"Error: Missing required columns: {missing_columns}")
                return False

            extra_columns = set(reader.fieldnames) - set(required_columns)
            if extra_columns:
                print(f"Warning: Extra columns found: {extra_columns}")

            # Validate data rows
            row_count = 0
            errors = []

            for i, row in enumerate(reader, 1):
                row_count += 1

                # Validate timestamp
                try:
                    datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                except ValueError:
                    errors.append(
                        f"Row {i}: Invalid timestamp format: {row['timestamp']}"
                    )

                # Validate numeric fields
                numeric_fields = [
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "vwap",
                    "trade_count",
                ]
                for field in numeric_fields:
                    try:
                        float(row[field])
                    except ValueError:
                        errors.append(f"Row {i}: Invalid {field} value: {row[field]}")

                # Basic OHLC validation
                try:
                    open_price, high_price, low_price, close_price = (
                        float(row["open"]),
                        float(row["high"]),
                        float(row["low"]),
                        float(row["close"]),
                    )
                    if not (
                        low_price <= open_price <= high_price
                        and low_price <= close_price <= high_price
                    ):
                        errors.append(
                            f"Row {i}: Invalid OHLC relationship (O:{open_price}, H:{high_price}, L:{low_price}, C:{close_price})"
                        )
                except ValueError:
                    pass  # Already caught above

                # Stop after first 10 errors to avoid spam
                if len(errors) >= 10:
                    break

            if errors:
                print(f"Found {len(errors)} validation errors:")
                for error in errors:
                    print(f"  {error}")
                if len(errors) >= 10:
                    print("  ... (showing first 10 errors)")
                return False

            print("✓ File validation passed")
            print(f"  Rows: {row_count}")
            print(f"  Columns: {', '.join(reader.fieldnames)}")
            return True

    except Exception as e:
        print(f"Error reading file: {e}")
        return False


def get_data_summary(filepath: str) -> dict[str, str | int] | None:
    """
    Get summary statistics for a data file.

    Args:
        filepath: Path to the CSV file

    Returns:
        Dictionary with summary stats or None if error
    """
    try:
        with open(filepath) as file:
            reader = csv.DictReader(file)

            rows = list(reader)
            if not rows:
                return None

            # Get time range
            first_timestamp = rows[0]["timestamp"]
            last_timestamp = rows[-1]["timestamp"]

            # Get price range
            closes = [float(row["close"]) for row in rows]
            highs = [float(row["high"]) for row in rows]
            lows = [float(row["low"]) for row in rows]
            volumes = [float(row["volume"]) for row in rows]

            return {
                "total_rows": len(rows),
                "time_range": f"{first_timestamp} to {last_timestamp}",
                "price_range": f"${min(lows):.2f} - ${max(highs):.2f}",
                "avg_close": f"${sum(closes) / len(closes):.2f}",
                "total_volume": f"{sum(volumes):.6f}",
                "avg_volume": f"{sum(volumes) / len(volumes):.6f}",
            }

    except Exception as e:
        print(f"Error generating summary: {e}")
        return None


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Validate CSV data files for backtesting"
    )

    parser.add_argument("files", nargs="+", help="CSV files to validate")

    parser.add_argument(
        "--summary", action="store_true", help="Show data summary statistics"
    )

    args = parser.parse_args()

    all_valid = True

    for filepath in args.files:
        print(f"\nValidating: {filepath}")
        print("=" * 50)

        is_valid = validate_csv_format(filepath)
        all_valid = all_valid and is_valid

        if is_valid and args.summary:
            summary = get_data_summary(filepath)
            if summary:
                print("\nData Summary:")
                for key, value in summary.items():
                    print(f"  {key.replace('_', ' ').title()}: {value}")

    if not all_valid:
        print("\n❌ Some files failed validation")
        sys.exit(1)
    else:
        print("\n✅ All files passed validation")


if __name__ == "__main__":
    main()
