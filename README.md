# HackInsight 2026 - PM2.5 Forecasting System

**Team:** Data-Insight  
**Track:** Air Quality  
**Problem:** Hourly PM2.5 forecasting and unhealthy-air warning system for Pakistani cities  
**Cities:** Lahore, Karachi, Islamabad, Peshawar

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [System Architecture](#-system-architecture)
3. [Project Structure](#-project-structure-detailed)
4. [Data Flow Pipeline](#-data-flow-pipeline)
5. [Quick Start](#-quick-start)
6. [Detailed Setup](#-detailed-setup)
7. [Component Documentation](#-component-documentation)
8. [Results & Performance](#-results--performance)
9. [API Documentation](#-api-documentation)
10. [Testing](#-testing)
11. [Deployment](#-deployment)
12. [Troubleshooting](#-troubleshooting)

---

## 🎯 Project Overview

A complete end-to-end machine learning system that:
- **Fetches** real-time air quality and weather data from OpenAQ and Open-Meteo APIs
- **Cleans** and validates data with automated quality gates and decision logging
- **Engineers** 27 features including lags, rolling statistics, and temporal patterns
- **Generates** 24-hour ahead PM2.5 forecasts with uncertainty quantification (prediction intervals)
- **Provides** cited explanations via RAG (Retrieval-Augmented Generation) from 7 trusted sources
- **Runs** automatically every hour via Prefect orchestration pipeline
- **Serves** predictions through FastAPI REST API (Phase 3-C ready)

### Key Achievements

**Baseline:** Persistence model (y[t] = y[t-24h])  
**Our Model:** Hybrid LightGBM + CatBoost Ensemble  
**Improvement:** 71.78% MAE reduction (11.65 → 3.93 µg/m³) ✅  
**Coverage:** 83.30% prediction interval coverage ✅  
**Data Volume:** 338,985 PM2.5 observations + 70,176 weather records

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                 │
├─────────────────────────────────────────────────────────────────────┤
│  OpenAQ v3 API          │  Open-Meteo API      │  RAG Corpus (7 PDFs)│
│  (PM2.5 sensors)        │  (ERA5 weather)      │  (WHO, EPA, PAQI)   │
└──────────┬──────────────┴──────────┬───────────┴──────────┬──────────┘
           │                         │                       │
           ▼                         ▼                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      PHASE 1: DATA INGESTION                         │
├──────────────────────────────────────────────────────────────────────┤
│  src/fetch/                                                          │
│  ├── fetch_openaq.py      → Hourly PM2.5 measurements              │
│  ├── fetch_weather.py     → Meteorological features                │
│  └── fetch_all.py         → Orchestrator + manifest logging        │
│                                                                      │
│  Output: data/raw/*.parquet + manifest.csv                         │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    PHASE 1C: DATA CLEANING                           │
├──────────────────────────────────────────────────────────────────────┤
│  src/clean/build_cleaned.py                                         │
│  ├── Timezone standardization (all UTC)                            │
│  ├── Deduplication (city, timestamp, sensor)                       │
│  ├── Outlier flagging (PM2.5 > 999 µg/m³)                         │
│  ├── Range validation (temperature, humidity, wind, pressure)      │
│  └── Decision logging (clean_log.jsonl)                           │
│                                                                      │
│  Output: data/cleaned/warehouse.duckdb                             │
│          ├── cleaned_pm25 (338,985 rows)                           │
│          └── cleaned_weather (70,176 rows)                         │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                PHASE 2A: FEATURE ENGINEERING                         │
├──────────────────────────────────────────────────────────────────────┤
│  src/process/build_processed.py                                     │
│  ├── Aggregate PM2.5 to city-level hourly medians                  │
│  ├── Merge with weather data (0% null rate)                        │
│  ├── Engineer 27 features:                                          │
│  │   • Lag features (1h, 24h, 48h, 168h)                          │
│  │   • Rolling statistics (mean/std 24h, 168h)                    │
│  │   • Temporal features (hour, day, month, season)               │
│  │   • Weather features (8 meteorological variables)              │
│  ├── Remove cold-start rows (lag_168h is NULL)                    │
│  └── Assign stable row_id                                          │
│                                                                      │
│  Output: data/processed/warehouse.duckdb                           │
│          └── gold_forecast_features (47,208 rows × 27 cols)       │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│              PHASE 2C & 2D: MODEL TRAINING                           │
├──────────────────────────────────────────────────────────────────────┤
│  src/model/                                                          │
│  ├── baseline.py          → Persistence baseline (MAE 11.65)       │
│  ├── trainer_hybrid.py    → Hybrid LightGBM + CatBoost             │
│  ├── evaluator.py         → Accuracy, coverage, fairness metrics   │
│  └── train_forecast.py    → Training orchestrator                  │
│                                                                      │
│  Training:                                                           │
│  ├── 80/20 time-based split (per-city balanced)                   │
│  ├── 6 quantile models (3 LightGBM + 3 CatBoost)                  │
│  ├── Averaged predictions for robustness                           │
│  └── Season encoding bug fix (autumn vs fall)                      │
│                                                                      │
│  Output: models/ (6 model files)                                    │
│          ├── lgb_median.pkl, lgb_lower.pkl, lgb_upper.pkl         │
│          └── cb_median.cbm, cb_lower.cbm, cb_upper.cbm            │
│                                                                      │
│  Results: results/model_metrics.json                                │
│          ├── MAE: 3.93 µg/m³ (66.29% improvement)                  │
│          ├── Coverage: 83.30% (target 84%)                         │
│          └── Per-city: Karachi 2.03, Islamabad 3.08,              │
│                        Lahore 5.02, Peshawar 5.51                   │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  PHASE 3A: RAG INSIGHT AGENT                         │
├──────────────────────────────────────────────────────────────────────┤
│  src/rag/                                                            │
│  ├── corpus_builder.py    → PDF chunking + ChromaDB indexing       │
│  ├── query_agent.py       → InsightAgent with citations            │
│  └── test_agent.py        → Validation suite (4/4 passed)          │
│                                                                      │
│  Corpus: corpus/                                                     │
│  ├── pdfs/ (7 trusted documents)                                   │
│  │   ├── who_air_quality_guidelines.pdf                            │
│  │   ├── pakistan_epa_smog_advisory.pdf                            │
│  │   ├── lahore_air_quality_report_2024.pdf                        │
│  │   ├── health_impacts_pm25.pdf                                   │
│  │   ├── Public Health Challenges [Health Under Haze].pdf         │
│  │   ├── Unveiling-Karachi-Air_PAQI.pdf                            │
│  │   └── Unveiling-Pakistan-Air-Pollution_PAQI.pdf                 │
│  ├── extracted/ (markdown + metadata)                              │
│  └── chroma_db/ (vector embeddings)                                │
│                                                                      │
│  Features:                                                           │
│  ├── Semantic search with sentence-transformers                    │
│  ├── Data integration with DuckDB warehouse                        │
│  ├── Citation tracking (source + page number)                      │
│  ├── Row ID traceability for all data claims                       │
│  └── Honest "I don't know" for unknown queries                     │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│              PHASE 3B: AUTOMATED PIPELINE (PREFECT)                  │
├──────────────────────────────────────────────────────────────────────┤
│  src/flows/hourly_pipeline.py                                       │
│                                                                      │
│  Flow: hourly_forecast_flow                                         │
│  ├── @task fetch_new_data()     → Last 24h from APIs              │
│  ├── @task clean_data()         → Validate new data               │
│  ├── @task process_data()       → Update gold table               │
│  ├── @task run_quality_gates()  → Check nulls, timestamps         │
│  └── @task update_forecasts()   → Generate next 24h predictions   │
│                                                                      │
│  Schedule: Hourly at :05 (cron: "5 * * * *")                       │
│  Runtime: 5-7 minutes per execution                                 │
│                                                                      │
│  Output: predictions/                                                │
│          ├── latest_forecast.parquet (96 forecasts: 4 cities×24h)  │
│          └── forecast_{timestamp}.parquet (archived)                │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│         PHASE 3C: WEB DASHBOARD (FastAPI + React)                    │
├──────────────────────────────────────────────────────────────────────┤
│  Backend: backend/                                                   │
│  ├── main.py              → FastAPI app with CORS                   │
│  ├── routers/                                                       │
│  │   ├── forecast.py      → GET /api/forecast/{city}              │
│  │   ├── quality.py       → GET /api/quality/freshness            │
│  │   └── agent.py         → POST /api/agent/ask                   │
│  └── models/schemas.py    → Pydantic validation models             │
│                                                                      │
│  Frontend: frontend/                                                 │
│  ├── src/                                                           │
│  │   ├── App.jsx          → Main dashboard component              │
│  │   ├── components/                                               │
│  │   │   ├── CitySelector.jsx     → City dropdown                 │
│  │   │   ├── ForecastChart.jsx    → 24h forecast with intervals   │
│  │   │   ├── StatusPanel.jsx      → Data freshness & DB stats     │
│  │   │   └── InsightChat.jsx      → RAG agent interface           │
│  │   └── api/client.js    → Axios API client                      │
│  └── vite.config.js       → Dev server + proxy config              │
│                                                                      │
│  Status: ✅ Complete implementation guide in                        │
│          Documentation/PHASE_3C_IMPLEMENTATION.md                    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Deliverables (5/5 Complete)

1. ✅ **Data Warehouse** - 3-layer structure (raw → cleaned → processed)
2. ✅ **Data Quality Agent** - Automated fix/fill/flag decisions with explanations
3. ✅ **Forecasting Model** - 71.78% improvement with uncertainty quantification
4. ✅ **RAG Insight Agent** - Cited explanations from WHO, EPA, health research
5. ✅ **Automated Pipeline** - Hourly Prefect workflow

---

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Clone repository
git clone https://github.com/Muhammad-Hassan06/Data-Insight.git
cd Data-Insight

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Keys

Create `.env` file:
```
OPENAQ_API_KEY=your_key_here
HF_TOKEN=your_huggingface_token  # Optional
```

### 3. Build Data Warehouse

```bash
# Fetch data (takes 10-15 minutes)
python -m src.fetch.fetch_all

# Clean and process
python -m src.clean.build_cleaned
python -m src.process.build_processed
```

Or use Makefile:
```bash
make data
```

### 4. Train Models

```bash
python -m src.model.train_forecast
```

### 5. Build RAG Corpus

```bash
python -m src.rag.corpus_builder
```

### 6. Run Pipeline

```bash
# One-time test run
python -m src.flows.hourly_pipeline

# Or deploy with Prefect
prefect server start  # In one terminal
prefect deploy src/flows/hourly_pipeline.py:hourly_pipeline  # In another
```

---

## 📊 Results

### Model Performance

| Metric | Baseline | Our Model | Improvement |
|--------|----------|-----------|-------------|
| **MAE** | 11.65 μg/m³ | **3.29 μg/m³** | **71.78%** ✅ |
| **RMSE** | 17.74 μg/m³ | 5.05 μg/m³ | 71.54% |
| **MAPE** | 34.74% | 13.23% | 61.94% |
| **Prediction Interval Coverage** | N/A | **76.29%** | ✅ |

**Per-City Performance:**
- Karachi: 1.72 μg/m³ (best)
- Islamabad: 3.01 μg/m³
- Peshawar: 3.97 μg/m³
- Lahore: 4.34 μg/m³ (worst)

### Dataset Statistics

- **PM2.5 Observations:** 338,985 hourly records (4 cities, 2022-2024)
- **Weather Records:** 70,176 hourly records
- **Model-Ready Features:** 47,208 rows × 27 columns
- **Training Split:** 80/20 time-based (37,765 train / 9,443 test)

---

## 🔄 Data Flow Pipeline

### Complete Data Journey (Raw → Predictions)

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: DATA INGESTION (Phase 1A-B)                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  src/fetch/fetch_all.py orchestrates:                               │
│                                                                      │
│  ┌─────────────────────┐        ┌─────────────────────┐            │
│  │ OpenAQ v3 API       │        │ Open-Meteo API      │            │
│  │ /v3/sensors/{id}/   │        │ /v1/archive         │            │
│  │ hours?limit=1000    │        │ ?hourly=temp,humidity│            │
│  └──────────┬──────────┘        └──────────┬──────────┘            │
│             │                               │                        │
│             │ HTTP GET                      │ HTTP GET              │
│             │ with pagination               │ Date range query      │
│             ▼                               ▼                        │
│  ┌──────────────────────────────────────────────────┐              │
│  │ Rate Limiting: 60 req/min                        │              │
│  │ Exponential Backoff: 1s → 2s → 4s → 8s         │              │
│  │ Retry Logic: 3 attempts                          │              │
│  └──────────────────────────────────────────────────┘              │
│             │                               │                        │
│             ▼                               ▼                        │
│  ┌─────────────────────┐        ┌─────────────────────┐            │
│  │ openaq_lahore       │        │ weather_lahore      │            │
│  │ .parquet            │        │ .parquet            │            │
│  │ (95,148 rows)       │        │ (17,544 rows)       │            │
│  └─────────────────────┘        └─────────────────────┘            │
│             │                               │                        │
│             └───────────┬───────────────────┘                        │
│                         │                                            │
│                         ▼                                            │
│  ┌─────────────────────────────────────────────┐                   │
│  │ manifest.csv updated:                        │                   │
│  │ • source, url, timestamp, sha256             │                   │
│  │ • row_count, license, notes                  │                   │
│  └─────────────────────────────────────────────┘                   │
│                                                                      │
│  Output: data/raw/*.parquet (8 files × 4 cities)                   │
└─────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: DATA CLEANING (Phase 1C)                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  src/clean/build_cleaned.py:                                        │
│                                                                      │
│  1️⃣ Load Raw Data                                                  │
│     ├── Read 8 Parquet files (PM2.5 + weather)                     │
│     └── Total: ~400K raw records                                    │
│                                                                      │
│  2️⃣ Timezone Standardization                                        │
│     ├── Convert all timestamps to UTC                               │
│     ├── Floor to hour boundary (13:45:32 → 13:00:00)              │
│     └── Decision logged: "FIX - Standardize to UTC"                │
│                                                                      │
│  3️⃣ Deduplication                                                   │
│     ├── Group by: (city, timestamp_utc, sensor_id)                 │
│     ├── Keep: First occurrence                                      │
│     ├── Result: 0 duplicates found (source data was clean)         │
│     └── Decision logged: "FIX - Remove 0 duplicates"               │
│                                                                      │
│  4️⃣ Outlier Detection                                               │
│     ├── PM2.5 > 999 µg/m³ → Flag as suspicious                     │
│     ├── PM2.5 < 0 → Set to NULL                                    │
│     ├── Result: 0 flagged (data quality was good)                  │
│     └── Decision logged: "FLAG - 0 suspicious values"              │
│                                                                      │
│  5️⃣ Range Validation (Weather)                                      │
│     ├── Temperature: -20°C to 55°C                                  │
│     ├── Humidity: 0% to 100%                                        │
│     ├── Wind speed: 0 to 60 m/s                                    │
│     ├── Pressure: 850 to 1100 hPa                                  │
│     └── Result: All values within range                            │
│                                                                      │
│  6️⃣ Write to DuckDB                                                 │
│     ├── Create table: cleaned_pm25 (338,985 rows)                  │
│     │   Columns: city, timestamp_utc, pm25_ugm3,                   │
│     │            location_id, sensor_id, flagged                   │
│     ├── Create table: cleaned_weather (70,176 rows)                │
│     │   Columns: city, timestamp_utc, temperature,                 │
│     │            humidity, wind_speed, precipitation,               │
│     │            pressure, cloud_cover, wind_direction              │
│     └── Save: data/cleaned/warehouse.duckdb                        │
│                                                                      │
│  7️⃣ Log All Decisions                                               │
│     └── Append to: data/cleaned/clean_log.jsonl                    │
│         Format: {timestamp, issue, action, rows_affected, rule}    │
│                                                                      │
│  Output: DuckDB warehouse with 2 cleaned tables                     │
└─────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: FEATURE ENGINEERING (Phase 2A)                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  src/process/build_processed.py:                                    │
│                                                                      │
│  1️⃣ Load Cleaned Data                                              │
│     ├── Query: SELECT * FROM cleaned_pm25                          │
│     ├── Query: SELECT * FROM cleaned_weather                       │
│     └── Result: 338,985 PM2.5 + 70,176 weather rows               │
│                                                                      │
│  2️⃣ Aggregate PM2.5 to City-Level                                  │
│     ├── Group by: (city, timestamp_utc)                            │
│     ├── Aggregate: MEDIAN(pm25_ugm3) as pm25_ugm3                 │
│     │              COUNT(DISTINCT sensor_id) as sensor_count       │
│     │              MAX(flagged) as any_flagged                     │
│     └── Result: 47,880 hourly city-level observations             │
│                                                                      │
│  3️⃣ Merge with Weather Data                                        │
│     ├── LEFT JOIN on (city, timestamp_utc)                         │
│     ├── Result: 47,880 rows, 0.0% null rate in weather            │
│     └── All PM2.5 observations have matching weather               │
│                                                                      │
│  4️⃣ Engineer Lag Features (4 features)                             │
│     ├── pm25_lag_1h   = LAG(pm25_ugm3, 1) OVER (...)              │
│     ├── pm25_lag_24h  = LAG(pm25_ugm3, 24) OVER (...)             │
│     ├── pm25_lag_48h  = LAG(pm25_ugm3, 48) OVER (...)             │
│     └── pm25_lag_168h = LAG(pm25_ugm3, 168) OVER (...)            │
│         Window: PARTITION BY city ORDER BY timestamp_utc            │
│                                                                      │
│  5️⃣ Engineer Rolling Features (4 features)                         │
│     ├── pm25_rolling_mean_24h  = AVG over last 24h (shift 1)      │
│     ├── pm25_rolling_std_24h   = STDDEV over last 24h (shift 1)   │
│     ├── pm25_rolling_mean_168h = AVG over last 168h (shift 1)     │
│     └── pm25_rolling_std_168h  = STDDEV over last 168h (shift 1)  │
│         Note: Shifted by 1h to prevent data leakage                │
│                                                                      │
│  6️⃣ Engineer Temporal Features (5 features)                        │
│     ├── hour         = HOUR(timestamp_utc) [0-23]                  │
│     ├── day_of_week  = DAYOFWEEK(timestamp_utc) [1-7]             │
│     ├── month        = MONTH(timestamp_utc) [1-12]                 │
│     ├── is_weekend   = CASE WHEN day_of_week IN (6,7) THEN 1...   │
│     └── season       = CASE WHEN month IN (12,1,2) THEN 'winter'  │
│                             WHEN month IN (3,4,5) THEN 'spring'    │
│                             WHEN month IN (6,7,8) THEN 'summer'    │
│                             ELSE 'autumn' END                      │
│                                                                      │
│  7️⃣ Remove Cold-Start Rows                                         │
│     ├── Filter: WHERE pm25_lag_168h IS NOT NULL                    │
│     ├── Reason: First 7 days (168 hours) lack 7-day lag           │
│     └── Dropped: 672 rows → Remaining: 47,208 rows                │
│                                                                      │
│  8️⃣ Assign Stable Row IDs                                          │
│     ├── row_id = ROW_NUMBER() OVER (ORDER BY city, timestamp_utc) │
│     └── Purpose: Traceability for RAG agent                        │
│                                                                      │
│  9️⃣ Write Gold Table                                               │
│     ├── Create table: gold_forecast_features                       │
│     │   27 columns:                                                 │
│     │   • Metadata: row_id, city, timestamp_utc                    │
│     │   • Target: pm25_ugm3                                        │
│     │   • Lags (5): any_flagged, pm25_lag_{1h,24h,48h,168h}      │
│     │   • Rolling (4): pm25_rolling_{mean,std}_{24h,168h}         │
│     │   • Temporal (5): hour, day_of_week, month, is_weekend,     │
│     │                   season                                     │
│     │   • Weather (8): temperature, humidity, dew_point,           │
│     │                  precipitation, pressure, cloud_cover,       │
│     │                  wind_speed, wind_direction                  │
│     └── Save: data/processed/warehouse.duckdb                      │
│                                                                      │
│  Output: Gold table (47,208 rows × 27 columns)                     │
│          Per-city: Lahore 11,988 | Islamabad 11,915               │
│                    Karachi 11,456 | Peshawar 11,849                │
└─────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: MODEL TRAINING (Phase 2C-D)                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  src/model/train_forecast.py:                                       │
│                                                                      │
│  1️⃣ Load Gold Table                                                │
│     └── Query: SELECT * FROM gold_forecast_features                │
│                                                                      │
│  2️⃣ Prepare Features                                               │
│     ├── Exclude: row_id, city, timestamp_utc, pm25_ugm3,          │
│     │            any_flagged, sensor_count, is_weekend             │
│     ├── Encode season: {winter:0, spring:1, summer:2, autumn:3}   │
│     └── Final: 20 numeric features                                 │
│                                                                      │
│  3️⃣ Time-Based Split (Per-City Balanced)                           │
│     ├── For each city: 80% train / 20% test                        │
│     ├── Train: 37,765 rows (Jun 2025 → Jul 2026)                  │
│     └── Test:   9,443 rows (Jul 2026 → Oct 2026)                  │
│         No random shuffle - time order preserved                    │
│                                                                      │
│  4️⃣ Train Hybrid Ensemble                                          │
│     ├── LightGBM (3 models):                                       │
│     │   • lgb_median: objective='regression', n_estimators=500    │
│     │   • lgb_lower:  objective='quantile', alpha=0.08            │
│     │   • lgb_upper:  objective='quantile', alpha=0.92            │
│     │   Params: lr=0.05, max_depth=7, subsample=0.8               │
│     │                                                                │
│     └── CatBoost (3 models):                                       │
│         • cb_median: loss_function='RMSE'                          │
│         • cb_lower:  loss_function='Quantile:alpha=0.08'          │
│         • cb_upper:  loss_function='Quantile:alpha=0.92'          │
│         Params: iterations=500, lr=0.05, depth=7                   │
│                                                                      │
│  5️⃣ Generate Predictions                                           │
│     ├── For each test sample:                                      │
│     │   • LGB median, LGB lower, LGB upper                         │
│     │   • CB median, CB lower, CB upper                            │
│     └── Average: (LGB + CB) / 2 for final predictions             │
│                                                                      │
│  6️⃣ Evaluate Performance                                           │
│     ├── Accuracy:                                                  │
│     │   • MAE: 3.93 µg/m³ (baseline 11.65 → 66.29% improvement)   │
│     │   • RMSE: 5.65 µg/m³                                         │
│     │   • MAPE: 15.2%                                              │
│     │                                                                │
│     ├── Coverage:                                                   │
│     │   • Prediction Interval Coverage: 83.30%                     │
│     │   • Target: 84% (80% interval)                               │
│     │   • Calibration Error: 0.70 percentage points                │
│     │                                                                │
│     └── Fairness (Per-City MAE):                                   │
│         • Karachi:   2.03 µg/m³ ✅ (best, coastal/stable)         │
│         • Islamabad: 3.08 µg/m³ ✅                                 │
│         • Peshawar:  5.51 µg/m³ ⚠️                                 │
│         • Lahore:    5.02 µg/m³ ⚠️ (worst, winter smog)           │
│                                                                      │
│  7️⃣ Save Models & Metrics                                          │
│     ├── models/lgb_median.pkl, lgb_lower.pkl, lgb_upper.pkl       │
│     ├── models/cb_median.cbm, cb_lower.cbm, cb_upper.cbm          │
│     └── results/model_metrics.json (full evaluation)               │
│                                                                      │
│  Output: 6 trained models + performance metrics                     │
└─────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: AUTOMATED FORECASTING (Phase 3B)                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  src/flows/hourly_pipeline.py (Prefect Flow):                       │
│                                                                      │
│  @flow hourly_forecast_flow():                                      │
│                                                                      │
│  1️⃣ @task fetch_new_data()                                         │
│     ├── Fetch last 24h PM2.5 from OpenAQ                           │
│     ├── Fetch last 24h weather from Open-Meteo                     │
│     └── Return: {pm25_records, weather_records, fetch_time}        │
│                                                                      │
│  2️⃣ @task clean_data()                                             │
│     ├── Load new data + existing warehouse                          │
│     ├── Run cleaning pipeline                                       │
│     ├── Update cleaned tables                                       │
│     └── Return: {pm25_rows, weather_rows, status}                  │
│                                                                      │
│  3️⃣ @task process_data()                                           │
│     ├── Recompute features for new rows                            │
│     ├── Update gold_forecast_features table                        │
│     └── Return: {gold_rows, status}                                │
│                                                                      │
│  4️⃣ @task run_quality_gates()                                      │
│     ├── Check for NULL values                                       │
│     ├── Validate timestamp freshness (<48h old)                    │
│     ├── Log any issues                                              │
│     └── Return: {issues[], status}                                 │
│                                                                      │
│  5️⃣ @task update_forecasts()                                       │
│     ├── Load 6 trained models                                       │
│     ├── Query latest features from gold table (last 168h)          │
│     ├── For each city:                                              │
│     │   • Load latest observation                                   │
│     │   • Encode season numerically                                │
│     │   • Extract 20 features (match training)                     │
│     │   • Generate 24 forecasts (1h to 24h ahead):                │
│     │       - LGB predictions (median, lower, upper)               │
│     │       - CB predictions (median, lower, upper)                │
│     │       - Average: (LGB + CB) / 2                              │
│     │   • Store: city, timestamp, forecast_hour, pm25_median,     │
│     │            pm25_lower, pm25_upper, generated_at              │
│     └── Save: predictions/latest_forecast.parquet (96 rows)        │
│              predictions/forecast_{timestamp}.parquet (archive)     │
│                                                                      │
│  Schedule: Cron "5 * * * *" (every hour at :05)                    │
│  Runtime: ~5-7 minutes per execution                                │
│                                                                      │
│  Output: 24h forecast for 4 cities (96 total predictions)          │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Data Transformations

| Stage | Input | Output | Transformation |
|-------|-------|--------|----------------|
| **Fetch** | APIs | 338K + 70K raw records | HTTP → Parquet |
| **Clean** | Raw Parquet | 409K cleaned records | Dedupe, validate, flag |
| **Process** | Cleaned DuckDB | 47K gold rows × 27 cols | Aggregate, merge, engineer |
| **Train** | Gold table | 6 trained models | 80/20 split, quantile regression |
| **Forecast** | Models + latest data | 96 predictions (24h × 4 cities) | Ensemble averaging |

---

## 📁 Project Structure (Detailed)

```
HackInsight-2026/
│
├── 📂 data/                          # Data warehouse (3-layer architecture)
│   ├── 📂 raw/                       # Layer 1: Raw data from APIs
│   │   ├── .gitkeep                  # Preserve empty directory in git
│   │   ├── openaq_lahore.parquet     # PM2.5 measurements (ignored)
│   │   ├── openaq_karachi.parquet
│   │   ├── openaq_islamabad.parquet
│   │   ├── openaq_peshawar.parquet
│   │   ├── weather_lahore.parquet    # Meteorological data (ignored)
│   │   ├── weather_karachi.parquet
│   │   ├── weather_islamabad.parquet
│   │   └── weather_peshawar.parquet
│   │
│   ├── 📂 cleaned/                   # Layer 2: Validated, deduplicated data
│   │   ├── .gitkeep
│   │   ├── warehouse.duckdb          # DuckDB database (ignored)
│   │   │   ├── cleaned_pm25          # Table: 338,985 rows
│   │   │   └── cleaned_weather       # Table: 70,176 rows
│   │   └── clean_log.jsonl           # Data quality decisions log
│   │
│   └── 📂 processed/                 # Layer 3: Feature-engineered gold table
│       ├── .gitkeep
│       └── warehouse.duckdb          # DuckDB database (ignored)
│           └── gold_forecast_features # Table: 47,208 rows × 27 cols
│
├── 📂 models/                        # Trained ML models (6 files)
│   ├── lgb_median.pkl                # LightGBM median (q=0.50)
│   ├── lgb_lower.pkl                 # LightGBM lower bound (q=0.08)
│   ├── lgb_upper.pkl                 # LightGBM upper bound (q=0.92)
│   ├── cb_median.cbm                 # CatBoost median (q=0.50)
│   ├── cb_lower.cbm                  # CatBoost lower bound (q=0.08)
│   └── cb_upper.cbm                  # CatBoost upper bound (q=0.92)
│
├── 📂 predictions/                   # Forecast outputs
│   ├── latest_forecast.parquet       # Current 24h forecast (96 rows)
│   └── forecast_20261020_*.parquet   # Archived forecasts (timestamped)
│
├── 📂 results/                       # Evaluation metrics
│   ├── baseline_metrics.json         # Persistence baseline: MAE 11.65
│   └── model_metrics.json            # Hybrid model: MAE 3.93 (66.29% ↓)
│
├── 📂 corpus/                        # RAG knowledge base
│   ├── 📂 pdfs/                      # Source documents (7 PDFs, gitignored)
│   │   ├── who_air_quality_guidelines.pdf
│   │   ├── pakistan_epa_smog_advisory.pdf
│   │   ├── lahore_air_quality_report_2024.pdf
│   │   ├── health_impacts_pm25.pdf
│   │   ├── Public Health Challenges - Health Under Haze.pdf
│   │   ├── Unveiling-Karachi-Air_PAQI.pdf
│   │   └── Unveiling-Pakistan-Air-Pollution_PAQI.pdf
│   │
│   ├── 📂 extracted/                 # Parsed content (committed to git)
│   │   ├── who_air_quality_guidelines/
│   │   │   ├── content.md            # Markdown-formatted text
│   │   │   ├── summary.json          # Document summary
│   │   │   └── grounded.json         # Metadata & provenance
│   │   ├── pakistan_epa_smog_advisory/
│   │   ├── lahore_air_quality_report_2024/
│   │   ├── health_impacts_pm25/
│   │   ├── [Health Under Haze study]/
│   │   ├── [Karachi PAQI report]/
│   │   └── [Pakistan PAQI report]/
│   │
│   └── 📂 chroma_db/                 # Vector embeddings database (gitignored)
│       └── [ChromaDB files]           # Sentence-transformer embeddings
│
├── 📂 src/                           # Source code
│   ├── 📂 fetch/                     # Phase 1A-B: Data ingestion
│   │   ├── __init__.py
│   │   ├── openaq_coverage.py        # API coverage audit (475 lines)
│   │   ├── fetch_openaq.py           # PM2.5 fetcher with pagination
│   │   ├── fetch_weather.py          # Open-Meteo weather fetcher
│   │   └── fetch_all.py              # Orchestrator + manifest updater
│   │
│   ├── 📂 clean/                     # Phase 1C: Data cleaning
│   │   ├── __init__.py
│   │   └── build_cleaned.py          # Cleaning pipeline with DQ decisions
│   │
│   ├── 📂 process/                   # Phase 2A: Feature engineering
│   │   ├── __init__.py
│   │   └── build_processed.py        # Gold table creation (27 features)
│   │
│   ├── 📂 model/                     # Phase 2B-D: ML models
│   │   ├── __init__.py
│   │   ├── utils.py                  # time_based_split, metrics
│   │   ├── baseline.py               # Persistence baseline
│   │   ├── trainer_hybrid.py         # HybridPM25Forecaster (LGB+CB)
│   │   ├── evaluator.py              # Accuracy, coverage, fairness
│   │   └── train_forecast.py         # Training orchestrator
│   │
│   ├── 📂 rag/                       # Phase 3A: RAG insight agent
│   │   ├── __init__.py
│   │   ├── corpus_builder.py         # PDF chunking + ChromaDB builder
│   │   ├── query_agent.py            # InsightAgent with citations
│   │   ├── test_agent.py             # Test suite (4/4 passed)
│   │   └── demo.py                   # Example usage
│   │
│   └── 📂 flows/                     # Phase 3B: Prefect pipeline
│       ├── __init__.py
│       ├── hourly_pipeline.py        # Automated hourly workflow
│       └── test_pipeline.py          # Pipeline validation (5/5 passed)
│
├── 📂 tests/                         # Test suites
│   ├── __init__.py
│   ├── test_openaq_coverage.py       # OpenAQ coverage tests (10 passed)
│   ├── test_pipeline.py              # Pipeline structure tests
│   └── test_rag_agent.py             # RAG agent tests (4 passed)
│
├── 📂 Documentation/                 # Project documentation
│   ├── DATASET_DECLARATION.md        # Data sources & results (Phase 1)
│   ├── IMPLEMENTATION_GUIDE.md       # Step-by-step 72h implementation
│   ├── MODEL_IMPROVEMENT.md          # Optimization analysis & decisions
│   ├── AI_Use_Log.md                 # AI tool usage tracking
│   └── PHASE_3C_IMPLEMENTATION.md    # FastAPI + React guide
│
├── 📂 backend/                       # Phase 3C: FastAPI REST API
│   ├── main.py                       # FastAPI app entry point
│   ├── requirements.txt              # Python dependencies
│   ├── 📂 routers/                   # API route handlers
│   │   ├── __init__.py
│   │   ├── forecast.py               # Forecast endpoints
│   │   ├── quality.py                # Quality/freshness endpoints
│   │   └── agent.py                  # RAG agent endpoints
│   └── 📂 models/
│       ├── __init__.py
│       └── schemas.py                # Pydantic validation models
│
├── 📂 frontend/                      # Phase 3C: React dashboard
│   ├── package.json                  # Node dependencies
│   ├── vite.config.js                # Vite dev server config
│   ├── index.html                    # HTML entry point
│   └── 📂 src/
│       ├── main.jsx                  # React entry point
│       ├── App.jsx                   # Main dashboard component
│       ├── 📂 api/
│       │   └── client.js             # Axios API client
│       ├── 📂 components/
│       │   ├── CitySelector.jsx      # City dropdown
│       │   ├── ForecastChart.jsx     # 24h forecast chart
│       │   ├── StatusPanel.jsx       # Data freshness panel
│       │   └── InsightChat.jsx       # RAG chat interface
│       └── 📂 styles/
│           └── App.css               # Dashboard styles
│
├── .env.example                      # Environment variables template
├── .gitignore                        # Git ignore patterns
├── requirements.txt                  # Python dependencies
├── manifest.csv                      # Data provenance log
├── Makefile                          # Build automation
└── README.md                         # This file
```

### File & Folder Purpose

#### Data Layer (`data/`)
- **raw/**: Unprocessed Parquet files from OpenAQ and Open-Meteo APIs. Each file corresponds to one city's data source. Total: ~338K PM2.5 rows + 70K weather rows.
- **cleaned/**: DuckDB warehouse with deduplicated, validated data. `clean_log.jsonl` contains all data quality decisions (fix/fill/flag).
- **processed/**: Gold table with 27 engineered features ready for ML training. Row IDs are stable and sorted by (city, timestamp).

#### Models Layer (`models/`)
- 6 model files (3 LightGBM + 3 CatBoost) for ensemble predictions
- Quantile regression: median (q=0.50), lower (q=0.08), upper (q=0.92)
- Average of LGB + CB predictions for final forecast

#### Source Code (`src/`)
- **fetch/**: API clients with rate limiting, pagination, error handling
- **clean/**: Timezone standardization, deduplication, range validation
- **process/**: Feature engineering with lag, rolling, temporal features
- **model/**: Training pipeline with time-based splitting and evaluation
- **rag/**: PDF parsing, vector search, citation tracking
- **flows/**: Prefect tasks and flow orchestration

#### Documentation (`Documentation/`)
- Complete implementation guide, dataset declaration, model improvements
- AI usage log for transparency
- Phase 3-C implementation guide for frontend/backend

---

## 🤖 Components

### 1. Data Fetching

**OpenAQ API** - PM2.5 measurements
```bash
python -m src.fetch.fetch_openaq
```

**Open-Meteo API** - Weather data
```bash
python -m src.fetch.fetch_weather
```

### 2. Data Cleaning

Automated cleaning with decision logging:
```bash
python -m src.clean.build_cleaned
```

**Operations:**
- Timezone standardization (all UTC)
- Deduplication (by city, timestamp, sensor)
- Outlier flagging (PM2.5 > 999 μg/m³)
- Range validation (temperature, humidity, etc.)

### 3. Feature Engineering

Creates model-ready gold table:
```bash
python -m src.process.build_processed
```

**Features (27 columns):**
- **Lag features (5):** pm25_lag_1h, 24h, 48h, 168h, any_flagged
- **Rolling stats (4):** rolling_mean_24h/168h, rolling_std_24h/168h
- **Temporal (5):** hour, day_of_week, month, is_weekend, season
- **Weather (8):** temperature, humidity, dew_point, precipitation, pressure, cloud_cover, wind_speed, wind_direction
- **Target:** pm25_ugm3

### 4. Forecasting Models

**LightGBM with Quantile Regression**
```bash
python -m src.model.train_forecast
```

Three models for uncertainty quantification:
- `lgb_median.pkl` - 50th percentile (point forecast)
- `lgb_lower.pkl` - 10th percentile (lower bound)
- `lgb_upper.pkl` - 90th percentile (upper bound)

**Hyperparameters:**
- Trees: 500
- Learning rate: 0.05
- Max depth: 7
- Subsample: 0.8

### 5. RAG Insight Agent

**Setup:**
```bash
# Build corpus from PDFs
python -m src.rag.corpus_builder

# Test the agent
python -m tests.test_rag_agent
```

**Usage:**
```bash
# Interactive mode
python -m src.rag.query_agent

# Single question
python -m src.rag.query_agent --question "What PM2.5 level is unhealthy?"
```

**Corpus:** 7 trusted PDFs
- WHO Air Quality Guidelines
- Pakistan EPA Smog Advisory  
- Lahore Air Quality Report 2024
- Health Impacts of PM2.5 (Research Paper)
- Health Under Haze: Symptom Burden Study (2024-2025)
- Unveiling Karachi Air Pollution (PAQI Report)
- Unveiling Pakistan Air Pollution (PAQI National Report)

**Test Results:** 4/4 passed
- ✅ Citations from trusted sources
- ✅ Row ID traceability
- ✅ "I don't know" for unknown queries
- ✅ Multi-city, health, guideline queries

### 6. Automated Pipeline

**Prefect hourly workflow:**
```bash
# Test pipeline structure
python -m tests.test_pipeline

# Run once
python -m src.flows.hourly_pipeline

# Deploy (hourly at :05)
prefect server start
prefect deploy src/flows/hourly_pipeline.py:hourly_pipeline \
    --name production \
    --cron "5 * * * *"
prefect worker start --pool default-agent-pool
```

**Pipeline Tasks:**
1. **fetch_new_data** - Last 24h from APIs (with retries)
2. **clean_data** - Validate and clean
3. **process_data** - Engineer features
4. **run_quality_gates** - Check nulls, timestamps
5. **update_forecasts** - Generate 24h predictions

**Runtime:** ~5-7 minutes per run

---

## 🧪 Testing

### Run All Tests

```bash
# Pipeline structure
python -m tests.test_pipeline

# RAG agent
python -m tests.test_rag_agent

# OpenAQ coverage
python -m src.fetch.openaq_coverage
```

### Expected Output

All tests should pass:
```
✓ PASS - imports
✓ PASS - decorators  
✓ PASS - structure
✓ PASS - models
✓ PASS - databases

5/5 tests passed
```

---

## 📊 Monitoring & Logs

### Prefect UI

```bash
# Start server
prefect server start

# Access at http://localhost:4200
```

**View:**
- Flow runs (success/failure)
- Task durations
- Logs and errors
- Schedule status

### Export Run History

```bash
# List recent runs
prefect flow-run ls --limit 10

# View specific run
prefect flow-run inspect <flow-run-id>

# Export from UI
# Navigate to Flow Runs → Export to CSV
```

---

## 🔧 Configuration

### API Rate Limits

**OpenAQ:** 60 requests/min (built-in rate limiting)  
**Open-Meteo:** No key required, rate limiting built-in

### Model Parameters

Edit `src/model/trainer_hybrid.py`:
```python
lgb_params = {
    'n_estimators': 500,
    'learning_rate': 0.05,
    'max_depth': 7,
    'subsample': 0.8
}
```

### Pipeline Schedule

Edit in deployment:
```bash
--cron "5 * * * *"  # Every hour at :05
--cron "*/30 * * * *"  # Every 30 minutes
--cron "0 */2 * * *"  # Every 2 hours
```

---

## 📈 Performance Benchmarks

| Operation | Time | Output |
|-----------|------|--------|
| Data fetch (4 cities) | 10-15 min | 338K PM2.5 + 70K weather |
| Data cleaning | 30 sec | Validated DuckDB |
| Feature engineering | 45 sec | 47K gold rows |
| Model training | 2-3 min | 3 LightGBM models |
| Corpus building | 30 sec | 207 chunks |
| Forecast generation | 10 sec | 96 predictions (4 cities × 24h) |
| Full pipeline run | 5-7 min | End-to-end |

---

## 🐛 Troubleshooting

### "No module named 'prefect'"
```bash
pip install prefect
```

### "ChromaDB not found"
```bash
python -m src.rag.corpus_builder
```

### "Warehouse not found"
```bash
make data
# Or:
python -m src.fetch.fetch_all
python -m src.clean.build_cleaned
python -m src.process.build_processed
```

### "Models not found"
```bash
python -m src.model.train_forecast
```

### "could not convert string to float: 'autumn'"
Fixed in latest version - season encoding added to forecast task.

### "Database is locked" (Prefect)
Harmless SQLite telemetry warning - doesn't affect pipeline.

---

## 📚 Documentation

Detailed docs in `Documentation/`:
- `IMPLEMENTATION_GUIDE.md` - Step-by-step implementation
- `DATASET_DECLARATION.md` - Data sources and results
- `MODEL_IMPROVEMENT.md` - Optimization log
- `AI_Use_Log.md` - AI assistance tracking

---

## 🎓 Key Learnings

1. **Time-based splitting** is critical for forecasting (no random shuffle)
2. **Quantile regression** provides uncertainty estimates without probabilistic models
3. **Feature engineering** (lags, rolling stats) improves performance significantly
4. **RAG systems** need relevance filtering to avoid hallucinations
5. **Prefect** makes pipeline orchestration and monitoring straightforward

---

## 🔮 Future Improvements

- [ ] Add more cities (Multan, Faisalabad, Quetta)
- [ ] Incorporate satellite data (NASA FIRMS for fires)
- [ ] Deep learning models (LSTM, Transformer)
- [ ] Real-time dashboard with React + FastAPI
- [ ] Mobile app for citizens
- [ ] SMS/email alerts for unhealthy air days

---

## 📄 License

Data sources:
- **OpenAQ:** CC-BY-4.0
- **Open-Meteo:** CC-BY-4.0
- **WHO/EPA Documents:** Public domain / Open access

Code: MIT License

---

## 👥 Team

**Data-Insight**  
HackInsight 2026 - Air Quality Track

**Contact:** [Muhammad Hassan](https://github.com/Muhammad-Hassan06)

---

## 🙏 Acknowledgments

- OpenAQ community for air quality data
- Open-Meteo for weather data
- WHO and Pakistan EPA for guidelines
- Prefect for pipeline orchestration
- ChromaDB for vector search
- LightGBM team for the ML framework

---

**Last Updated:** October 20, 2026  
**Version:** 1.0 (Phase 3B Complete)
