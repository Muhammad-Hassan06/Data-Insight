"""
Module: baseline
Location: src/model/baseline.py
Purpose: Persistence baseline model for PM2.5 forecasting.

Baseline: y(t) = y(t - 24h)
    "Tomorrow's PM2.5 at hour H equals today's PM2.5 at hour H"

This is the simplest reasonable forecast for cyclical data with strong
daily patterns. The model must beat this baseline by ≥20% MAE to demonstrate
genuine predictive skill.
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

from src.model.utils import (
    load_gold_table,
    time_based_split,
    calculate_mae,
    calculate_rmse,
    calculate_mape,
    evaluate_by_city,
)


PROJECT_ROOT = Path(__file__).parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"


class PersistenceBaseline:
    """
    Naive baseline: predict y(t) = y(t - 24h).
    
    Uses pm25_lag_24h feature directly as the prediction.
    """
    
    def __init__(self):
        self.name = "PersistenceBaseline"
    
    def predict(self, X: pd.DataFrame) -> pd.Series:
        """
        Return the 24-hour lag as the prediction.
        
        Args:
            X: DataFrame with pm25_lag_24h column
            
        Returns:
            Series of predictions (same index as X)
        """
        if "pm25_lag_24h" not in X.columns:
            raise ValueError("pm25_lag_24h column not found in input DataFrame")
        
        return X["pm25_lag_24h"]
    
    def evaluate(self, test_df: pd.DataFrame) -> dict:
        """
        Evaluate baseline on the test set.
        
        Args:
            test_df: Test DataFrame with columns: pm25_ugm3 (target), pm25_lag_24h
            
        Returns:
            Dict with overall and per-city metrics
        """
        y_true = test_df["pm25_ugm3"]
        y_pred = self.predict(test_df)
        
        # Overall metrics
        overall_mae = calculate_mae(y_true, y_pred)
        overall_rmse = calculate_rmse(y_true, y_pred)
        overall_mape = calculate_mape(y_true, y_pred)
        
        # Per-city breakdown
        test_df_copy = test_df.copy()
        test_df_copy["y_pred"] = y_pred
        by_city = evaluate_by_city(test_df_copy, "pm25_ugm3", "y_pred")
        
        return {
            "model": self.name,
            "overall": {
                "mae": float(overall_mae),
                "rmse": float(overall_rmse),
                "mape": float(overall_mape),
                "test_samples": int(len(test_df)),
            },
            "by_city": by_city.to_dict(orient="records"),
        }


def main():
    """Train and evaluate the persistence baseline."""
    
    print("=" * 72)
    print("PHASE 2C  —  BASELINE MODEL")
    print("=" * 72)
    
    # 1. Load data
    print("\n[1/4] Loading gold table...")
    df = load_gold_table()
    print(f"  Loaded {len(df):,} rows")
    
    # 2. Time-based split
    print("\n[2/4] Creating time-based train/test split (80/20)...")
    train, test = time_based_split(df, test_size=0.2, by_city=True)
    print(f"  Train: {len(train):,} rows")
    print(f"  Test:  {len(test):,} rows")
    
    # Show date ranges
    print(f"\n  Train date range:")
    for city in sorted(train["city"].unique()):
        city_train = train[train["city"] == city]
        print(f"    {city:<12} {city_train['timestamp_utc'].min()} → {city_train['timestamp_utc'].max()}")
    
    print(f"\n  Test date range:")
    for city in sorted(test["city"].unique()):
        city_test = test[test["city"] == city]
        print(f"    {city:<12} {city_test['timestamp_utc'].min()} → {city_test['timestamp_utc'].max()}")
    
    # 3. Evaluate baseline
    print("\n[3/4] Evaluating persistence baseline (y[t] = y[t-24h])...")
    baseline = PersistenceBaseline()
    results = baseline.evaluate(test)
    
    # 4. Print results
    print("\n[4/4] Baseline Results:")
    print(f"\n  Overall Metrics:")
    print(f"    MAE  : {results['overall']['mae']:.2f} µg/m³")
    print(f"    RMSE : {results['overall']['rmse']:.2f} µg/m³")
    print(f"    MAPE : {results['overall']['mape']:.2f}%")
    print(f"    Samples: {results['overall']['test_samples']:,}")
    
    print(f"\n  Per-City MAE:")
    for city_result in results["by_city"]:
        city = city_result["city"]
        mae = city_result["mae"]
        count = city_result["count"]
        print(f"    {city:<12} {mae:6.2f} µg/m³  ({count:,} samples)")
    
    # Identify worst city
    worst_city = max(results["by_city"], key=lambda x: x["mae"])
    print(f"\n  Worst performer: {worst_city['city']} (MAE={worst_city['mae']:.2f})")
    
    # 5. Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "baseline_metrics.json"
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n  [SAVED] {output_path}")
    
    print("\n" + "=" * 72)
    print("[OK] Baseline evaluation complete.")
    print(f"     Target for model: MAE < {results['overall']['mae'] * 0.8:.2f} µg/m³")
    print(f"     (20% improvement required)")
    print("=" * 72)


if __name__ == "__main__":
    main()
