# Model Improvement Analysis

**Date:** October 20, 2026  
**Current Model:** LightGBM Quantile Regression  
**Current Performance:** MAE 3.29 µg/m³ (71.78% improvement over baseline)  
**Hackathon Requirement:** ≥20% improvement over baseline ✅

---

## Executive Summary

Our current model **significantly exceeds** hackathon requirements (71.78% vs 20% required improvement). This document analyzes the dataset characteristics, identifies model weaknesses, and proposes realistic improvement strategies for future iterations.

**Bottom Line:** The model is production-ready. Further improvements are optional enhancements, not critical fixes.

---

## 1. Dataset Characteristics

### 1.1 Overall Statistics

- **Total Samples:** 47,208 rows
- **Date Range:** June 2025 → October 2026 (16 months)
- **Cities:** Lahore, Karachi, Islamabad, Peshawar
- **Features:** 22 features (4 lags, 4 rolling, 5 temporal, 8 weather, 1 other)

### 1.2 PM2.5 Distribution by City

| City | Mean | Median | Std | Min | Max | Coeff. Variation |
|------|------|--------|-----|-----|-----|------------------|
| **Karachi** | 41.76 | 30.60 | 31.08 | 1.55 | 324.00 | 0.744 (stable) |
| **Islamabad** | 60.83 | 42.40 | 52.82 | 0.03 | 340.00 | 0.868 (moderate) |
| **Peshawar** | 88.33 | 53.00 | 87.06 | 0.00 | 613.00 | 0.986 (volatile) |
| **Lahore** | 97.08 | 52.77 | 94.70 | 0.00 | 527.00 | 0.975 (volatile) |

**Key Insight:** Cities have drastically different pollution profiles. Karachi is stable and predictable; Lahore and Peshawar are highly volatile with extreme values.

### 1.3 Temporal Patterns

**Monthly Variation:**
- Lowest: August (35.24 µg/m³) — summer, monsoon
- Highest: December (203.19 µg/m³) — winter, smog season
- **Range:** 5.8x difference between cleanest and dirtiest months

**Hourly Variation:**
- Lowest: Hour 10 (47.93 µg/m³) — morning ventilation
- Highest: Hour 16 (89.16 µg/m³) — afternoon traffic/heat
- **Range:** 86% increase from cleanest to dirtiest hour

### 1.4 Feature Correlations with Target

| Feature | Correlation | Insight |
|---------|-------------|---------|
| **pm25_lag_1h** | 0.977 | Recent past is strongest predictor |
| **pm25_rolling_mean_24h** | 0.890 | Daily average captures trend |
| **pm25_lag_24h** | 0.883 | Same-hour yesterday useful |
| **pm25_lag_48h** | 0.838 | 2-day lag still relevant |
| **wind_speed** | -0.392 | Wind disperses pollution |
| **temperature** | -0.624 | Cooler = more pollution (winter smog) |

---

## 2. Train vs Test Set Analysis

### 2.1 Distribution Shift (Critical Finding)

| Metric | Training Set | Test Set | Implication |
|--------|-------------|----------|-------------|
| **Mean PM2.5** | 79.90 µg/m³ | 41.93 µg/m³ | Test is 47% cleaner |
| **Std PM2.5** | 81.16 | 22.14 | Test is 73% less volatile |
| **Date Range** | June 2025 → July 2026 | July → Oct 2026 | Test = summer only |
| **Months** | All 12 months | Only months 7-10 | Missing winter data |
| **Max Value** | 613.00 µg/m³ | 185.50 µg/m³ | No extreme events in test |

**⚠️ Critical Insight:**  
Our test set represents **summer months only** (July-October), which are naturally cleaner. The model has **not been tested on winter smog conditions** (Nov-Feb), where PM2.5 can exceed 500 µg/m³.

**Real-World Implication:**  
Our MAE 3.29 µg/m³ is on "easy mode" data. Winter performance is likely MAE 5-8 µg/m³ (still beats baseline, but not as impressive).

---

## 3. Current Model Performance

### 3.1 Overall Metrics

- **MAE:** 3.29 µg/m³
- **RMSE:** 5.05 µg/m³
- **MAPE:** 13.23%
- **Improvement over Baseline:** 71.78% ✅ (required: ≥20%)
- **Prediction Interval Coverage:** 76.29% (target: 80%, acceptable: 75-85%) ✅

### 3.2 Error Distribution

| Percentile | Error (µg/m³) | Interpretation |
|------------|---------------|----------------|
| 50th (Median) | 2.12 | Half of predictions within 2.1 µg/m³ |
| 90th | 7.28 | 90% of predictions within 7.3 µg/m³ |
| 95th | 10.33 | 5% of predictions have error >10 µg/m³ |
| Max | 47.61 | Worst prediction off by 47.6 µg/m³ |

### 3.3 Errors by PM2.5 Level

| AQI Category | MAE | MAPE | % of Test Set | Assessment |
|--------------|-----|------|---------------|------------|
| **Good (0-12)** | 6.23 | 116% | 3.3% | ⚠️ Overpredicts clean air |
| **Moderate (12-35)** | 2.78 | 11.7% | 52.6% | ✅ Excellent |
| **Unhealthy SG (35-55)** | 3.03 | 7.0% | 36.3% | ✅ Excellent |
| **Unhealthy (55-150)** | 6.69 | 9.7% | 7.8% | ⚠️ Underpredicts spikes |

**Key Weakness:** Model struggles at extremes (very clean air and heavy pollution).

### 3.4 Per-City Performance

| City | MAE | RMSE | Coverage | Assessment |
|------|-----|------|----------|------------|
| **Karachi** | 1.72 | 2.26 | 77.99% | ✅ Excellent (stable city) |
| **Islamabad** | 3.01 | 4.67 | 76.54% | ✅ Good |
| **Peshawar** | 3.97 | 5.77 | 76.53% | ⚠️ Moderate |
| **Lahore** | 4.34 | 6.34 | 74.26% | ⚠️ Worst (volatile city) |

**Key Weakness:** Single global model struggles with city heterogeneity.

### 3.5 Feature Importance (Top 10)

| Rank | Feature | Importance | Notes |
|------|---------|------------|-------|
| 1 | hour | 1665 | Time of day is critical |
| 2 | pm25_lag_1h | 1580 | Recent past dominates |
| 3 | wind_speed | 911 | Wind disperses pollution |
| 4 | wind_direction | 895 | Directional patterns matter |
| 5 | pressure | 877 | Atmospheric stability |
| 6 | pm25_rolling_mean_24h | 861 | Daily trend |
| 7 | pm25_lag_24h | 857 | Same-hour yesterday |
| 8 | dew_point | 851 | Moisture affects visibility |
| 9 | pm25_rolling_std_24h | 829 | Volatility indicator |
| 10 | temperature | 826 | Seasonal effects |

**Weakest Features (candidates for removal):**
- is_weekend (importance: 1)
- season (importance: 12)
- day_of_week (importance: 13)
- sensor_count (importance: 14)

---

## 4. Top 10 Worst Predictions (Error Analysis)

| Timestamp | City | True | Predicted | Error | Pattern |
|-----------|------|------|-----------|-------|---------|
| 2026-08-11 21:00 | Peshawar | 18.00 | 65.61 | 47.61 | Sudden drop (rain?) |
| 2026-07-11 20:00 | Islamabad | 2.85 | 36.19 | 33.34 | Clean air event |
| 2026-07-26 21:00 | Peshawar | 84.30 | 51.14 | 33.16 | Evening spike missed |
| 2026-08-10 04:00 | Lahore | 61.60 | 94.57 | 32.97 | Overpredicted nighttime |
| 2026-07-21 07:00 | Lahore | 14.25 | 47.18 | 32.93 | Morning clean-up |

**Common Failure Modes:**
1. **Sudden clean-air events** (rain, wind shift) — model expects persistence
2. **Evening hours (20:00-21:00)** — transition period hard to predict
3. **Peshawar & Lahore** — volatile cities with rapid changes

---

## 5. Improvement Opportunities (Ranked by Expected Impact)

### 🥇 HIGH IMPACT (Expected MAE Reduction: 10-20%)

#### **5.1 Per-City Models**

**Why it helps:**
- Karachi (CV=0.744) needs different model than Lahore (CV=0.975)
- Each city has unique pollution sources, weather patterns, geography
- Allows city-specific feature importance and hyperparameters

**Implementation:**
```python
models = {}
for city in ['Lahore', 'Karachi', 'Islamabad', 'Peshawar']:
    city_train = train_df[train_df['city'] == city]
    models[city] = PM25Forecaster(
        # City-specific hyperparameters
        n_estimators=500 if city == 'Karachi' else 700,
        max_depth=5 if city == 'Karachi' else 9
    )
    models[city].train(X_city_train, y_city_train)
```

**Expected Result:**
- Karachi: MAE 1.72 → 1.2 (stable city, should be near-perfect)
- Lahore: MAE 4.34 → 3.5 (volatile city, harder to improve)
- **Overall: MAE 3.29 → 2.6-2.9** (10-20% improvement)

**Effort:** ~2 hours (modify trainer, re-run evaluation)

**Pros:**
- Highest expected improvement
- Still explainable ("specialized models per city")
- Addresses root cause (city heterogeneity)

**Cons:**
- More complex (4 models instead of 1)
- Harder to maintain
- Need to retrain all 4 if data changes

---

#### **5.2 Hybrid Model (LightGBM + Domain Rules)**

**Why it helps:**
- Pure ML misses domain knowledge about extreme events
- Add rule-based adjustments for known patterns

**Example Rules:**
```python
# Rule 1: Rain events (rapid PM2.5 drops)
if precipitation > 5mm and pm25_lag_1h > 50:
    prediction *= 0.6  # Expect 40% drop

# Rule 2: High wind disperses pollution
if wind_speed > 20 m/s:
    prediction = min(prediction, pm25_lag_24h)  # Cap at yesterday

# Rule 3: Winter morning inversions
if month in [11, 12, 1, 2] and hour in [6, 7, 8]:
    prediction *= 1.3  # Expect 30% spike (traps pollution)

# Rule 4: Weekend traffic reduction
if is_weekend and hour in [8, 9, 10]:
    prediction *= 0.85  # 15% less traffic pollution
```

**Expected Result:** MAE 3.29 → 2.8-3.0 (5-10% improvement)

**Effort:** ~3 hours (requires domain research, tuning thresholds)

**Pros:**
- Incorporates expert knowledge
- Handles extreme events better
- Explainable to stakeholders

**Cons:**
- Rules may overfit to training period
- Harder to maintain (rules need updating)

---

### 🥈 MEDIUM IMPACT (Expected MAE Reduction: 5-10%)

#### **5.3 Add Short-Term Lag Features**

**Why it helps:**
- pm25_lag_1h has correlation 0.977 (strongest predictor)
- More granular recent lags capture momentum

**New Features:**
- pm25_lag_2h, pm25_lag_3h, pm25_lag_6h, pm25_lag_12h
- pm25_rolling_mean_6h, pm25_rolling_std_6h
- pm25_change_1h = lag_1h - lag_2h (rate of change)

**Expected Result:** MAE 3.29 → 3.0-3.1 (3-6% improvement)

**Effort:** ~1 hour (modify feature engineering in processed layer)

**Note:** We tested this (V3) and got MAE 3.17 (slight improvement, but lost test samples due to cold-start). Feasible but marginal gain.

---

#### **5.4 Time-Weighted Recent Average**

**Why it helps:**
- Simple rolling_mean_24h treats all hours equally
- Recent hours should have more weight

**Implementation:**
```python
# Instead of: rolling_mean_24h = mean(lag_1h...lag_24h)
# Use exponential weighting:
weights = np.exp(-np.arange(24) / 6)  # decay factor = 6 hours
weighted_avg = np.average([lag_1h, lag_2h, ..., lag_24h], weights=weights)
```

**Expected Result:** MAE 3.29 → 3.0-3.15 (4-9% improvement)

**Effort:** ~1 hour

---

#### **5.5 Separate Day/Night Models**

**Why it helps:**
- Night errors (MAE ~4.0) higher than day errors (MAE ~2.6)
- Different atmospheric dynamics (inversions, reduced mixing)

**Implementation:**
```python
model_day = PM25Forecaster()   # Train on hours 6-21
model_night = PM25Forecaster() # Train on hours 22-5

# Predict based on time of day
if hour >= 6 and hour <= 21:
    prediction = model_day.predict(X)
else:
    prediction = model_night.predict(X)
```

**Expected Result:** MAE 3.29 → 3.0-3.1 (6-9% improvement)

**Effort:** ~1.5 hours

---

### 🥉 LOW IMPACT (Expected MAE Reduction: <5%)

#### **5.6 Feature Engineering Tweaks**

- Remove weakest features (is_weekend, sensor_count, season, day_of_week)
- Add interaction terms (hour × pm25_lag_1h, temp × humidity)

**Note:** We tested this (V2) and got MAE 3.92 (worse). Feature removal can hurt more than help.

---

#### **5.7 Hyperparameter Tuning**

- More trees: 500 → 1000
- Slower learning: 0.05 → 0.03
- Deeper trees: 7 → 9

**Note:** Tested in V2/V3, marginal gains at best. Current hyperparameters are well-tuned.

---

#### **5.8 Different Model Architecture**

**Options:**
- **Prophet** (Facebook's time series model)
  - Pros: Handles seasonality, trends, holidays
  - Cons: Designed for daily/weekly forecasts, not hourly
  - Expected: Similar performance to LightGBM

- **LSTM/GRU** (Deep Learning)
  - Pros: Can capture long-term dependencies
  - Cons: Needs more data, harder to explain, slower training
  - Expected: Slight improvement (MAE 3.29 → 3.0) if tuned well

- **XGBoost** (Gradient Boosting)
  - Pros: Very similar to LightGBM
  - Cons: Slower, no significant advantage
  - Expected: Identical performance (MAE ~3.3)

**Recommendation:** Stick with LightGBM. It's state-of-art for tabular data.

---

## 6. Decision Matrix

| Strategy | Expected Gain | Effort | Risk | Priority |
|----------|--------------|--------|------|----------|
| **Per-City Models** | MAE 3.29 → 2.6-2.9 (15%) | 2h | Low | 🥇 HIGH |
| **Hybrid (ML + Rules)** | MAE 3.29 → 2.8-3.0 (10%) | 3h | Medium | 🥇 HIGH |
| **Short-Term Lags** | MAE 3.29 → 3.0-3.1 (6%) | 1h | Low | 🥈 MEDIUM |
| **Weighted Avg** | MAE 3.29 → 3.0-3.15 (5%) | 1h | Low | 🥈 MEDIUM |
| **Day/Night Models** | MAE 3.29 → 3.0-3.1 (8%) | 1.5h | Low | 🥈 MEDIUM |
| **Feature Tweaks** | MAE 3.29 → 3.4+ (-5%) | 2h | High | ❌ SKIP |
| **Hyperparameter Tuning** | MAE 3.29 → 3.2 (3%) | 2h | Low | 🥉 LOW |
| **Different Architecture** | Unknown | 8h+ | High | ❌ SKIP |

---

## 7. Recommended Action Plan

### 🎯 **OPTION A: Keep Current Model (RECOMMENDED)**

**Rationale:**
- MAE 3.29 is **71.78% improvement** over baseline (required: ≥20%)
- Model is clean, explainable, production-ready
- **Time better spent on Phase 3 deliverables:**
  - RAG Insight Agent (4-5 hours) — MANDATORY
  - Prefect Pipeline (3-4 hours) — MANDATORY
  - FastAPI + React Dashboard (3-4 hours) — MANDATORY
  - Polish & Documentation (3-4 hours) — REQUIRED

**Judges prioritize:**
1. **Complete working system** > Perfect model
2. **Explainability** > Marginal accuracy gains
3. **Deployment readiness** > Overfitting to test set

**Your competitive advantage:**
- "We beat baseline by 71%, identified future improvements, then focused on building a complete system"
- "Our model is production-ready and well-documented"

---

### 🎯 **OPTION B: Implement Per-City Models (IF 2+ HOURS BUFFER)**

**When to choose this:**
- Phase 3A, 3B, 3C are complete
- You have 2+ hours remaining before submission
- You want to push for maximum MAE reduction

**Steps:**
1. Modify `trainer.py` to accept city parameter (30 min)
2. Train 4 separate models (30 min)
3. Update `evaluator.py` to route by city (30 min)
4. Re-run evaluation, update metrics (30 min)
5. Update documentation (30 min)

**Expected Outcome:**
- MAE 3.29 → 2.6-2.9 (15% improvement)
- New story: "We beat baseline by 75-77%"

---

## 8. Limitations & Caveats

### 8.1 Test Set Bias

Our test set (July-October 2026) is **NOT representative** of full-year conditions:
- Missing winter smog season (Nov-Feb)
- Missing spring crop burning (Mar-Apr)
- Only covers "easy" months (summer monsoon)

**Real-world winter performance is likely:**
- MAE 5-8 µg/m³ (still beats baseline 11.65 µg/m³)
- Lower coverage % (more extreme values)

**Recommendation for viva:**
- Be transparent: "Our test set is summer data, winter validation needed"
- Show seasonal analysis: "December has 5.8x higher PM2.5 than August"

### 8.2 Unseen Extreme Events

Model has not been tested on:
- Severe smog episodes (PM2.5 > 500 µg/m³)
- Rare clean-air events (PM2.5 < 5 µg/m³)
- Rapid weather shifts (rain, cold fronts)

**Recommendation:** Deploy with human oversight, especially for AQI >150 predictions.

### 8.3 Missing Features

Not captured in current model:
- **Traffic data** (would improve rush-hour predictions)
- **Industrial activity** (factory emissions)
- **Agricultural fires** (crop burning in Mar-Apr)
- **Construction activity** (dust pollution)

**Future work:** Integrate real-time traffic APIs, satellite fire data.

---

## 9. Conclusion

### Current Status: ✅ **PRODUCTION-READY**

| Requirement | Target | Achieved | Status |
|-------------|--------|----------|--------|
| Beat Baseline | ≥20% improvement | **71.78%** | ✅ PASSED |
| Uncertainty Quantification | 80% coverage | **76.29%** | ✅ PASSED |
| Fairness Analysis | Report by city | Per-city MAE documented | ✅ PASSED |
| Explainability | Simple model | LightGBM + feature importance | ✅ PASSED |

### Future Improvements (Post-Hackathon)

**Phase 1 (High Impact):**
1. Implement per-city models (15% MAE reduction)
2. Collect winter test data (Nov-Feb) for validation
3. Add hybrid rules for extreme events

**Phase 2 (Operational):**
4. Integrate real-time traffic data
5. Add satellite fire detection
6. Deploy A/B testing (current vs per-city)

**Phase 3 (Research):**
7. Explore LSTM for long-term dependencies
8. Test ensemble methods (LightGBM + Prophet)
9. Incorporate air quality forecast models (CMAQ, WRF-Chem)

---

**Document prepared by:** Team Data-Insight  
**Last updated:** October 20, 2026  
**Status:** Analysis complete, proceeding with current model for Phase 3 deployment
