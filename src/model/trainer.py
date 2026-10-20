
"""
Phase 2D — PM2.5 Forecaster with Uncertainty Quantification

Trains 3 LightGBM models using quantile regression:
  - Median (q=0.50): point forecast
  - Lower bound (q=0.10): 10th percentile
  - Upper bound (q=0.90): 90th percentile

This provides 80% prediction intervals (90% - 10% = 80% coverage target).
"""

import pickle
from pathlib import Path
from typing import Dict, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd


class PM25Forecaster:
    """LightGBM quantile regression forecaster for PM2.5 with uncertainty."""

    def __init__(
        self,
        n_estimators: int = 500,
        learning_rate: float = 0.05,
        max_depth: int = 7,
        num_leaves: int = 31,
        min_child_samples: int = 20,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        random_state: int = 42,
    ):
        """
        Initialize three quantile regressors.

        Args:
            n_estimators: Number of boosting rounds
            learning_rate: Shrinkage rate
            max_depth: Maximum tree depth
            num_leaves: Max leaves per tree
            min_child_samples: Minimum samples per leaf
            subsample: Row sampling fraction
            colsample_bytree: Column sampling fraction
            random_state: Seed for reproducibility
        """
        self.params = {
            "objective": "quantile",
            "metric": "quantile",
            "boosting_type": "gbdt",
            "n_estimators": n_estimators,
            "learning_rate": learning_rate,
            "max_depth": max_depth,
            "num_leaves": num_leaves,
            "min_child_samples": min_child_samples,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "random_state": random_state,
            "verbosity": -1,
            "force_col_wise": True,
        }

        # Three models for median + 80% interval
        self.model_median = None  # q=0.50
        self.model_lower = None  # q=0.10
        self.model_upper = None  # q=0.90

        self.feature_names = None

    def train(
        self, X_train: pd.DataFrame, y_train: pd.Series
    ) -> Dict[str, lgb.Booster]:
        """
        Train three quantile models on the same training data.

        Args:
            X_train: Feature matrix (exclude timestamp, city_name, pm25)
            y_train: Target PM2.5 values

        Returns:
            Dictionary of trained models {median, lower, upper}
        """
        self.feature_names = list(X_train.columns)

        print("  [TRAIN] Training median model (q=0.50)...")
        params_median = {**self.params, "alpha": 0.50}
        self.model_median = lgb.LGBMRegressor(**params_median)
        self.model_median.fit(X_train, y_train)

        print("  [TRAIN] Training lower bound (q=0.10)...")
        params_lower = {**self.params, "alpha": 0.10}
        self.model_lower = lgb.LGBMRegressor(**params_lower)
        self.model_lower.fit(X_train, y_train)

        print("  [TRAIN] Training upper bound (q=0.90)...")
        params_upper = {**self.params, "alpha": 0.90}
        self.model_upper = lgb.LGBMRegressor(**params_upper)
        self.model_upper.fit(X_train, y_train)

        return {
            "median": self.model_median,
            "lower": self.model_lower,
            "upper": self.model_upper,
        }

    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate point forecast + prediction interval.

        Args:
            X: Feature matrix (same columns as training)

        Returns:
            (median_predictions, lower_bound, upper_bound)
        """
        if self.model_median is None:
            raise ValueError("Models not trained. Call train() first.")

        pred_median = self.model_median.predict(X)
        pred_lower = self.model_lower.predict(X)
        pred_upper = self.model_upper.predict(X)

        return pred_median, pred_lower, pred_upper

    def save(self, output_dir: Path) -> None:
        """
        Save all three models to disk as pickle files.

        Args:
            output_dir: Directory to save models (will be created if missing)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        for name, model in [
            ("median", self.model_median),
            ("lower", self.model_lower),
            ("upper", self.model_upper),
        ]:
            path = output_dir / f"pm25_forecaster_{name}.pkl"
            with open(path, "wb") as f:
                pickle.dump(model, f)
            print(f"  [SAVED] {path}")

        # Save feature names for inference
        feature_path = output_dir / "feature_names.pkl"
        with open(feature_path, "wb") as f:
            pickle.dump(self.feature_names, f)
        print(f"  [SAVED] {feature_path}")

    @classmethod
    def load(cls, output_dir: Path) -> "PM25Forecaster":
        """
        Load saved models from disk.

        Args:
            output_dir: Directory containing saved models

        Returns:
            PM25Forecaster instance with loaded models
        """
        forecaster = cls()

        for name in ["median", "lower", "upper"]:
            path = output_dir / f"pm25_forecaster_{name}.pkl"
            with open(path, "rb") as f:
                model = pickle.load(f)
                setattr(forecaster, f"model_{name}", model)

        feature_path = output_dir / "feature_names.pkl"
        with open(feature_path, "rb") as f:
            forecaster.feature_names = pickle.load(f)

        return forecaster
