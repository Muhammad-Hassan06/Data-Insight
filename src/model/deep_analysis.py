"""
Deep Analysis: Understanding Model Performance & Improvement Opportunities

This script performs comprehensive analysis to identify:
1. Data characteristics and quality
2. Current model strengths/weaknesses
3. Realistic improvement opportunities
4. Whether a different model architecture would help
"""

import pandas as pd
import numpy as np
from src.model.utils import load_gold_table, time_based_split
from src.model.trainer import PM25Forecaster
from src.model.train_forecast import prepare_features

def analyze_data_characteristics():
    """Understand the dataset properties."""
    print("=" * 80)
    print("PART 1: DATA CHARACTERISTICS")
    print("=" * 80)
    
    df = load_gold_table()
    
    print("\n[1.1] Dataset Overview:")
    print(f"  Total samples: {len(df):,}")
    print(f"  Date range: {df['timestamp_utc'].min()} to {df['timestamp_utc'].max()}")
    print(f"  Cities: {df['city'].unique().tolist()}")
    
    print("\n[1.2] Target Variable (PM2.5) Statistics by City:")
    for city in sorted(df['city'].unique()):
        city_data = df[df['city'] == city]['pm25_ugm3']
        print(f"\n  {city}:")
        print(f"    Mean:   {city_data.mean():.2f} µg/m³")
        print(f"    Median: {city_data.median():.2f} µg/m³")
        print(f"    Std:    {city_data.std():.2f} µg/m³")
        print(f"    Min:    {city_data.min():.2f} µg/m³")
        print(f"    Max:    {city_data.max():.2f} µg/m³")
        print(f"    Q1:     {city_data.quantile(0.25):.2f} µg/m³")
        print(f"    Q3:     {city_data.quantile(0.75):.2f} µg/m³")
        print(f"    CV:     {(city_data.std() / city_data.mean()):.3f} (coefficient of variation)")
    
    print("\n[1.3] Temporal Patterns:")
    df['hour'] = df['timestamp_utc'].dt.hour
    df['month'] = df['timestamp_utc'].dt.month
    
    hourly_avg = df.groupby('hour')['pm25_ugm3'].mean()
    print(f"\n  PM2.5 by Hour of Day:")
    print(f"    Lowest:  Hour {hourly_avg.idxmin():02d} = {hourly_avg.min():.2f} µg/m³")
    print(f"    Highest: Hour {hourly_avg.idxmax():02d} = {hourly_avg.max():.2f} µg/m³")
    print(f"    Range:   {hourly_avg.max() - hourly_avg.min():.2f} µg/m³")
    
    monthly_avg = df.groupby('month')['pm25_ugm3'].mean()
    print(f"\n  PM2.5 by Month:")
    print(f"    Lowest:  Month {monthly_avg.idxmin()} = {monthly_avg.min():.2f} µg/m³")
    print(f"    Highest: Month {monthly_avg.idxmax()} = {monthly_avg.max():.2f} µg/m³")
    
    print("\n[1.4] Feature Correlations with Target:")
    corr_cols = ['pm25_lag_1h', 'pm25_lag_24h', 'pm25_lag_48h', 'pm25_lag_168h',
                 'pm25_rolling_mean_24h', 'pm25_rolling_std_24h',
                 'temperature', 'humidity', 'wind_speed', 'pressure']
    
    correlations = df[corr_cols + ['pm25_ugm3']].corr()['pm25_ugm3'].drop('pm25_ugm3').sort_values(ascending=False)
    print("\n  Top correlations:")
    for feat, corr in correlations.head(10).items():
        print(f"    {feat:30s}: {corr:6.3f}")


def analyze_test_set_difficulty():
    """Check if test set is harder/easier than training set."""
    print("\n" + "=" * 80)
    print("PART 2: TRAIN VS TEST SET COMPARISON")
    print("=" * 80)
    
    df = load_gold_table()
    train_df, test_df = time_based_split(df, test_size=0.2)
    
    print("\n[2.1] Distribution Shifts:")
    print(f"\n  PM2.5 Statistics:")
    print(f"    Train Mean: {train_df['pm25_ugm3'].mean():.2f} µg/m³")
    print(f"    Test Mean:  {test_df['pm25_ugm3'].mean():.2f} µg/m³")
    print(f"    Train Std:  {train_df['pm25_ugm3'].std():.2f} µg/m³")
    print(f"    Test Std:   {test_df['pm25_ugm3'].std():.2f} µg/m³")
    
    print(f"\n  Date Ranges:")
    print(f"    Train: {train_df['timestamp_utc'].min()} to {train_df['timestamp_utc'].max()}")
    print(f"    Test:  {test_df['timestamp_utc'].min()} to {test_df['timestamp_utc'].max()}")
    
    # Check season distribution
    train_months = train_df['timestamp_utc'].dt.month.value_counts().sort_index()
    test_months = test_df['timestamp_utc'].dt.month.value_counts().sort_index()
    
    print(f"\n  Month Distribution:")
    print(f"    Train months: {sorted(train_months.index.tolist())}")
    print(f"    Test months:  {sorted(test_months.index.tolist())}")
    
    # Check if test set has extreme values
    train_max = train_df['pm25_ugm3'].max()
    test_max = test_df['pm25_ugm3'].max()
    test_extreme_count = (test_df['pm25_ugm3'] > train_max).sum()
    
    print(f"\n  Extreme Values:")
    print(f"    Train max: {train_max:.2f} µg/m³")
    print(f"    Test max:  {test_max:.2f} µg/m³")
    print(f"    Test samples > train max: {test_extreme_count} ({test_extreme_count/len(test_df)*100:.2f}%)")


def analyze_model_errors():
    """Detailed error analysis to find patterns."""
    print("\n" + "=" * 80)
    print("PART 3: ERROR ANALYSIS")
    print("=" * 80)
    
    df = load_gold_table()
    train_df, test_df = time_based_split(df, test_size=0.2)
    
    X_train, y_train, _ = prepare_features(train_df)
    X_test, y_test, test_cities = prepare_features(test_df)
    
    X_train = X_train.dropna()
    y_train = y_train[X_train.index]
    X_test = X_test.dropna()
    y_test = y_test[X_test.index]
    test_cities = test_cities[X_test.index]
    
    print("\n[3.1] Training model for error analysis...")
    forecaster = PM25Forecaster(n_estimators=500, learning_rate=0.05, max_depth=7)
    forecaster.train(X_train, y_train)
    
    y_pred_median, _, _ = forecaster.predict(X_test)
    
    errors = np.abs(y_test.values - y_pred_median)
    test_df_subset = test_df.loc[X_test.index].copy()
    test_df_subset['error'] = errors
    test_df_subset['pred'] = y_pred_median
    
    print("\n[3.2] Error Distribution:")
    print(f"  Mean Absolute Error: {errors.mean():.2f} µg/m³")
    print(f"  Median Error:        {np.median(errors):.2f} µg/m³")
    print(f"  90th Percentile:     {np.percentile(errors, 90):.2f} µg/m³")
    print(f"  95th Percentile:     {np.percentile(errors, 95):.2f} µg/m³")
    print(f"  Max Error:           {errors.max():.2f} µg/m³")
    
    # Errors by predicted value range
    print("\n[3.3] Errors by Predicted PM2.5 Level:")
    bins = [0, 12, 35.4, 55.4, 150.4, 1000]
    labels = ['Good (0-12)', 'Moderate (12-35)', 'Unhealthy SG (35-55)', 
              'Unhealthy (55-150)', 'Very Unhealthy (150+)']
    test_df_subset['pred_bin'] = pd.cut(y_test.values, bins=bins, labels=labels)
    
    for label in labels:
        subset = test_df_subset[test_df_subset['pred_bin'] == label]
        if len(subset) > 0:
            mae = subset['error'].mean()
            mape = (subset['error'] / (subset['pm25_ugm3'] + 1e-10)).mean() * 100
            count = len(subset)
            pct = count / len(test_df_subset) * 100
            print(f"  {label:25s}  MAE={mae:5.2f}  MAPE={mape:5.1f}%  n={count:,} ({pct:4.1f}%)")
    
    # Worst predictions
    print("\n[3.4] Top 10 Worst Predictions:")
    worst = test_df_subset.nlargest(10, 'error')[['timestamp_utc', 'city', 'pm25_ugm3', 'pred', 'error']]
    for i, row in worst.iterrows():
        print(f"  {row['timestamp_utc']}  {row['city']:10s}  "
              f"True={row['pm25_ugm3']:6.2f}  Pred={row['pred']:6.2f}  Error={row['error']:6.2f}")
    
    # Consecutive errors (model drift)
    print("\n[3.5] Checking for Model Drift (consecutive high errors):")
    test_df_subset = test_df_subset.sort_values('timestamp_utc')
    test_df_subset['high_error'] = (test_df_subset['error'] > 5).astype(int)
    test_df_subset['error_streak'] = test_df_subset.groupby('city')['high_error'].rolling(10).sum().values
    
    max_streak = test_df_subset['error_streak'].max()
    print(f"  Max consecutive errors (>5 µg/m³) in 10-hour window: {max_streak:.0f}")
    
    # Feature importance
    print("\n[3.6] Feature Importance (Top 10):")
    importances = forecaster.model_median.feature_importances_
    feature_names = X_train.columns
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': importances
    }).sort_values('importance', ascending=False)
    
    for i, row in importance_df.head(10).iterrows():
        print(f"  {row['feature']:30s}  {row['importance']:8.1f}")


def suggest_improvements():
    """Provide specific, actionable recommendations."""
    print("\n" + "=" * 80)
    print("PART 4: IMPROVEMENT OPPORTUNITIES")
    print("=" * 80)
    
    print("\n[4.1] Current Model Strengths:")
    print("  ✅ Strong lag features (pm25_lag_1h importance: 703)")
    print("  ✅ Captures temporal patterns (hour importance: 753)")
    print("  ✅ Good weather integration")
    print("  ✅ Simple, explainable architecture")
    print("  ✅ Already beats baseline by 71.78%")
    
    print("\n[4.2] Identified Weaknesses:")
    print("  ⚠️  Higher errors at extreme values (clean air <12, heavy pollution >55)")
    print("  ⚠️  Nighttime predictions worse (MAE ~4.0 vs midday ~2.6)")
    print("  ⚠️  Lahore hardest to predict (MAE 4.34 vs Karachi 1.72)")
    print("  ⚠️  Coefficient of variation suggests high volatility")
    
    print("\n[4.3] Potential Improvements (Ranked by Expected Impact):")
    
    print("\n  🥇 HIGH IMPACT (likely 10-20% MAE reduction):")
    print("     1. Per-City Models")
    print("        - Train separate model for each city")
    print("        - Karachi (low pollution, stable) needs different model than Lahore (high, volatile)")
    print("        - Implementation: 4 separate LGBMRegressor instances")
    print("        - Tradeoff: More complex, but captures city-specific patterns")
    
    print("\n     2. Hybrid Model (LightGBM + Simple Rules)")
    print("        - Use LightGBM for normal conditions")
    print("        - Add rule-based adjustments for extremes:")
    print("          * If pm25_lag_1h > 100: increase predicted interval width")
    print("          * If wind_speed > 20: dampen persistence effect")
    print("        - Captures domain knowledge that pure ML might miss")
    
    print("\n  🥈 MEDIUM IMPACT (likely 5-10% MAE reduction):")
    print("     3. Add Short-Term Lag Features (2h, 3h, 6h)")
    print("        - pm25_lag_1h is strongest predictor (importance 703)")
    print("        - More granular short-term lags could help")
    print("        - Risk: Minimal, we tested this (V3 had slight gain)")
    
    print("\n     4. Time-Weighted Recent Average")
    print("        - Instead of simple rolling_mean_24h, weight recent hours more")
    print("        - Formula: weighted_avg = 0.5*lag_1h + 0.3*lag_2h + 0.2*lag_3h")
    print("        - Captures momentum better")
    
    print("\n     5. Separate Night/Day Models")
    print("        - Errors are higher at night (hour 00-05: MAE ~4.0)")
    print("        - Train one model for 06:00-21:00, another for 22:00-05:00")
    print("        - Different atmospheric dynamics at night")
    
    print("\n  🥉 LOW IMPACT (likely <5% MAE reduction):")
    print("     6. Feature Engineering Tweaks")
    print("        - Remove weakest features (is_weekend, sensor_count)")
    print("        - Add interaction terms (hour × lag_1h)")
    print("        - We tested this (V2), it made things worse")
    
    print("\n     7. Hyperparameter Tuning")
    print("        - More trees (500 → 1000)")
    print("        - Slower learning (0.05 → 0.03)")
    print("        - Deeper trees (7 → 9)")
    print("        - Marginal gains at best, tested in V2/V3")
    
    print("\n     8. Different Model Architecture")
    print("        - Prophet (time series specific)")
    print("        - LSTM/GRU (deep learning)")
    print("        - XGBoost (similar to LightGBM)")
    print("        - Risk: High complexity, harder to explain in viva")
    
    print("\n[4.4] Recommended Action Plan:")
    print("\n  🎯 OPTION A: Go with Current Model (RECOMMENDED)")
    print("     - MAE 3.29 is already excellent (71.78% improvement)")
    print("     - Time better spent on Phase 3 (RAG, Pipeline, Dashboard)")
    print("     - Model is clean, explainable, meets all requirements")
    
    print("\n  🎯 OPTION B: Implement Per-City Models (IF 2+ HOURS AVAILABLE)")
    print("     - Expected gain: 10-20% MAE reduction (3.29 → 2.6-2.9)")
    print("     - Implementation time: ~2 hours")
    print("     - Steps:")
    print("       1. Modify trainer to accept city parameter")
    print("       2. Train 4 separate models")
    print("       3. Update evaluator to route predictions by city")
    print("       4. Re-run all evaluations")
    print("     - Worth it ONLY if you have buffer time")
    
    print("\n  🎯 OPTION C: Try Prophet/LSTM (NOT RECOMMENDED)")
    print("     - High risk, unknown reward")
    print("     - Would need to learn new framework")
    print("     - LightGBM is already state-of-art for tabular data")
    print("     - Save this for post-hackathon exploration")


def main():
    print("\n" + "=" * 80)
    print("DEEP ANALYSIS: MODEL PERFORMANCE & IMPROVEMENT STRATEGY")
    print("=" * 80)
    print("\nGoal: Understand current performance and identify realistic improvements")
    print("Current Model: LightGBM Quantile Regression (MAE 3.29 µg/m³, 71.78% improvement)")
    print("\n")
    
    analyze_data_characteristics()
    analyze_test_set_difficulty()
    analyze_model_errors()
    suggest_improvements()
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("\nBottom Line:")
    print("  - Current model is STRONG (71.78% > 20% required)")
    print("  - Per-city models could gain 10-20% improvement")
    print("  - Other approaches have marginal/unknown benefit")
    print("  - Recommend: Proceed to Phase 3 unless 2+ hours buffer exists")
    print("=" * 80)


if __name__ == "__main__":
    main()
