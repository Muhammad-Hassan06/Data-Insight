"""
Module: build_processed
Location: src/process/build_processed.py
Purpose: Build the gold-layer feature table for modelling.

Steps:
  1. Load cleaned_pm25 and cleaned_weather from DuckDB
  2. Aggregate PM2.5 to one hourly value per (city, timestamp_utc)
     — median across all sensors for that hour
  3. Merge with weather on (city, timestamp_utc) — left join from PM2.5
  4. Engineer features:
       Lag features   : pm25_lag_1h, 24h, 48h, 168h (7 days)
       Rolling stats  : rolling_mean_24h, rolling_std_24h, rolling_mean_168h
       Temporal       : hour, day_of_week, month, is_weekend, season
       Weather        : all cleaned_weather columns
  5. Drop rows where any lag feature is NULL (cold-start period)
  6. Assign stable row_id
  7. Write gold_forecast_features table to data/processed/warehouse.duckdb
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT   = Path(__file__).parent.parent.parent
CLEANED_DB     = PROJECT_ROOT / "data" / "cleaned"  / "warehouse.duckdb"
PROCESSED_DIR  = PROJECT_ROOT / "data" / "processed"
PROCESSED_DB   = PROCESSED_DIR / "warehouse.duckdb"

CITIES = ["Lahore", "Karachi", "Islamabad", "Peshawar"]

# Lag windows in hours
LAGS = [1, 24, 48, 168]

# Rolling windows in hours
ROLLING_WINDOWS = [24, 168]


# ---------------------------------------------------------------------------
# Step 1 — Load cleaned tables
# ---------------------------------------------------------------------------

def load_cleaned() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read cleaned_pm25 and cleaned_weather from the cleaned warehouse."""
    con = duckdb.connect(str(CLEANED_DB), read_only=True)

    pm25 = con.execute("""
        SELECT
            city,
            timestamp_utc,
            pm25_ugm3,
            flagged
        FROM cleaned_pm25
        WHERE pm25_ugm3 IS NOT NULL
        ORDER BY city, timestamp_utc
    """).df()

    weather = con.execute("""
        SELECT
            city,
            timestamp_utc,
            temperature,
            humidity,
            dew_point,
            precipitation,
            pressure,
            cloud_cover,
            wind_speed,
            wind_direction
        FROM cleaned_weather
        ORDER BY city, timestamp_utc
    """).df()

    con.close()

    # Ensure tz-aware timestamps
    pm25["timestamp_utc"]    = pd.to_datetime(pm25["timestamp_utc"],    utc=True)
    weather["timestamp_utc"] = pd.to_datetime(weather["timestamp_utc"], utc=True)

    print(f"  [LOAD] cleaned_pm25    : {len(pm25):,} rows")
    print(f"  [LOAD] cleaned_weather : {len(weather):,} rows")
    return pm25, weather


# ---------------------------------------------------------------------------
# Step 2 — Aggregate PM2.5 to one value per (city, hour)
# ---------------------------------------------------------------------------

def aggregate_pm25(pm25: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse multiple sensors into a single hourly city-level value.

    Uses median to be robust to sensor outliers. Also records:
      - sensor_count   : how many sensors contributed
      - any_flagged    : True if any contributing reading was flagged
    """
    agg = (
        pm25.groupby(["city", "timestamp_utc"])
        .agg(
            pm25_ugm3    = ("pm25_ugm3",  "median"),
            sensor_count = ("pm25_ugm3",  "count"),
            any_flagged  = ("flagged",     "any"),
        )
        .reset_index()
    )
    print(f"  [AGG]  hourly city-level PM2.5 : {len(agg):,} rows")
    return agg


# ---------------------------------------------------------------------------
# Step 3 — Merge PM2.5 + weather
# ---------------------------------------------------------------------------

def merge_sources(pm25_agg: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Left-join PM2.5 (target) with weather features on (city, timestamp_utc)."""
    merged = pm25_agg.merge(weather, on=["city", "timestamp_utc"], how="left")
    weather_null_pct = merged["temperature"].isna().mean() * 100
    print(f"  [MERGE] {len(merged):,} rows | weather null rate: {weather_null_pct:.1f}%")
    return merged


# ---------------------------------------------------------------------------
# Step 4 — Feature engineering
# ---------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add lag, rolling and temporal features.
    All features are computed per-city to prevent cross-city leakage.
    """
    df = df.sort_values(["city", "timestamp_utc"]).copy()
    result_parts = []

    for city, grp in df.groupby("city"):
        grp = grp.set_index("timestamp_utc").sort_index()
        pm25 = grp["pm25_ugm3"]

        # ---- Lag features --------------------------------------------------
        for lag in LAGS:
            grp[f"pm25_lag_{lag}h"] = pm25.shift(lag)

        # ---- Rolling statistics --------------------------------------------
        for window in ROLLING_WINDOWS:
            # min_periods=window//2 so we don't drop too many rows at series start
            grp[f"pm25_rolling_mean_{window}h"] = (
                pm25.shift(1)                        # shift 1 to avoid leakage
                    .rolling(window, min_periods=window // 2)
                    .mean()
            )
            grp[f"pm25_rolling_std_{window}h"] = (
                pm25.shift(1)
                    .rolling(window, min_periods=window // 2)
                    .std()
            )

        # ---- Temporal features ---------------------------------------------
        idx = grp.index  # DatetimeTZDtype index
        grp["hour"]        = idx.hour
        grp["day_of_week"] = idx.dayofweek          # 0=Monday … 6=Sunday
        grp["month"]       = idx.month
        grp["is_weekend"]  = (idx.dayofweek >= 5).astype(int)

        # Season (Pakistan / Northern Hemisphere)
        # Winter: Dec-Feb, Spring: Mar-May, Summer: Jun-Aug, Autumn: Sep-Nov
        season_map = {
            12: "winter", 1: "winter",  2: "winter",
             3: "spring", 4: "spring",  5: "spring",
             6: "summer", 7: "summer",  8: "summer",
             9: "autumn", 10: "autumn", 11: "autumn",
        }
        grp["season"] = grp["month"].map(season_map)

        grp = grp.reset_index()
        result_parts.append(grp)

    out = pd.concat(result_parts, ignore_index=True)
    print(f"  [FEAT] Features engineered : {len(out):,} rows, {len(out.columns)} cols")
    return out


# ---------------------------------------------------------------------------
# Step 5 — Drop cold-start rows (any core lag is NULL)
# ---------------------------------------------------------------------------

def drop_cold_start(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop rows where the longest-horizon lag (168h) is NULL.
    These are the first 7 days of each city's series where lag features
    cannot be computed — unusable for training or evaluation.
    """
    before = len(df)
    df = df.dropna(subset=["pm25_lag_168h"]).reset_index(drop=True)
    dropped = before - len(df)
    print(f"  [COLD] Dropped {dropped:,} cold-start rows (lag_168h is NULL)")
    return df


# ---------------------------------------------------------------------------
# Step 6 — Assign stable row_id
# ---------------------------------------------------------------------------

def assign_row_ids(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign a stable integer row_id sorted by (city, timestamp_utc).
    row_id is 1-indexed and used for traceable citations in the RAG agent.
    """
    df = df.sort_values(["city", "timestamp_utc"]).reset_index(drop=True)
    df.insert(0, "row_id", df.index + 1)
    return df


# ---------------------------------------------------------------------------
# Step 7 — Write to processed DuckDB
# ---------------------------------------------------------------------------

def write_gold_table(df: pd.DataFrame) -> None:
    """Persist the gold feature table to data/processed/warehouse.duckdb."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(PROCESSED_DB))
    con.execute("DROP TABLE IF EXISTS gold_forecast_features")

    # Register the DataFrame and create table from it
    con.register("gold_df", df)
    con.execute("CREATE TABLE gold_forecast_features AS SELECT * FROM gold_df")

    # Verify
    count = con.execute("SELECT COUNT(*) FROM gold_forecast_features").fetchone()[0]
    cities = con.execute(
        "SELECT city, COUNT(*) as n FROM gold_forecast_features GROUP BY city ORDER BY city"
    ).fetchall()

    con.close()

    print(f"\n  [GOLD] gold_forecast_features : {count:,} total rows")
    for city, n in cities:
        print(f"         {city:<12} : {n:,} rows")
    print(f"  [DB]   Saved → {PROCESSED_DB}")


# ---------------------------------------------------------------------------
# Summary print
# ---------------------------------------------------------------------------

def print_schema_summary(df: pd.DataFrame) -> None:
    """Print column groups so it's easy to verify feature coverage."""
    lag_cols     = [c for c in df.columns if "lag"     in c]
    rolling_cols = [c for c in df.columns if "rolling" in c]
    temporal_cols = ["hour", "day_of_week", "month", "is_weekend", "season"]
    weather_cols = ["temperature", "humidity", "dew_point", "precipitation",
                    "pressure", "cloud_cover", "wind_speed", "wind_direction"]

    print("\n  Feature groups in gold table:")
    print(f"    Lag features     ({len(lag_cols)}) : {lag_cols}")
    print(f"    Rolling features ({len(rolling_cols)}) : {rolling_cols}")
    print(f"    Temporal         ({len(temporal_cols)}) : {temporal_cols}")
    print(f"    Weather          ({len(weather_cols)}) : {weather_cols}")
    print(f"    Target column    : pm25_ugm3")
    print(f"    Total columns    : {len(df.columns)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 72)
    print("PHASE 2A  —  PROCESSED / GOLD LAYER")
    print("=" * 72)

    # 1. Load
    print("\n[1/6] Loading cleaned tables...")
    pm25, weather = load_cleaned()

    # 2. Aggregate PM2.5
    print("\n[2/6] Aggregating PM2.5 to hourly city-level medians...")
    pm25_agg = aggregate_pm25(pm25)

    # 3. Merge
    print("\n[3/6] Merging PM2.5 + weather...")
    merged = merge_sources(pm25_agg, weather)

    # 4. Feature engineering
    print("\n[4/6] Engineering features...")
    featured = engineer_features(merged)

    # 5. Drop cold-start
    print("\n[5/6] Removing cold-start rows...")
    featured = drop_cold_start(featured)

    # 6. Row IDs + write
    print("\n[6/6] Assigning row IDs and writing gold table...")
    featured = assign_row_ids(featured)
    print_schema_summary(featured)
    write_gold_table(featured)

    print("\n" + "=" * 72)
    print("[OK] Gold layer complete.")
    print(f"     Processed DB : {PROCESSED_DB}")
    print("=" * 72)


if __name__ == "__main__":
    main()
