"""
Initialize DuckDB warehouse layers (cleaned and processed) for local development and live dashboard.
Creates:
  - data/cleaned/warehouse.duckdb (tables: cleaned_pm25, cleaned_weather)
  - data/processed/warehouse.duckdb (table: gold_forecast_features)
"""
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLEANED_DIR = PROJECT_ROOT / "data" / "cleaned"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

CLEANED_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

CLEANED_DB = CLEANED_DIR / "warehouse.duckdb"
PROCESSED_DB = PROCESSED_DIR / "warehouse.duckdb"

CITIES = {
    "Lahore": {"lat": 31.5497, "lon": 74.3436, "base_pm25": 68.0},
    "Karachi": {"lat": 24.8607, "lon": 67.0011, "base_pm25": 28.0},
    "Islamabad": {"lat": 33.6844, "lon": 73.0479, "base_pm25": 42.0},
    "Peshawar": {"lat": 34.0151, "lon": 71.5249, "base_pm25": 58.0},
}

def init_warehouses():
    print("[1/3] Initializing DuckDB warehouse layers...")
    
    # 1. Cleaned Database
    con_clean = duckdb.connect(str(CLEANED_DB))
    
    con_clean.execute("""
        CREATE TABLE IF NOT EXISTS cleaned_pm25 (
            city VARCHAR,
            location_id BIGINT,
            sensor_id BIGINT,
            timestamp_utc TIMESTAMP,
            value DOUBLE,
            unit VARCHAR,
            flagged BOOLEAN,
            flag_reason VARCHAR
        )
    """)
    
    con_clean.execute("""
        CREATE TABLE IF NOT EXISTS cleaned_weather (
            city VARCHAR,
            timestamp_utc TIMESTAMP,
            temperature DOUBLE,
            humidity DOUBLE,
            dew_point DOUBLE,
            precipitation DOUBLE,
            pressure DOUBLE,
            cloud_cover DOUBLE,
            wind_speed DOUBLE,
            wind_direction DOUBLE,
            flagged BOOLEAN,
            flag_reason VARCHAR
        )
    """)
    
    # Check if empty, populate with hourly series for last 96 hours
    existing_pm25 = con_clean.execute("SELECT COUNT(*) FROM cleaned_pm25").fetchone()[0]
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    timestamps = [now - timedelta(hours=i) for i in range(168, -1, -1)]
    
    if existing_pm25 == 0:
        print("  Populating cleaned_pm25 and cleaned_weather...")
        pm25_rows = []
        weather_rows = []
        
        for city, meta in CITIES.items():
            base = meta["base_pm25"]
            for i, ts in enumerate(timestamps):
                # Realistic diurnal cycle
                hour = ts.hour
                cycle = 15.0 * np.sin((hour - 6) * np.pi / 12)
                val = max(5.0, base + cycle + np.random.normal(0, 3.0))
                
                pm25_rows.append({
                    "city": city,
                    "location_id": 4515157,
                    "sensor_id": 88210,
                    "timestamp_utc": ts,
                    "value": round(val, 2),
                    "unit": "µg/m³",
                    "flagged": False,
                    "flag_reason": None,
                })
                
                weather_rows.append({
                    "city": city,
                    "timestamp_utc": ts,
                    "temperature": round(24.0 + 6.0 * np.sin((hour - 8) * np.pi / 12), 1),
                    "humidity": round(55.0 - 15.0 * np.sin((hour - 8) * np.pi / 12), 1),
                    "dew_point": 14.5,
                    "precipitation": 0.0,
                    "pressure": 1012.0,
                    "cloud_cover": 20.0,
                    "wind_speed": round(3.5 + np.random.uniform(0, 2), 1),
                    "wind_direction": 180.0,
                    "flagged": False,
                    "flag_reason": None,
                })
                
        df_pm25 = pd.DataFrame(pm25_rows)
        df_weather = pd.DataFrame(weather_rows)
        
        con_clean.register("df_pm25", df_pm25)
        con_clean.execute("INSERT INTO cleaned_pm25 SELECT * FROM df_pm25")
        
        con_clean.register("df_weather", df_weather)
        con_clean.execute("INSERT INTO cleaned_weather SELECT * FROM df_weather")
        
    con_clean.close()
    print("  [OK] Cleaned warehouse ready.")

    # 2. Processed Database
    con_proc = duckdb.connect(str(PROCESSED_DB))
    
    con_proc.execute("""
        CREATE TABLE IF NOT EXISTS gold_forecast_features (
            row_id BIGINT,
            city VARCHAR,
            timestamp_utc TIMESTAMP,
            pm25_ugm3 DOUBLE,
            sensor_count INTEGER,
            any_flagged BOOLEAN,
            temperature DOUBLE,
            humidity DOUBLE,
            dew_point DOUBLE,
            precipitation DOUBLE,
            pressure DOUBLE,
            cloud_cover DOUBLE,
            wind_speed DOUBLE,
            wind_direction DOUBLE,
            pm25_lag_1h DOUBLE,
            pm25_lag_24h DOUBLE,
            pm25_lag_48h DOUBLE,
            pm25_lag_168h DOUBLE,
            pm25_rolling_mean_24h DOUBLE,
            pm25_rolling_std_24h DOUBLE,
            pm25_rolling_mean_168h DOUBLE,
            pm25_rolling_std_168h DOUBLE,
            hour INTEGER,
            day_of_week INTEGER,
            month INTEGER,
            is_weekend INTEGER,
            season VARCHAR
        )
    """)
    
    existing_gold = con_proc.execute("SELECT COUNT(*) FROM gold_forecast_features").fetchone()[0]
    if existing_gold == 0:
        print("  Populating gold_forecast_features...")
        gold_rows = []
        row_id = 1
        
        # Connect to cleaned to engineer features
        con_c = duckdb.connect(str(CLEANED_DB), read_only=True)
        raw_pm25 = con_c.execute("SELECT city, timestamp_utc, value as pm25_ugm3 FROM cleaned_pm25 ORDER BY city, timestamp_utc").df()
        raw_weather = con_c.execute("SELECT * FROM cleaned_weather ORDER BY city, timestamp_utc").df()
        con_c.close()
        
        for city in CITIES.keys():
            c_pm25 = raw_pm25[raw_pm25["city"] == city].sort_values("timestamp_utc").set_index("timestamp_utc")
            c_weather = raw_weather[raw_weather["city"] == city].sort_values("timestamp_utc").set_index("timestamp_utc")
            
            s = c_pm25["pm25_ugm3"]
            lag_1h = s.shift(1)
            lag_24h = s.shift(24)
            lag_48h = s.shift(48)
            lag_168h = s.shift(168)
            roll_mean_24h = s.shift(1).rolling(24, min_periods=12).mean()
            roll_std_24h = s.shift(1).rolling(24, min_periods=12).std().fillna(1.0)
            roll_mean_168h = s.shift(1).rolling(168, min_periods=24).mean()
            roll_std_168h = s.shift(1).rolling(168, min_periods=24).std().fillna(2.0)
            
            for ts in s.index[24:]:  # Skip initial cold start
                w_row = c_weather.loc[ts] if ts in c_weather.index else None
                h = ts.hour
                dow = ts.weekday()
                mo = ts.month
                
                gold_rows.append({
                    "row_id": row_id,
                    "city": city,
                    "timestamp_utc": ts,
                    "pm25_ugm3": float(s.loc[ts]),
                    "sensor_count": 1,
                    "any_flagged": False,
                    "temperature": float(w_row["temperature"]) if w_row is not None else 25.0,
                    "humidity": float(w_row["humidity"]) if w_row is not None else 50.0,
                    "dew_point": float(w_row["dew_point"]) if w_row is not None else 14.0,
                    "precipitation": float(w_row["precipitation"]) if w_row is not None else 0.0,
                    "pressure": float(w_row["pressure"]) if w_row is not None else 1012.0,
                    "cloud_cover": float(w_row["cloud_cover"]) if w_row is not None else 20.0,
                    "wind_speed": float(w_row["wind_speed"]) if w_row is not None else 3.5,
                    "wind_direction": float(w_row["wind_direction"]) if w_row is not None else 180.0,
                    "pm25_lag_1h": float(lag_1h.loc[ts]) if not pd.isna(lag_1h.loc[ts]) else float(s.loc[ts]),
                    "pm25_lag_24h": float(lag_24h.loc[ts]) if not pd.isna(lag_24h.loc[ts]) else float(s.loc[ts]),
                    "pm25_lag_48h": float(lag_48h.loc[ts]) if not pd.isna(lag_48h.loc[ts]) else float(s.loc[ts]),
                    "pm25_lag_168h": float(lag_168h.loc[ts]) if not pd.isna(lag_168h.loc[ts]) else float(s.loc[ts]),
                    "pm25_rolling_mean_24h": float(roll_mean_24h.loc[ts]) if not pd.isna(roll_mean_24h.loc[ts]) else float(s.loc[ts]),
                    "pm25_rolling_std_24h": float(roll_std_24h.loc[ts]) if not pd.isna(roll_std_24h.loc[ts]) else 2.0,
                    "pm25_rolling_mean_168h": float(roll_mean_168h.loc[ts]) if not pd.isna(roll_mean_168h.loc[ts]) else float(s.loc[ts]),
                    "pm25_rolling_std_168h": float(roll_std_168h.loc[ts]) if not pd.isna(roll_std_168h.loc[ts]) else 3.0,
                    "hour": h,
                    "day_of_week": dow,
                    "month": mo,
                    "is_weekend": 1 if dow >= 5 else 0,
                    "season": "autumn" if mo in [9, 10, 11] else "winter",
                })
                row_id += 1
                
        df_gold = pd.DataFrame(gold_rows)
        con_proc.register("df_gold", df_gold)
        con_proc.execute("INSERT INTO gold_forecast_features SELECT * FROM df_gold")
        
    con_proc.close()
    print(f"  [OK] Processed gold warehouse ready ({row_id - 1} rows).")
    print("[SUCCESS] DuckDB databases initialized at:")
    print(f"  - {CLEANED_DB}")
    print(f"  - {PROCESSED_DB}")

if __name__ == "__main__":
    init_warehouses()
