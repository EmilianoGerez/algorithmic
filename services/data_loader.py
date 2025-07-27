"""
Data loading utilities with production-quality fallback mechanisms.

This module provides streaming data loaders with Polars as primary engine
and Pandas fallback for broader compatibility. Includes validation and
preprocessing for backtesting workflows.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Union

from core.entities import Candle

logger = logging.getLogger(__name__)


def load_market_data(path: str | Path, **kwargs: Any) -> Any:
    """Load market data with graceful fallback from Polars to Pandas.

    This function attempts to use Polars for optimal performance, but gracefully
    falls back to Pandas if Polars is not available, ensuring broad compatibility.

    Args:
        path: Path to data file (CSV or Parquet)
        **kwargs: Additional arguments passed to the loader

    Returns:
        DataFrame (Polars or Pandas) containing market data

    Raises:
        ImportError: If neither Polars nor Pandas is available
        FileNotFoundError: If data file doesn't exist
        ValueError: If data format is invalid
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    # Try Polars first (faster)
    try:
        import polars as pl

        if path.suffix.lower() == ".parquet":
            df = pl.read_parquet(path, **kwargs)
        else:
            df = pl.read_csv(path, **kwargs)

        logger.info(f"Loaded {len(df)} rows using Polars from {path}")
        return df

    except ImportError:
        logger.warning(
            "Polars not available, falling back to Pandas (slower performance)"
        )

        try:
            import pandas as pd
            import polars as pl  # For conversion

            if path.suffix.lower() == ".parquet":
                df_pandas = pd.read_parquet(path, **kwargs)
            else:
                df_pandas = pd.read_csv(path, **kwargs)

            # Convert to Polars for uniform interface
            df = pl.from_pandas(df_pandas)
            logger.info(f"Loaded {len(df)} rows using Pandas fallback from {path}")
            return df

        except ImportError:
            raise ImportError(
                "Neither Polars nor Pandas is available. Please install at least one."
            ) from None

    except Exception as e:
        logger.error(f"Failed to load data from {path}: {e}")
        raise ValueError(f"Invalid data format in {path}: {e}") from e


def validate_market_data(df: Any, config: Any) -> bool:
    """Validate market data structure and content.

    Args:
        df: Market data DataFrame
        config: Data configuration with column mappings

    Returns:
        True if validation passes

    Raises:
        ValueError: If validation fails
    """
    # Check required columns exist
    required_cols = [config.date_column, *config.ohlcv_columns]
    available_cols = df.columns

    missing_cols = set(required_cols) - set(available_cols)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Check data types and ranges
    ohlc_cols = config.ohlcv_columns[:4]  # open, high, low, close

    # Validate OHLC relationships
    df_sample = df.head(1000)  # Check first 1000 rows for performance

    for i, row in enumerate(df_sample.iter_rows(named=True)):
        o, h, low, c = [row[col] for col in ohlc_cols]

        if not (low <= o <= h and low <= c <= h):
            raise ValueError(
                f"Invalid OHLC data at row {i}: O={o}, H={h}, L={low}, C={c}"
            )

        if h < low:
            raise ValueError(f"High < Low at row {i}: H={h}, L={low}")

    logger.info(f"Data validation passed: {len(df)} rows")
    return True


def create_candle_stream(df: Any, config: Any) -> Iterator[Candle]:
    """Create streaming iterator of Candle objects from DataFrame.

    This generator yields Candle objects one at a time for memory-efficient
    processing of large datasets.

    Args:
        df: Market data DataFrame
        config: Data configuration with column mappings

    Yields:
        Candle objects with proper datetime parsing
    """

    date_col = config.date_column
    o_col, h_col, l_col, c_col, v_col = config.ohlcv_columns

    for row in df.iter_rows(named=True):
        # Parse timestamp
        ts_raw = row[date_col]
        if isinstance(ts_raw, str):
            # Try common datetime formats
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                try:
                    ts = datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    ts = datetime.strptime(ts_raw, "%Y-%m-%d")
        else:
            ts = ts_raw  # Assume already datetime

        yield Candle(
            ts=ts,
            open=float(row[o_col]),
            high=float(row[h_col]),
            low=float(row[l_col]),
            close=float(row[c_col]),
            volume=float(row[v_col]),
        )


def create_csv_candle_stream(path: str | Path, config: Any) -> Iterator[Candle]:
    """Memory-efficient CSV streaming without loading full dataset.

    For very large CSV files, this bypasses DataFrame loading entirely
    and streams directly from the CSV file.

    Args:
        path: Path to CSV file
        config: Data configuration

    Yields:
        Candle objects
    """

    with open(path, newline="") as f:
        reader = csv.DictReader(f)

        date_col = config.date_column
        o_col, h_col, l_col, c_col, v_col = config.ohlcv_columns

        for row in reader:
            # Parse timestamp
            ts_raw = row[date_col]
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                try:
                    ts = datetime.strptime(ts_raw, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    ts = datetime.strptime(ts_raw, "%Y-%m-%d")

            yield Candle(
                ts=ts,
                open=float(row[o_col]),
                high=float(row[h_col]),
                low=float(row[l_col]),
                close=float(row[c_col]),
                volume=float(row[v_col]),
            )


class DataLoader:
    """Production-quality data loader with multiple streaming strategies."""

    def __init__(self, config: Any) -> None:
        """Initialize data loader with configuration.

        Args:
            config: Data configuration object
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def load_and_validate(self, path: str | Path) -> Any:
        """Load and validate market data.

        Args:
            path: Path to data file

        Returns:
            Validated DataFrame
        """
        df = load_market_data(path)
        validate_market_data(df, self.config)
        return df

    def create_stream(
        self, path: str | Path, use_csv_stream: bool = False
    ) -> Iterator[Candle]:
        """Create candle stream with optional CSV streaming mode.

        Args:
            path: Path to data file
            use_csv_stream: If True, use direct CSV streaming for large files

        Returns:
            Iterator of Candle objects
        """
        if use_csv_stream and Path(path).suffix.lower() == ".csv":
            self.logger.info(f"Using direct CSV streaming for {path}")
            return create_csv_candle_stream(path, self.config)
        else:
            self.logger.info(f"Loading DataFrame then streaming for {path}")
            df = self.load_and_validate(path)
            return create_candle_stream(df, self.config)

    def get_data_info(self, path: str | Path) -> dict[str, Any]:
        """Get summary information about the dataset.

        Args:
            path: Path to data file

        Returns:
            Dictionary with data summary statistics
        """
        df = self.load_and_validate(path)

        date_col = self.config.date_column
        close_col = self.config.ohlcv_columns[3]  # close

        return {
            "total_rows": len(df),
            "date_range": {
                "start": df[date_col].min(),
                "end": df[date_col].max(),
            },
            "price_range": {
                "min": df[close_col].min(),
                "max": df[close_col].max(),
            },
            "file_size_mb": Path(path).stat().st_size / (1024 * 1024),
        }

    def split_into_folds(
        self, path: str | Path, n_folds: int, train_fraction: float = 0.5
    ) -> list[tuple[Any, Any]]:
        """Split dataset into walk-forward folds.

        Args:
            path: Path to data file
            n_folds: Number of folds for walk-forward analysis
            train_fraction: Fraction of each fold used for training

        Returns:
            List of (train_df, test_df) tuples for each fold
        """
        self.logger.info(
            f"Creating {n_folds} walk-forward folds with {train_fraction:.1%} training data"
        )

        # Load full dataset
        df = self.load_and_validate(path)

        # Sort by date to ensure chronological order
        date_col = self.config.date_column
        df = df.sort(date_col)

        total_rows = len(df)
        fold_size = total_rows // n_folds

        folds = []

        for i in range(n_folds):
            # Calculate fold boundaries
            fold_start = i * fold_size
            fold_end = min((i + 1) * fold_size, total_rows)

            if fold_end - fold_start < 100:  # Skip very small folds
                self.logger.warning(
                    f"Skipping fold {i + 1} - too small ({fold_end - fold_start} rows)"
                )
                continue

            # Get fold data
            fold_data = df[fold_start:fold_end]

            # Split into train/test
            fold_rows = len(fold_data)
            train_size = int(fold_rows * train_fraction)

            if train_size < 50 or (fold_rows - train_size) < 20:
                self.logger.warning(
                    f"Skipping fold {i + 1} - insufficient train/test data"
                )
                continue

            train_data = fold_data[:train_size]
            test_data = fold_data[train_size:]

            folds.append((train_data, test_data))

            self.logger.info(
                f"Fold {i + 1}: {len(train_data)} train, {len(test_data)} test rows"
            )

        self.logger.info(f"Created {len(folds)} valid walk-forward folds")
        return folds
