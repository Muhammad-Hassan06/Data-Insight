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

### Independent Source (Not on track list / auxiliary)
- **Name:** NASA FIRMS Fire Information for Resource Management System (Optional / Enrichment)
- **Publisher:** NASA Earthdata
- **URL or DOI:** https://firms.modaps.eosdis.nasa.gov
- **Licence:** NASA Open Data Policy (Public Domain)

---

### Expected Volume
- **Target:** At least 2 years of continuous hourly records (or >= 50,000 raw observation records) across target Pakistani cities (Lahore, Karachi, Islamabad, Peshawar).

### Fit for Problem and Primary User
- Ground-level PM2.5 from physical monitors reflects what citizens breathe, while ERA5 meteorological covariates (boundary layer height, temperature inversions, wind speed, relative humidity) explain particulate dispersion and accumulation during smog episodes.

### Declared Baseline (Fixed in Advance)
- **Baseline Type:** Persistence Model: $y(t) = y(t - 24\text{h})$ (Same hour previous day)
- **Evaluation Metric:** Mean Absolute Error (MAE) in $\mu\text{g}/\text{m}^3$.
- **Success Criteria:**
  1. At least 20% MAE reduction over the persistence baseline on the untouched time-split test set.
  2. Prediction interval coverage of approximately 90% ($\alpha = 0.10$).
