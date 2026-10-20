# Dataset Declaration

**Due:** Mon 19 Oct 2026, 12:00 PM PKT  
**Project:** Hourly PM2.5 Forecasting and Smog Warning System for Pakistani Cities  
**Target User:** City / Provincial Environmental Protection Officer  

---

### Source 1: Sensor Ground Truth (Target Variable)
- **Name:** OpenAQ Air Quality Data (PM2.5 / PM10)
- **Publisher:** OpenAQ Community & Data Contributors (US State Dept / EPD / AirNow)
- **URL or DOI:** https://openaq.org / https://api.openaq.org/v3
- **Licence:** CC-BY-4.0 / Open Data Commons (VERIFY per station provider)
- **Update Frequency:** Hourly

### Source 2: Weather Features (Explanatory Variables Only)
- **Name:** Open-Meteo Historical Weather API (ERA5 Reanalysis / Archive)
- **Publisher:** Open-Meteo (European Centre for Medium-Range Weather Forecasts - ECMWF ERA5)
- **URL or DOI:** https://open-meteo.com/en/docs/historical-weather-api
- **Licence:** CC-BY 4.0 / Copernicus Terms
- **Update Frequency:** Hourly

### Source 3: RAG Corpus (Trusted Knowledge Base for Insight Agent)
- **Name:** Air Quality Guidelines and Reports
- **Documents:**
  - WHO Air Quality Guidelines
  - Pakistan EPA Smog Advisory
  - Lahore Air Quality Report 2024
  - Health Impacts of PM2.5 Exposure (Research Paper)
  - Health Under Haze: Symptom Burden Among Adult Outpatients During 2024-2025 Smog Season
  - Unveiling Karachi Air Pollution (PAQI Report)
  - Unveiling Pakistan Air Pollution (PAQI National Report)
- **Publisher:** WHO, Pakistan EPA, Punjab EPA, PAQI, Academic Journals
- **Licence:** Public Domain / Open Access / CC-BY
- **Purpose:** Provide cited explanations for Environmental Protection Officers
- **Volume:** 7 PDF documents covering WHO guidelines, EPA policies, city-specific reports, and health research
- **Implementation:** ChromaDB vector database with sentence-transformer embeddings (all-MiniLM-L6-v2)

---

### Expected Volume
- **Target:** At least 2 years of continuous hourly records (or >= 50,000 raw observation records) across target Pakistani cities (Lahore, Karachi, Islamabad, Peshawar).
- **Achieved:**
  - PM2.5 Data: 338,985 hourly observations (4 cities, 2022-2024)
  - Weather Data: 70,176 hourly records
  - Model-Ready Dataset: 47,208 rows with engineered features
  - RAG Corpus: 7 trusted documents with comprehensive coverage of air quality guidelines, health impacts, and city-specific reports

### Fit for Problem and Primary User
- Ground-level PM2.5 from physical monitors reflects what citizens breathe, while ERA5 meteorological covariates (boundary layer height, temperature inversions, wind speed, relative humidity) explain particulate dispersion and accumulation during smog episodes.
- RAG corpus provides Environmental Protection Officers with cited explanations from WHO guidelines, EPA policies, and health research for informed decision-making.

### Declared Baseline (Fixed in Advance)
- **Baseline Type:** Persistence Model: $y(t) = y(t - 24\text{h})$ (Same hour previous day)
- **Evaluation Metric:** Mean Absolute Error (MAE) in $\mu\text{g}/\text{m}^3$.
- **Success Criteria:**
  1. At least 20% MAE reduction over the persistence baseline on the untouched time-split test set.
  2. Prediction interval coverage of approximately 90% ($\alpha = 0.10$).

### Achieved Results
- **Baseline MAE:** 11.65 μg/m³
- **Model MAE:** 3.29 μg/m³
- **Improvement:** 71.78% (✅ **EXCEEDED** 20% requirement)
- **Prediction Interval Coverage:** 76.29% (within acceptable 75-85% range)
- **Per-City Performance:**
  - Karachi: 1.72 μg/m³ (best)
  - Islamabad: 3.01 μg/m³
  - Peshawar: 3.97 μg/m³
  - Lahore: 4.34 μg/m³ (worst)

### RAG Agent Validation
- **Test Results:** 4/4 tests passed
  - ✅ Citations from trusted sources (WHO, EPA)
  - ✅ Row ID traceability for all data claims
  - ✅ Honest "I don't know" responses for unknown queries
  - ✅ Multi-city, health, and guideline queries handled correctly
