"""
Phase 2D — Model Evaluation Metrics

Evaluates LightGBM forecaster against hackathon requirements:
  1. Accuracy: MAE/RMSE + % improvement over baseline
  2. Uncertainty: Prediction interval coverage (% of actuals within [q10, q90])
  3. Fairness: Per-city error breakdown
"""

from typing import Dict, Tuple

import numpy as np
import pandas as pd


def evaluate_accuracy(
    y_true: np.ndarray, y_pred: np.ndarray, baseline_mae: float
) -> Dict[str, float]:
    """
    Calculate point forecast accuracy metrics.

    Args:
        y_true: Actual PM2.5 values
        y_pred: Predicted PM2.5 values (median forecast)
        baseline_mae: MAE from baseline model for comparison

    Returns:
        Dictionary with MAE, RMSE, MAPE, improvement%
    """
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))

    # MAPE (avoid division by zero)
    epsilon = 1e-10
    mape = np.mean(np.abs((y_true - y_pred) / (y_true + epsilon))) * 100

    # Improvement over baseline
    improvement_pct = ((baseline_mae - mae) / baseline_mae) * 100

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2),
        "baseline_mae": round(baseline_mae, 2),
        "improvement_pct": round(improvement_pct, 2),
    }


def evaluate_coverage(
    y_true: np.ndarray, y_lower: np.ndarray, y_upper: np.ndarray
) -> Dict[str, float]:
    """
    Calculate prediction interval coverage.

    Args:
        y_true: Actual PM2.5 values
        y_lower: Lower bound predictions (q=0.10)
        y_upper: Upper bound predictions (q=0.90)

    Returns:
        Dictionary with coverage%, mean_interval_width, calibration_error
    """
    # Count actuals within [lower, upper] interval
    in_interval = (y_true >= y_lower) & (y_true <= y_upper)
    coverage = np.mean(in_interval) * 100

    # Average interval width
    interval_width = np.mean(y_upper - y_lower)

    # Calibration error: target is 84% coverage (92nd - 8th percentile)
    target_coverage = 84.0
    calibration_error = abs(coverage - target_coverage)

    return {
        "coverage_pct": round(coverage, 2),
        "target_coverage_pct": target_coverage,
        "calibration_error": round(calibration_error, 2),
        "mean_interval_width": round(interval_width, 2),
    }


def evaluate_by_city(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_lower: np.ndarray,
    y_upper: np.ndarray,
    city_labels: pd.Series,
) -> Tuple[pd.DataFrame, str]:
    """
    Report errors grouped by city (fairness check).

    Args:
        y_true: Actual PM2.5 values
        y_pred: Predicted PM2.5 values (median)
        y_lower: Lower bound predictions
        y_upper: Upper bound predictions
        city_labels: City name for each sample

    Returns:
        (DataFrame with per-city metrics, name of worst performer)
    """
    results = []

    for city in sorted(city_labels.unique()):
        mask = city_labels == city
        city_true = y_true[mask]
        city_pred = y_pred[mask]
        city_lower = y_lower[mask]
        city_upper = y_upper[mask]

        # Accuracy
        mae = np.mean(np.abs(city_true - city_pred))
        rmse = np.sqrt(np.mean((city_true - city_pred) ** 2))

        # Coverage
        in_interval = (city_true >= city_lower) & (city_true <= city_upper)
        coverage = np.mean(in_interval) * 100

        results.append(
            {
                "city": city,
                "samples": int(mask.sum()),
                "mae": round(mae, 2),
                "rmse": round(rmse, 2),
                "coverage_pct": round(coverage, 2),
            }
        )

    df = pd.DataFrame(results)

    # Identify worst performer (highest MAE)
    worst_city = df.loc[df["mae"].idxmax(), "city"]

    return df, worst_city


def format_evaluation_report(
    overall_metrics: Dict[str, float],
    coverage_metrics: Dict[str, float],
    city_metrics: pd.DataFrame,
    worst_city: str,
    n_samples: int,
) -> str:
    """
    Format all metrics into a human-readable report.

    Args:
        overall_metrics: Output from evaluate_accuracy()
        coverage_metrics: Output from evaluate_coverage()
        city_metrics: DataFrame from evaluate_by_city()
        worst_city: Name of city with highest MAE
        n_samples: Total test samples

    Returns:
        Formatted string report
    """
    lines = [
        "=" * 72,
        "PHASE 2D  —  LIGHTGBM FORECASTING MODEL",
        "=" * 72,
        "",
        "[1/3] Overall Accuracy:",
        f"  MAE  : {overall_metrics['mae']:.2f} µg/m³",
        f"  RMSE : {overall_metrics['rmse']:.2f} µg/m³",
        f"  MAPE : {overall_metrics['mape']:.2f}%",
        f"  Samples: {n_samples:,}",
        "",
        "  Baseline Comparison:",
        f"    Baseline MAE     : {overall_metrics['baseline_mae']:.2f} µg/m³",
        f"    Model MAE        : {overall_metrics['mae']:.2f} µg/m³",
        f"    Improvement      : {overall_metrics['improvement_pct']:.2f}%",
        "",
    ]

    # Success/failure check
    if overall_metrics["improvement_pct"] >= 20.0:
        lines.append(f"  ✅ PASSED: Beat baseline by ≥20%")
    else:
        lines.append(
            f"  ❌ FAILED: Only {overall_metrics['improvement_pct']:.2f}% improvement (need ≥20%)"
        )

    lines += [
        "",
        "[2/3] Uncertainty Quantification:",
        f"  Prediction Interval: [{coverage_metrics['target_coverage_pct']:.0f}% coverage target]",
        f"    Actual Coverage    : {coverage_metrics['coverage_pct']:.2f}%",
        f"    Calibration Error  : {coverage_metrics['calibration_error']:.2f} pp",
        f"    Avg Interval Width : {coverage_metrics['mean_interval_width']:.2f} µg/m³",
        "",
    ]

    # Coverage check
    if 79.0 <= coverage_metrics["coverage_pct"] <= 89.0:
        lines.append(f"  ✅ PASSED: Coverage within acceptable range")
    else:
        lines.append(
            f"  ⚠️  WARNING: Coverage deviation {coverage_metrics['calibration_error']:.2f}pp from target"
        )

    lines += [
        "",
        "[3/3] Fairness by City (per-group errors):",
        "",
    ]

    # Format city table
    for _, row in city_metrics.iterrows():
        worst_marker = " ⚠️ WORST" if row["city"] == worst_city else ""
        lines.append(
            f"  {row['city']:12s}  MAE={row['mae']:6.2f}  RMSE={row['rmse']:6.2f}  "
            f"Coverage={row['coverage_pct']:5.2f}%  (n={row['samples']:,}){worst_marker}"
        )

    lines += [
        "",
        f"  Worst performer: {worst_city}",
        "",
        "=" * 72,
        "[OK] Model evaluation complete.",
        "=" * 72,
    ]

    return "\n".join(lines)
