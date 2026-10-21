---
title: Data Insight - Air Quality PM2.5 Forecaster
emoji: 🌫️
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 4.19.2
app_file: app.py
pinned: false
license: mit
---

# Data-Insight: Pakistan Air Quality & PM2.5 Forecaster

A real-time 24-hour PM2.5 forecasting dashboard with uncertainty quantification (quantile regression) and grounded RAG air quality insights for major Pakistani cities (Lahore, Karachi, Islamabad, Peshawar).

## Architecture
- **Model**: Hybrid Quantile Ensemble (LightGBM + CatBoost, 20 features)
- **Baseline**: 24-hour Persistence ($y[t] = y[t-24\text{h}]$)
- **Metrics**: MAE 3.93 µg/m³ (66.29% improvement vs baseline 11.65 µg/m³)
- **Coverage**: 83.3% within 80% prediction interval
- **Feature Store**: DuckDB warehouse with OpenAQ and Open-Meteo feeds
