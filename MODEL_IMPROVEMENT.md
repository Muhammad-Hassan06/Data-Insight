# Model Improvement Analysis — Data-Insight PM2.5 Forecaster

**Date:** 20 October 2026  
**Current Model:** LightGBM Quantile Regression (3 models: q=0.10, q=0.50, q=0.90)  
**Current MAE:** 3.29 µg/m³ | **Baseline MAE:** 11.65 µg/m³ | **Improvement:** 71.76%

---

## 1. Dataset Overview & Characteristics

### 1.1 Data Volume

| Source | Records | Cities | Time Range |
|--------|---------|--------|------------|
| OpenAQ PM2.5 (raw) | 339,768 | 4 | Oct 2024 → Oct 2026 (2 years) |
| Open-Meteo Weather (raw) | 70,176 | 4 | Oct 2024 → Oct 2026 (2 years) |
| Gold Table (after aggregation, merging, feature engineering) | 47,304 | 4 | ~Oct 2024 → Oct 2026 |
| Train Set | 37,842 | 4 | ~80% earliest data |
| Test Set | 9,462 | 4 | ~20% latest data |

### 1.2 PM2.5 Distribution by City

| City | Typical Range | Key Challenge |
|------|--------------|---------------|
| **Karachi** | Low pollution, stable (MAE 1.72) | Easiest to predict — small variance, coastal climate |
| **Islamabad** | Moderate, semi-seasonal (MAE 3.02) | Moderate volatility, hill station effects |
| **Peshawar** | High pollution, spiky (MAE 3.95) | 759 readings > 500 µg/m³ — extreme pollution spikes |
| **Lahore** | Highest & most volatile (MAE 4.36) | 379 readings > 500 µg/m³, severe winter smog, max 763 µg/m³ |

### 1.3 Data Quality Issues Detected

| Issue | City | Rows Affected | Action Taken |
|-------|------|---------------|--------------|
| PM2.5 spikes > 500 µg/m³ | Peshawar | 759 | Flagged (kept) |
| PM2.5 spikes > 500 µg/m³ | Lahore | 379 | Flagged (kept) |
| PM2.5 spikes > 500 µg/m³ | Karachi | 6 | Flagged (kept) |
| PM2.5 spikes > 500 µg/m³ | Islamabad | 1 | Flagged (kept) |
| Long temporal gaps (>24h) | Islamabad | 108 hours | Flagged, left as NULL |
| Long temporal gaps (>24h) | Lahore | 35 hours | Flagged, left as NULL |
| Short temporal gaps (≤2h) | All cities | 113 total hours | Filled via interpolation |

### 1.4 Current Feature Set (22 features used by model)

| Category | Features | Count |
|----------|----------|-------|
| **Lag** | `pm25_lag_1h`, `pm25_lag_24h`, `pm25_lag_48h`, `pm25_lag_168h`, `any_flagged` | 5 |
| **Rolling** | `pm25_rolling_mean_24h`, `pm25_rolling_std_24h`, `pm25_rolling_mean_168h`, `pm25_rolling_std_168h` | 4 |
| **Temporal** | `hour`, `day_of_week`, `month`, `is_weekend`, `season` | 5 |
| **Weather** | `temperature`, `humidity`, `dew_point`, `precipitation`, `pressure`, `cloud_cover`, `wind_speed`, `wind_direction` | 8 |

### 1.5 Key Observations About the Data

1. **Extreme right-skew in Lahore & Peshawar** — PM2.5 values span 0–862 µg/m³. The model sees mostly low/moderate values but occasionally faces extreme spikes. This skewed distribution means MAE is dominated by large errors during pollution events.

2. **Strong autoregressive signal** — `pm25_lag_1h` is by far the most important feature (importance ~703). This means PM2.5 at time `t` is highly predicted by the value at `t-1`, which makes sense physically (air quality changes slowly).

3. **Diurnal cycle matters** — `hour` is the 2nd most important feature (~753 importance). PM2.5 peaks at night (boundary layer compression) and is lowest in the afternoon.

4. **Weather has moderate signal** — Temperature, humidity, and wind speed contribute but are secondary to the autoregressive lags.

5. **8,554 training nulls + 4,684 test nulls were dropped** — This is concerning. The nulls likely come from weather columns not aligning perfectly with PM2.5 timestamps (0% weather null rate was reported during merge, so these may be from the season encoding or edge cases). This means ~22% of training data and ~49% of test data was unused.

---

## 2. Current Model Strengths & Weaknesses

### 2.1 Strengths

- **71.76% improvement over baseline** — Far exceeds the 20% requirement
- **LightGBM is state-of-the-art for tabular data** — Well-suited for this mix of numerical + categorical features
- **Quantile regression provides uncertainty** — 80% prediction intervals with 76.35% actual coverage
- **Simple, explainable, fast** — Easy to explain during viva, trains in seconds
- **Per-city time-split** — Proper evaluation with no data leakage

### 2.2 Weaknesses

| Weakness | Evidence | Impact |
|----------|----------|--------|
| **Lahore is hardest to predict** | MAE 4.36 vs Karachi 1.72 (2.5x worse) | Fairness gap across cities |
| **Nighttime errors are higher** | Night (00-05) MAE ~4.0 vs midday ~2.6 | Consistent under-performance at night |
| **Extreme pollution events poorly captured** | Errors spike when PM2.5 > 150 µg/m³ | Exactly when predictions matter most (health alerts) |
| **Single global model** | Same model parameters for Karachi (stable, low) and Lahore (volatile, high) | Cannot specialise for different city dynamics |
| **~22-49% null-related data loss** | 8,554 train + 4,684 test rows dropped | Less data for training, potentially biased test set |
| **Coverage below target** | 76.35% actual vs 80% target | Prediction intervals are slightly too narrow |
| **No inter-city features** | Regional smog events affect Lahore+Islamabad simultaneously | Missing regional correlation signal |
| **No fire/burning features** | NASA FIRMS data available but unused | Major PM2.5 driver in Punjab (crop burning season) |

---

## 3. Model Alternatives — Should We Switch?

### 3.1 Keep LightGBM (RECOMMENDED — With Enhancements)

> **Verdict: YES, keep LightGBM as the backbone. Enhance, don't replace.**

LightGBM is the right choice for this problem because:
- Tabular data with mixed feature types = gradient boosting territory
- Fast training (seconds) allows rapid iteration
- Native support for quantile regression (uncertainty)
- Handles missing values naturally
- Feature importance is interpretable for viva

### 3.2 Alternative Models Comparison

| Model | Expected MAE Gain | Complexity | Training Time | Hackathon Risk | Recommendation |
|-------|-------------------|------------|---------------|----------------|----------------|
| **Per-City LightGBM** | 10-20% better | Low | Same | Low | ⭐ **HIGHLY RECOMMENDED** |
| **XGBoost** | ~0-3% better | Low | Slightly slower | Low | ✅ Worth trying (drop-in replacement) |
| **CatBoost** | ~2-5% better | Low | Slightly slower | Low | ✅ Worth trying (better categorical handling) |
| **LightGBM + DART** | ~3-8% better | Low | 2-3x slower | Low | ✅ Worth trying (dropout regularisation) |
| **Stacking Ensemble** | 5-15% better | Medium | 3-5x slower | Medium | ⚠️ If time permits |
| **Prophet** | Likely worse | Medium | Slow | Medium | ❌ Not suitable (designed for daily/weekly, not hourly with features) |
| **LSTM / GRU** | Unknown (possibly 5-15%) | High | Very slow (needs GPU) | High | ❌ Too risky for hackathon |
| **Temporal Fusion Transformer** | Possibly 10-20% better | Very High | Very slow (GPU required) | Very High | ❌ Far too complex for 72h hackathon |
| **ARIMA/SARIMAX** | Likely worse | Medium | Fast | Low | ❌ Can't handle 22 exogenous features well |
| **Random Forest** | 5-10% worse | Low | Fast | Low | ❌ Known to underperform gradient boosting |

---

## 4. Detailed Improvement Strategies (Ranked by Impact)

### 🥇 HIGH IMPACT — Expected 10-20% MAE Reduction

#### Strategy 1: Per-City Models (Train 4 Separate LightGBM Models)

**Why:** A single model tries to learn patterns for both Karachi (stable, coastal, low PM2.5) and Lahore (extreme, landlocked, heavy smog). These cities have fundamentally different PM2.5 dynamics.

**What to do:**
- Train 4 independent LightGBM models, one per city
- Each model learns city-specific patterns (e.g., Lahore's winter smog, Karachi's sea breeze effect)
- At prediction time, route each sample to the correct city model

**Expected gain:**
- Lahore MAE: 4.36 → ~3.5 (city-specific patterns captured)
- Karachi MAE: 1.72 → ~1.5 (already good, minor improvement)
- Overall MAE: 3.29 → ~2.6-2.9

**Tradeoffs:**
- 4 models instead of 1 (4x model files, but each is smaller)
- Cannot generalise to unseen cities (acceptable for this problem)
- Slightly more code complexity in trainer/evaluator

**Implementation time:** ~2 hours

---

#### Strategy 2: Incorporate NASA FIRMS Fire Data

**Why:** Crop burning is the #1 driver of extreme PM2.5 events in Punjab (Lahore, Peshawar). This is the exact scenario where our model fails most. We already have the NASA FIRMS API key configured but unused.

**What to do:**
- Fetch fire hotspot data from NASA FIRMS API for the same 2-year period
- Create features: `fire_count_50km`, `fire_count_100km`, `fire_radiative_power_avg`
- Add these as additional features to the gold table

**Expected gain:**
- Would dramatically improve predictions during Oct-Nov smog season
- Lahore MAE during winter could drop by 20-30%
- Overall MAE: 3.29 → ~2.8-3.0

**Tradeoffs:**
- Requires new data fetch module
- API rate limits on FIRMS
- Fire data may have reporting delays

**Implementation time:** ~3-4 hours

---

#### Strategy 3: Fix the Null Data Loss Problem

**Why:** 8,554 training rows and 4,684 test rows are being dropped due to nulls. That's ~22% of training data and ~49% of test data wasted. These nulls appear when `prepare_features()` calls `dropna()`. This is a massive data loss that could be hurting model generalisation.

**What to do:**
- Investigate which columns have the nulls (likely `season` encoding or edge-case weather columns)
- Use LightGBM's native missing value handling instead of dropping rows
- Or impute weather columns with forward-fill (appropriate for hourly data)

**Expected gain:**
- More training data = better generalisation
- More test data = more reliable evaluation
- Potential MAE improvement: 5-10%

**Implementation time:** ~1-2 hours

---

### 🥈 MEDIUM IMPACT — Expected 5-10% MAE Reduction

#### Strategy 4: Add Short-Term Lag Features (2h, 3h, 6h, 12h)

**Why:** `pm25_lag_1h` is the most important feature. Adding intermediate lags (2h, 3h, 6h, 12h) gives the model more granular information about recent PM2.5 trends.

**What to do:**
- Add `pm25_lag_2h`, `pm25_lag_3h`, `pm25_lag_6h`, `pm25_lag_12h` to `build_processed.py`
- Also add: `pm25_rolling_mean_6h`, `pm25_rolling_std_6h`

**Expected gain:** 3-7% MAE reduction

**Implementation time:** ~30 minutes

---

#### Strategy 5: Add Rate-of-Change Features

**Why:** The model knows the current PM2.5 level (via lags) but doesn't know if pollution is increasing or decreasing. A "delta" feature captures momentum.

**What to do:**
- `pm25_delta_1h = pm25_lag_1h - pm25_lag_2h` (hourly change)
- `pm25_delta_3h = pm25_lag_1h - pm25_lag_3h` (3-hour trend)
- `pm25_delta_24h = pm25_lag_1h - pm25_lag_24h` (daily change)
- `pm25_acceleration = delta_1h - (pm25_lag_2h - pm25_lag_3h)` (is pollution accelerating?)

**Expected gain:** 3-5% MAE reduction

**Implementation time:** ~30 minutes

---

#### Strategy 6: Time-Weighted Moving Average

**Why:** `rolling_mean_24h` treats all 24 hours equally, but recent hours matter more. An exponentially weighted mean gives more weight to recent values.

**What to do:**
- Replace or supplement `rolling_mean_24h` with `pm25_ewm_24h` (exponential weighted mean, span=24)
- Add `pm25_ewm_6h` for short-term trends

**Expected gain:** 2-5% MAE reduction

**Implementation time:** ~20 minutes

---

#### Strategy 7: Separate Day/Night Models

**Why:** Nighttime errors are systematically higher (~4.0 MAE vs ~2.6 midday). Night and day have different atmospheric dynamics (boundary layer height, traffic patterns, heating).

**What to do:**
- Split data into Day (06:00-21:00) and Night (22:00-05:00)
- Train 2 models (or 8 if combined with per-city)
- Route predictions based on hour

**Expected gain:** 5-8% MAE reduction (especially at night)

**Implementation time:** ~1.5 hours

---

#### Strategy 8: Try XGBoost or CatBoost as Drop-in Replacement

**Why:** These are direct competitors to LightGBM. Sometimes one outperforms the other on a specific dataset. They use slightly different tree-building algorithms.

**XGBoost:**
```
pip install xgboost
```
- Uses `exact` or `hist` tree method
- Sometimes better at capturing interactions
- Drop-in replacement: just change `LGBMRegressor` → `XGBRegressor`

**CatBoost:**
```
pip install catboost
```
- Superior handling of categorical features (`season`, `city`)
- Built-in ordered boosting (prevents target leakage)
- Slightly slower but often more accurate

**Expected gain:** 0-5% MAE reduction (varies by dataset)

**Implementation time:** ~30 minutes each

---

### 🥉 LOW IMPACT — Expected <5% MAE Reduction

#### Strategy 9: Hyperparameter Tuning with Optuna

**Why:** Current hyperparameters (500 trees, lr=0.05, depth=7) are reasonable but not optimised.

**What to tune:**
| Parameter | Current | Search Range |
|-----------|---------|--------------|
| n_estimators | 500 | 300-2000 |
| learning_rate | 0.05 | 0.01-0.1 |
| max_depth | 7 | 5-12 |
| num_leaves | 31 | 15-63 |
| min_child_samples | 20 | 10-50 |
| subsample | 0.8 | 0.6-1.0 |
| colsample_bytree | 0.8 | 0.6-1.0 |
| reg_alpha (L1) | 0 | 0-10 |
| reg_lambda (L2) | 0 | 0-10 |

**Expected gain:** 1-3% MAE reduction

**Implementation time:** ~1 hour (using Optuna with 100 trials)

---

#### Strategy 10: Feature Interaction Terms

**Why:** LightGBM can learn interactions through tree splits, but providing explicit interaction features can help.

**Candidates:**
- `hour × pm25_lag_1h` — Diurnal pattern conditional on current pollution level
- `wind_speed × humidity` — Dispersion depends on both
- `temperature × month` — Seasonal temperature patterns
- `city_encoded × season` — City-specific seasonality

**Expected gain:** 0-3% MAE reduction (LightGBM may already capture these)

**Implementation time:** ~30 minutes

---

#### Strategy 11: Stacking Ensemble

**Why:** Combine multiple models (LightGBM, XGBoost, CatBoost) into a meta-learner.

**Architecture:**
```
Level 0: LightGBM, XGBoost, CatBoost (each trained on gold features)
Level 1: Ridge Regression (trained on Level 0 predictions)
```

**Expected gain:** 5-10% MAE reduction (ensembles usually improve)

**Tradeoffs:**
- 3x model complexity
- Harder to explain in viva
- Risk of overfitting the meta-learner

**Implementation time:** ~3 hours

---

## 5. Coverage Improvement (76.35% → 80% Target)

The prediction interval coverage is 76.35% against an 80% target. This means intervals are slightly too narrow.

### Options:
1. **Widen quantiles**: Change from [0.10, 0.90] to [0.08, 0.92] — simplest fix
2. **Post-hoc calibration**: Multiply interval width by `80/76.35 ≈ 1.05`
3. **Conformal prediction**: Use a holdout calibration set to compute exact quantile corrections
4. **Per-city quantiles**: Lahore (73.70% coverage) needs wider intervals than Karachi (78.84%)

**Recommended:** Option 1 (change quantiles to [0.08, 0.92]) — ~10 minutes, high confidence it fixes the gap.

---

## 6. Recommended Action Plan

### Priority Order (if time is limited)

| Priority | Strategy | Expected Gain | Time | Risk |
|----------|----------|---------------|------|------|
| **1** | Fix null data loss (Strategy 3) | 5-10% | 1-2h | Very Low |
| **2** | Per-city models (Strategy 1) | 10-20% | 2h | Low |
| **3** | Add short-term lags + deltas (Strategy 4+5) | 5-10% | 1h | Very Low |
| **4** | Widen quantiles for coverage fix | Coverage 76→80% | 10min | None |
| **5** | Try XGBoost/CatBoost (Strategy 8) | 0-5% | 30min | Low |
| **6** | NASA FIRMS fire data (Strategy 2) | 10-20% (seasonal) | 3-4h | Medium |
| **7** | Hyperparameter tuning (Strategy 9) | 1-3% | 1h | Low |

### If You Have 2 Hours
→ Do **Priority 1 + 2** (fix nulls + per-city models). Expected overall MAE: **~2.5-2.8 µg/m³**

### If You Have 4 Hours
→ Do **Priority 1 + 2 + 3 + 4**. Expected overall MAE: **~2.3-2.6 µg/m³** with proper coverage

### If You Have 6+ Hours
→ Do all of the above + **Priority 5 + 6**. Expected overall MAE: **~2.0-2.4 µg/m³**

---

## 7. Final Verdict

> **Keep LightGBM. Don't switch models. Enhance the pipeline.**

The current model is already strong (71.76% improvement). The biggest gains come from:
1. **Not throwing away data** (fix null loss)
2. **Specialising per city** (per-city models)
3. **Better features** (short-term lags, deltas, fire data)

Switching to LSTM, Prophet, or Transformers is **NOT recommended** for this hackathon — they add massive complexity, need GPU/long training, are harder to explain, and may not even outperform an enhanced LightGBM.

---

*Analysis based on: 339,768 PM2.5 records, 70,176 weather records, 47,304 gold table rows across Lahore, Karachi, Islamabad, and Peshawar (Oct 2024 – Oct 2026).*
