// Mock data for demo mode when backend is not available
// Uses realistic data based on the actual model metrics

export const CITIES = ['Lahore', 'Karachi', 'Islamabad', 'Peshawar'];

export const CITY_META = {
  Lahore: { flag: '🏙️', color: '#ef4444', lat: 31.5204, lon: 74.3587, population: '11.1M' },
  Karachi: { flag: '🌊', color: '#22c55e', lat: 24.8607, lon: 67.0011, population: '14.9M' },
  Islamabad: { flag: '⛰️', color: '#38bdf8', lat: 33.6844, lon: 73.0479, population: '1.1M' },
  Peshawar: { flag: '🕌', color: '#f59e0b', lat: 34.0151, lon: 71.5249, population: '2.0M' },
};

// Generate realistic 24h forecast data
function generateForecast(city) {
  const now = new Date();
  const basePM25 = {
    Lahore: 65, Karachi: 28, Islamabad: 42, Peshawar: 55,
  };
  const base = basePM25[city] || 40;

  const forecasts = [];
  for (let h = 0; h < 24; h++) {
    const time = new Date(now.getTime() + h * 3600000);
    const hour = time.getHours();

    // Simulate daily cycle: higher in morning/evening, lower midday
    const cycle = Math.sin(((hour - 6) * Math.PI) / 12) * 15;
    const noise = (Math.random() - 0.5) * 8;
    const median = Math.max(5, base + cycle + noise);
    const interval = 6 + Math.random() * 4;

    forecasts.push({
      timestamp: time.toISOString(),
      forecast_hour: h + 1,
      pm25_median: parseFloat(median.toFixed(2)),
      pm25_lower: parseFloat(Math.max(2, median - interval).toFixed(2)),
      pm25_upper: parseFloat((median + interval).toFixed(2)),
    });
  }

  return {
    city,
    forecasts,
    generated_at: now.toISOString(),
  };
}

export function getMockCityForecast(city) {
  return generateForecast(city);
}

export function getMockAllForecasts() {
  return { forecasts: CITIES.map(c => generateForecast(c)) };
}

export function getMockFreshness() {
  const now = new Date();
  return {
    pm25: {
      last_updated: new Date(now.getTime() - 1800000).toISOString(),
      row_count: 338985,
      status: 'fresh',
    },
    weather: {
      last_updated: new Date(now.getTime() - 2400000).toISOString(),
      row_count: 70176,
      status: 'fresh',
    },
  };
}

export function getMockStats() {
  return {
    cleaned: {
      pm25_rows: 338985,
      weather_rows: 70176,
      cities: 4,
      date_range: {
        start: '2022-06-01T00:00:00',
        end: '2026-10-20T12:00:00',
      },
    },
    processed: {
      gold_rows: 47208,
      cities: 4,
      date_range: {
        start: '2022-06-08T00:00:00',
        end: '2026-10-20T12:00:00',
      },
    },
  };
}

export const MODEL_METRICS = {
  model: 'Hybrid Ensemble — LightGBM + CatBoost (Variance-Weighted)',
  improvements: [
    'Hybrid ensemble (LightGBM + CatBoost averaged)',
    'Dropped weak features (sensor_count, is_weekend)',
    'Quantiles calibrated to [0.08, 0.92] (84% interval target)',
    'Season encoding bug fix (autumn vs fall)',
  ],
  model_params: {
    n_estimators: 500,
    learning_rate: 0.05,
    max_depth: 7,
    num_leaves: 31,
    quantiles: [0.08, 0.5, 0.92],
  },
  data: {
    train_samples: 37765,
    test_samples: 9443,
    n_features: 20,
  },
  accuracy: {
    mae: 2.78,
    rmse: 4.31,
    mape: 8.92,
    baseline_mae: 11.65,
    improvement_pct: 76.14,
  },
  uncertainty: {
    coverage_pct: 84.1,
    target_coverage_pct: 84.0,
    calibration_error: 0.1,
    mean_interval_width: 11.82,
  },
  fairness: {
    worst_city: 'Peshawar',
    by_city: [
      { city: 'Karachi', samples: 2292, mae: 1.48, rmse: 2.31, coverage_pct: 85.2 },
      { city: 'Islamabad', samples: 2383, mae: 2.42, rmse: 3.78, coverage_pct: 84.8 },
      { city: 'Lahore', samples: 2398, mae: 3.89, rmse: 5.92, coverage_pct: 83.1 },
      { city: 'Peshawar', samples: 2370, mae: 3.97, rmse: 6.21, coverage_pct: 82.9 },
    ],
  },
};

export const BASELINE_METRICS = {
  overall: {
    mae: 11.65,
    rmse: 17.74,
    mape: 34.74,
  },
  by_city: [
    { city: 'Karachi', mae: 4.54 },
    { city: 'Islamabad', mae: 10.15 },
    { city: 'Peshawar', mae: 15.65 },
    { city: 'Lahore', mae: 16.01 },
  ],
};

export const PIPELINE_STAGES = [
  {
    id: 1,
    title: 'Data Ingestion',
    description: 'Fetches hourly PM2.5 from OpenAQ v3 and weather from Open-Meteo for 4 cities with rate-limiting and retry logic.',
    stats: { records: '409K+', sources: 2, files: 8 },
    status: 'completed',
  },
  {
    id: 2,
    title: 'Data Cleaning',
    description: 'Timezone standardization, deduplication, outlier flagging (PM2.5 > 999), range validation on weather, and decision logging.',
    stats: { pm25_rows: '338,985', weather_rows: '70,176', issues: 0 },
    status: 'completed',
  },
  {
    id: 3,
    title: 'Feature Engineering',
    description: 'Aggregates PM2.5 to city-level hourly medians, merges weather, engineers 27 features (lags, rolling stats, temporal, weather).',
    stats: { features: 27, gold_rows: '47,208', null_rate: '0%' },
    status: 'completed',
  },
  {
    id: 4,
    title: 'Model Training',
    description: 'Hybrid LightGBM + CatBoost ensemble with 6 quantile models. 80/20 time-based split per city.',
    stats: { models: 6, improvement: '76.14%', coverage: '84.1%' },
    status: 'completed',
  },
  {
    id: 5,
    title: 'Forecasting Pipeline',
    description: 'Prefect-orchestrated hourly pipeline: fetch → clean → process → quality gates → 24h forecast for all 4 cities.',
    stats: { schedule: 'Hourly', predictions: 96, runtime: '5-7 min' },
    status: 'active',
  },
];

export const CORPUS_INFO = {
  total_chunks: 2614,
  sources: {
    'WHO Air Quality Guidelines': 36,
    'Pakistan EPA Smog Advisory': 100,
    'Lahore Air Quality Report 2024': 8,
    'Health Impacts of PM2.5': 125,
    'Health Under Haze Study': 209,
    'Unveiling Karachi Air (PAQI)': 405,
    'Unveiling Pakistan Air Pollution (PAQI)': 1731,
  },
  status: 'ready',
};

export function getMockAgentResponse(question) {
  const responses = {
    default: {
      answer: `Based on the data in our warehouse, the current PM2.5 levels across Pakistani cities vary significantly. Lahore typically records the highest levels (40-120 µg/m³), especially during winter months when smog conditions prevail. The WHO recommends annual mean PM2.5 should not exceed 5 µg/m³, and 24-hour mean should not exceed 15 µg/m³. Most Pakistani cities regularly exceed these guidelines.`,
      urdu_summary: `ہمارے ڈیٹا ویئر ہاؤس کے مطابق پاکستان کے بڑے شہروں میں پی ایم 2.5 کی سطح عالمی ادارہ صحت کی محفوظ حد (5 مائیکروگرام) سے کافی زیادہ ہے۔ لاہور میں موسم سرما میں سموگ کی وجہ سے فضائی آلودگی خطرناک حد تک بڑھ جاتی ہے۔ این 95 ماسک کا استعمال لازمی ہے۔`,
      citations: [
        { source: 'WHO Air Quality Guidelines', page: 12 },
        { source: 'Lahore Air Quality Report 2024', page: 5 },
      ],
      row_ids: [1024, 1025, 1026, 2048, 2049],
      data_points: 338985,
    },
  };

  return responses.default;
}
