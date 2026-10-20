"""
Module: utils
Location: src/model/utils.py
Purpose: Shared utilities for model training and evaluation.
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple


PROJECT_ROOT = Path(__file__).parent.parent.parent
PROCESSED_DB = PROJECT_ROOT / "data" / "processed" / "warehouse.duckdb"


def load_gold_table() -> pd.DataFrame:
    """
    Load the gold_forecast_features table from DuckDB.
    
    Returns sorted by (city, timestamp_utc) with timezone-aware timestamps.
    """
    con = duckdb.connect(str(PROCESSED_DB), read_only=True)
    df = con.execute("SELECT * FROM gold_forecast_features ORDER BY city, timestamp_utc").df()
    con.close()
    
    # Ensure timestamp is tz-aware
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    
    return df


def time_based_split(
    df: pd.DataFrame,
    test_size: float = 0.2,
    by_city: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split data by time (not random) to prevent data leakage.
    
    Args:
        df: Gold table DataFrame, must be sorted by timestamp
        test_size: Fraction of data to use for test (default 0.2 = 20%)
        by_city: If True, split each city independently to ensure balanced test set
        
    Returns:
        (train_df, test_df)
    """
    if by_city:
        train_parts = []
        test_parts = []
        
        for city in df["city"].unique():
            city_df = df[df["city"] == city].sort_values("timestamp_utc")
            split_idx = int(len(city_df) * (1 - test_size))
            train_parts.append(city_df.iloc[:split_idx])
            test_parts.append(city_df.iloc[split_idx:])
        
        train = pd.concat(train_parts, ignore_index=True)
        test = pd.concat(test_parts, ignore_index=True)
    else:
        # Global split (not recommended — can create city imbalance)
        split_idx = int(len(df) * (1 - test_size))
        train = df.iloc[:split_idx]
        test = df.iloc[split_idx:]
    
    return train, test


def calculate_mae(y_true: pd.Series, y_pred: pd.Series) -> float:
    """
    Calculate Mean Absolute Error.
    
    Handles NaN in predictions by excluding those rows from the calculation.
    """
    mask = ~(pd.isna(y_true) | pd.isna(y_pred))
    if mask.sum() == 0:
        return np.nan
    return np.mean(np.abs(y_true[mask] - y_pred[mask]))


def calculate_rmse(y_true: pd.Series, y_pred: pd.Series) -> float:
    """Calculate Root Mean Squared Error."""
    mask = ~(pd.isna(y_true) | pd.isna(y_pred))
    if mask.sum() == 0:
        return np.nan
    return np.sqrt(np.mean((y_true[mask] - y_pred[mask]) ** 2))


def calculate_mape(y_true: pd.Series, y_pred: pd.Series, epsilon: float = 1e-10) -> float:
    """
    Calculate Mean Absolute Percentage Error.
    
    Adds epsilon to denominator to avoid division by zero.
    """
    mask = ~(pd.isna(y_true) | pd.isna(y_pred))
    if mask.sum() == 0:
        return np.nan
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / (y_true[mask] + epsilon))) * 100


def evaluate_by_city(
    df: pd.DataFrame,
    y_true_col: str,
    y_pred_col: str,
) -> pd.DataFrame:
    """
    Calculate MAE for each city separately.
    
    Returns a DataFrame with columns: city, mae, rmse, count
    """
    results = []
    for city in df["city"].unique():
        city_df = df[df["city"] == city]
        y_true = city_df[y_true_col]
        y_pred = city_df[y_pred_col]
        
        results.append({
            "city": city,
            "mae": calculate_mae(y_true, y_pred),
            "rmse": calculate_rmse(y_true, y_pred),
            "count": len(city_df),
        })
    
    return pd.DataFrame(results).sort_values("city")
