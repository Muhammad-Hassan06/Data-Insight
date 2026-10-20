"""
Phase 2D — Train Hybrid PM2.5 Forecasting Model (LightGBM + CatBoost Ensemble)

Orchestrates:
  1. Load gold table from DuckDB
  2. Train/test split (80/20 time-based, per-city balanced)
  3. Train 6 quantile models:
     - LightGBM: 3 models (median q=0.50, lower q=0.08, upper q=0.92)
     - CatBoost: 3 models (median q=0.50, lower q=0.08, upper q=0.92)
  4. Generate predictions by averaging LightGBM + CatBoost outputs
  5. Evaluate: accuracy, coverage, fairness
  6. Save: models (6 files) + metrics (JSON)

Final Improvements Applied:
  - Hybrid ensemble: LightGBM + CatBoost averaged predictions
  - Weak features dropped: sensor_count, is_weekend (near-zero importance)
  - Quantiles widened from [0.10, 0.90] to [0.08, 0.92] → 84% interval
  - Season encoding bug fix: "autumn" instead of "fall" → evaluates on full test set
  
Final Performance:
  - MAE: 3.93 µg/m³ (66.29% improvement over 11.65 baseline)
  - Coverage: 83.30% (target 84%, calibration error 0.70pp)
  - Per-city MAE: Karachi 2.03, Islamabad 3.08, Lahore 5.02, Peshawar 5.51
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.model.evaluator import (
    evaluate_accuracy,
    evaluate_by_city,
    evaluate_coverage,
    format_evaluation_report,
)
from src.model.trainer_hybrid import HybridPM25Forecaster
from src.model.utils import load_gold_table, time_based_split

# Paths
RESULTS_DIR = Path("results")
MODELS_DIR = Path("models")  # Will contain hybrid ensemble (6 model files)
BASELINE_METRICS_PATH = RESULTS_DIR / "baseline_metrics.json"
MODEL_METRICS_PATH = RESULTS_DIR / "model_metrics.json"

# Feature columns (exclude metadata, target, and weak features)
# sensor_count and is_weekend dropped — near-zero feature importance
EXCLUDE_COLS = ["row_id", "timestamp_utc", "city", "pm25_ugm3", "any_flagged", "sensor_count", "is_weekend"]


def prepare_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Extract feature matrix X, target y, and city labels.
    Encodes categorical features (season) as numeric.

    Args:
        df: Gold table with all columns

    Returns:
        (X: features, y: target PM2.5, cities: city labels)
    """
    feature_cols = [col for col in df.columns if col not in EXCLUDE_COLS]

    X = df[feature_cols].copy()
    y = df["pm25_ugm3"].copy()
    cities = df["city"].copy()

    # Encode categorical features
    # Season: winter=0, spring=1, summer=2, autumn=3
    if "season" in X.columns:
        season_map = {"winter": 0, "spring": 1, "summer": 2, "autumn": 3}
        X["season"] = X["season"].map(season_map)

    return X, y, cities


def load_baseline_mae() -> float:
    """Load baseline MAE from Phase 2C results."""
    with open(BASELINE_METRICS_PATH, "r") as f:
        baseline = json.load(f)
    return baseline["overall"]["mae"]


def main():
    print("\n" + "=" * 72)
    print("PHASE 2D  —  TRAIN HYBRID FORECASTING MODEL  (LightGBM + CatBoost)")
    print("=" * 72)
    print()

    # -----------------------------------------------------------------
    # Step 1: Load data
    # -----------------------------------------------------------------
    print("[1/6] Loading gold table...")
    df = load_gold_table()
    print(f"  Loaded {len(df):,} rows  |  {df.shape[1]} columns")
    print()

    # -----------------------------------------------------------------
    # Step 2: Train/test split (same as baseline)
    # -----------------------------------------------------------------
    print("[2/6] Creating time-based train/test split (80/20)...")
    train_df, test_df = time_based_split(df, test_size=0.2)
    print(f"  Train: {len(train_df):,} rows")
    print(f"  Test:  {len(test_df):,} rows")
    print()

    # -----------------------------------------------------------------
    # Step 3: Prepare features
    # -----------------------------------------------------------------
    print("[3/6] Preparing feature matrices...")
    X_train, y_train, _ = prepare_features(train_df)
    X_test, y_test, test_cities = prepare_features(test_df)

    print(f"  Features: {X_train.shape[1]} columns")
    print(f"  Feature names: {', '.join(X_train.columns[:5])}... (showing first 5)")
    print()

    # Check for nulls (should be none after Phase 1C + 2A)
    train_nulls = X_train.isnull().sum().sum()
    test_nulls = X_test.isnull().sum().sum()
    if train_nulls > 0 or test_nulls > 0:
        print(f"  ⚠️  WARNING: Found {train_nulls} train nulls, {test_nulls} test nulls")
        print("     Dropping rows with nulls (should not happen if pipeline correct)")
        X_train = X_train.dropna()
        y_train = y_train[X_train.index]
        X_test = X_test.dropna()
        y_test = y_test[X_test.index]
        test_cities = test_cities[X_test.index]
        print()

    # -----------------------------------------------------------------
    # Step 4: Train hybrid ensemble (LightGBM + CatBoost)
    # -----------------------------------------------------------------
    print("[4/6] Training hybrid ensemble (LightGBM + CatBoost)...")
    print("  Quantiles: [0.08, 0.50, 0.92]  (84% prediction interval)")
    forecaster = HybridPM25Forecaster(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=7,
        num_leaves=31,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )

    forecaster.train(X_train, y_train)
    print("  [OK] Hybrid ensemble trained (6 models: 3 LightGBM + 3 CatBoost)")
    print()

    # -----------------------------------------------------------------
    # Step 5: Predict + Evaluate (averaged from both algorithms)
    # -----------------------------------------------------------------
    print("[5/6] Generating hybrid predictions and evaluating...")
    y_pred_median, y_pred_lower, y_pred_upper = forecaster.predict(X_test)

    # Load baseline for comparison
    baseline_mae = load_baseline_mae()

    # Accuracy
    accuracy_metrics = evaluate_accuracy(
        y_true=y_test.values,
        y_pred=y_pred_median,
        baseline_mae=baseline_mae,
    )

    # Uncertainty
    coverage_metrics = evaluate_coverage(
        y_true=y_test.values,
        y_lower=y_pred_lower,
        y_upper=y_pred_upper,
    )

    # Fairness
    city_metrics, worst_city = evaluate_by_city(
        y_true=y_test.values,
        y_pred=y_pred_median,
        y_lower=y_pred_lower,
        y_upper=y_pred_upper,
        city_labels=test_cities,
    )

    print("  [OK] Evaluation complete")
    print()

    # -----------------------------------------------------------------
    # Step 6: Save results
    # -----------------------------------------------------------------
    print("[6/6] Saving models and metrics...")

    # Save models as pickle files
    MODELS_DIR.mkdir(exist_ok=True)
    forecaster.save(MODELS_DIR)

    # Save metrics as JSON
    RESULTS_DIR.mkdir(exist_ok=True)
    metrics_output = {
        "model": "Hybrid Ensemble — LightGBM + CatBoost (averaged)",
        "improvements": [
            "Hybrid ensemble (simple averaging)",
            "Dropped weak features (sensor_count, is_weekend)",
            "Quantiles [0.08,0.92]",
            "Season encoding bug fix"
        ],
        "model_params": {
            "n_estimators": 500,
            "learning_rate": 0.05,
            "max_depth": 7,
            "num_leaves": 31,
            "quantiles": [0.08, 0.50, 0.92],
        },
        "data": {
            "train_samples": len(train_df),
            "test_samples": len(test_df),
            "n_features": X_train.shape[1],
        },
        "accuracy": accuracy_metrics,
        "uncertainty": coverage_metrics,
        "fairness": {
            "worst_city": worst_city,
            "by_city": city_metrics.to_dict(orient="records"),
        },
    }

    with open(MODEL_METRICS_PATH, "w") as f:
        json.dump(metrics_output, f, indent=2)

    print(f"  [SAVED] {MODEL_METRICS_PATH}")
    print()

    # -----------------------------------------------------------------
    # Print formatted report
    # -----------------------------------------------------------------
    report = format_evaluation_report(
        overall_metrics=accuracy_metrics,
        coverage_metrics=coverage_metrics,
        city_metrics=city_metrics,
        worst_city=worst_city,
        n_samples=len(test_df),
    )
    print(report)


if __name__ == "__main__":
    main()
