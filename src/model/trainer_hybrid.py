"""
Hybrid PM2.5 Forecaster — LightGBM + CatBoost Ensemble

Combines two gradient boosting algorithms via simple averaging:
  - LightGBM (histogram-based, fast training)
  - CatBoost (ordered boosting, native categorical handling)

Each algorithm trains 3 quantile models (q=0.08, 0.50, 0.92).
Final predictions are the average of both algorithms' outputs.

This reduces variance and often improves MAE by 2-4% over single models.
"""

import pickle
from pathlib import Path
from typing import Tuple

import lightgbm as lgb
import catboost as cb
import numpy as np
import pandas as pd


class HybridPM25Forecaster:
    """LightGBM + CatBoost hybrid ensemble with quantile regression."""

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
        Initialize hybrid ensemble parameters.

        Args:
            n_estimators: Number of boosting rounds
            learning_rate: Shrinkage rate
            max_depth: Maximum tree depth
            num_leaves: Max leaves per tree (LightGBM only)
            min_child_samples: Minimum samples per leaf
            subsample: Row sampling fraction
            colsample_bytree: Column sampling fraction
            random_state: Seed for reproducibility
        """
        self.params = {
            "n_estimators": n_estimators,
            "learning_rate": learning_rate,
            "max_depth": max_depth,
            "num_leaves": num_leaves,
            "min_child_samples": min_child_samples,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "random_state": random_state,
        }

        # LightGBM models
        self.lgb_median = None
        self.lgb_lower = None
        self.lgb_upper = None

        # CatBoost models
        self.cb_median = None
        self.cb_lower = None
        self.cb_upper = None

        self.feature_names = None
        self.cat_features = None  # Categorical feature indices for CatBoost

    def train(
        self, X_train: pd.DataFrame, y_train: pd.Series
    ) -> dict:
        """
        Train both LightGBM and CatBoost quantile models.

        Args:
            X_train: Feature matrix (season should be numeric for LightGBM, will be converted for CatBoost)
            y_train: Target PM2.5 values

        Returns:
            Dictionary with both sets of models
        """
        self.feature_names = list(X_train.columns)

        # Identify categorical features
        self.cat_features = ["season"] if "season" in X_train.columns else []

        # ================================================================
        # LIGHTGBM (expects numeric season)
        # ================================================================
        print("  [HYBRID] Training LightGBM...")

        lgb_params = {
            "objective": "quantile",
            "metric": "quantile",
            "boosting_type": "gbdt",
            **self.params,
            "verbosity": -1,
            "force_col_wise": True,
        }

        print("    [LGB] Median (q=0.50)...")
        self.lgb_median = lgb.LGBMRegressor(**{**lgb_params, "alpha": 0.50})
        self.lgb_median.fit(X_train, y_train)

        print("    [LGB] Lower (q=0.08)...")
        self.lgb_lower = lgb.LGBMRegressor(**{**lgb_params, "alpha": 0.08})
        self.lgb_lower.fit(X_train, y_train)

        print("    [LGB] Upper (q=0.92)...")
        self.lgb_upper = lgb.LGBMRegressor(**{**lgb_params, "alpha": 0.92})
        self.lgb_upper.fit(X_train, y_train)

        # ================================================================
        # CATBOOST (convert season to string)
        # ================================================================
        print("  [HYBRID] Training CatBoost...")

        X_train_cat = X_train.copy()
        if self.cat_features:
            for col in self.cat_features:
                X_train_cat[col] = X_train_cat[col].astype(str)

        cb_params = {
            "iterations": self.params["n_estimators"],
            "learning_rate": self.params["learning_rate"],
            "depth": self.params["max_depth"],
            "random_state": self.params["random_state"],
            "verbose": False,
        }

        print("    [CB] Median (q=0.50)...")
        self.cb_median = cb.CatBoostRegressor(
            loss_function="Quantile:alpha=0.50",
            **cb_params,
            cat_features=self.cat_features if self.cat_features else None,
        )
        self.cb_median.fit(X_train_cat, y_train, verbose=False)

        print("    [CB] Lower (q=0.08)...")
        self.cb_lower = cb.CatBoostRegressor(
            loss_function="Quantile:alpha=0.08",
            **cb_params,
            cat_features=self.cat_features if self.cat_features else None,
        )
        self.cb_lower.fit(X_train_cat, y_train, verbose=False)

        print("    [CB] Upper (q=0.92)...")
        self.cb_upper = cb.CatBoostRegressor(
            loss_function="Quantile:alpha=0.92",
            **cb_params,
            cat_features=self.cat_features if self.cat_features else None,
        )
        self.cb_upper.fit(X_train_cat, y_train, verbose=False)

        return {
            "lightgbm": {
                "median": self.lgb_median,
                "lower": self.lgb_lower,
                "upper": self.lgb_upper,
            },
            "catboost": {
                "median": self.cb_median,
                "lower": self.cb_lower,
                "upper": self.cb_upper,
            },
        }

    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate hybrid predictions by averaging LightGBM and CatBoost outputs.

        Args:
            X: Feature matrix (same columns as training, season numeric)

        Returns:
            (median_predictions, lower_bound, upper_bound) — averaged from both models
        """
        if self.lgb_median is None or self.cb_median is None:
            raise ValueError("Models not trained. Call train() first.")

        # LightGBM predictions (expects numeric season)
        lgb_median = self.lgb_median.predict(X)
        lgb_lower = self.lgb_lower.predict(X)
        lgb_upper = self.lgb_upper.predict(X)

        # CatBoost predictions (convert season to string)
        X_cat = X.copy()
        if self.cat_features:
            for col in self.cat_features:
                X_cat[col] = X_cat[col].astype(str)

        cb_median = self.cb_median.predict(X_cat)
        cb_lower = self.cb_lower.predict(X_cat)
        cb_upper = self.cb_upper.predict(X_cat)

        # Average predictions from both models
        pred_median = (lgb_median + cb_median) / 2
        pred_lower = (lgb_lower + cb_lower) / 2
        pred_upper = (lgb_upper + cb_upper) / 2

        return pred_median, pred_lower, pred_upper

    def save(self, output_dir: Path) -> None:
        """
        Save all 6 models (3 LightGBM + 3 CatBoost) to disk.

        Args:
            output_dir: Directory to save models (will be created if missing)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save LightGBM models
        for name, model in [
            ("lgb_median", self.lgb_median),
            ("lgb_lower", self.lgb_lower),
            ("lgb_upper", self.lgb_upper),
        ]:
            path = output_dir / f"{name}.pkl"
            with open(path, "wb") as f:
                pickle.dump(model, f)
            print(f"  [SAVED] {path}")

        # Save CatBoost models
        for name, model in [
            ("cb_median", self.cb_median),
            ("cb_lower", self.cb_lower),
            ("cb_upper", self.cb_upper),
        ]:
            path = output_dir / f"{name}.cbm"
            model.save_model(str(path))
            print(f"  [SAVED] {path}")

        # Save metadata
        meta_path = output_dir / "hybrid_meta.pkl"
        with open(meta_path, "wb") as f:
            pickle.dump(
                {
                    "feature_names": self.feature_names,
                    "cat_features": self.cat_features,
                },
                f,
            )
        print(f"  [SAVED] {meta_path}")

    @classmethod
    def load(cls, output_dir: Path) -> "HybridPM25Forecaster":
        """
        Load saved hybrid ensemble from disk.

        Args:
            output_dir: Directory containing saved models

        Returns:
            HybridPM25Forecaster instance with loaded models
        """
        forecaster = cls()

        # Load LightGBM models
        for name in ["lgb_median", "lgb_lower", "lgb_upper"]:
            path = output_dir / f"{name}.pkl"
            with open(path, "rb") as f:
                model = pickle.load(f)
                setattr(forecaster, name, model)

        # Load CatBoost models
        for name in ["cb_median", "cb_lower", "cb_upper"]:
            path = output_dir / f"{name}.cbm"
            model = cb.CatBoostRegressor()
            model.load_model(str(path))
            setattr(forecaster, name, model)

        # Load metadata
        meta_path = output_dir / "hybrid_meta.pkl"
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)
            forecaster.feature_names = meta["feature_names"]
            forecaster.cat_features = meta["cat_features"]

        return forecaster
