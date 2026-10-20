"""
Module: build_cleaned
Location: src/clean/build_cleaned.py
Purpose: Transform raw Parquet files into a cleaned DuckDB warehouse layer.

Cleaning rules applied:
  - All timestamps converted to UTC, floored to the hour
  - Duplicate (city, location_id, timestamp_utc) rows: keep first occurrence
  - PM2.5 values < 0: fix to NULL (physically impossible)
  - PM2.5 values > 999 µg/m³: flag as suspicious (keep value, mark flagged=True)
  - Weather values: validate expected ranges, flag outliers
  - Missing values: kept as NULL — never silently imputed here
  - All changes recorded in a change log appended to data/cleaned/clean_log.jsonl
"""

import json
import datetime
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent
RAW_DIR      = PROJECT_ROOT / "data" / "raw"
CLEANED_DIR  = PROJECT_ROOT / "data" / "cleaned"
DB_PATH      = CLEANED_DIR / "warehouse.duckdb"
LOG_PATH     = CLEANED_DIR / "clean_log.jsonl"

CITIES = ["lahore", "karachi", "islamabad", "peshawar"]

# Outlier thresholds
PM25_MAX_VALID   = 999.0   # µg/m³ — above this is flagged suspicious
PM25_MIN_VALID   =   0.0   # µg/m³ — below this is physically impossible → NULL

TEMP_RANGE    = (-20.0, 55.0)   # °C  — Pakistan range
HUMIDITY_RANGE = (0.0, 100.0)   # %
WIND_RANGE     = (0.0, 60.0)    # m/s
PRESSURE_RANGE = (850.0, 1100.0) # hPa


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------

def _log(entries: list[dict]) -> None:
    """Append decision entries to the JSONL clean log."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        for entry in entries:
            entry["logged_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            fh.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# PM2.5 cleaning
# ---------------------------------------------------------------------------

def clean_pm25(city: str) -> pd.DataFrame:
    """
    Load, clean and return the PM2.5 DataFrame for one city.

    Returns an empty DataFrame if the raw file is missing.
    """
    raw_file = RAW_DIR / f"openaq_pm25_{city}.parquet"
    if not raw_file.exists():
        print(f"  [SKIP] {raw_file.name} not found")
        return pd.DataFrame()

    df = pd.read_parquet(raw_file)
    log_entries = []
    original_len = len(df)

    # ---- 1. Timestamp normalisation ----------------------------------------
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    # Floor to the hour so PM2.5 and weather align
    df["timestamp_utc"] = df["timestamp_utc"].dt.floor("h")

    # ---- 2. Deduplicate (city, location_id, sensor_id, timestamp_utc) ------
    before = len(df)
    df = df.drop_duplicates(
        subset=["city", "location_id", "sensor_id", "timestamp_utc"],
        keep="first"
    )
    dupes_removed = before - len(df)
    if dupes_removed:
        log_entries.append({
            "city": city, "layer": "pm25",
            "rule": "deduplicate",
            "action": "fix",
            "rows_affected": dupes_removed,
            "explanation": f"Removed {dupes_removed} duplicate (city, location_id, sensor_id, timestamp_utc) rows; kept first occurrence."
        })

    # ---- 3. Add flagged column ---------------------------------------------
    df["flagged"] = False
    df["flag_reason"] = None

    # ---- 4. Negative values → NULL (physically impossible) -----------------
    neg_mask = df["value"] < PM25_MIN_VALID
    neg_count = neg_mask.sum()
    if neg_count:
        df.loc[neg_mask, "value"] = np.nan
        df.loc[neg_mask, "flagged"] = True
        df.loc[neg_mask, "flag_reason"] = "negative_value_set_null"
        log_entries.append({
            "city": city, "layer": "pm25",
            "rule": "range_check_negative",
            "action": "fix",
            "rows_affected": int(neg_count),
            "explanation": f"Set {neg_count} negative PM2.5 values to NULL (physically impossible)."
        })

    # ---- 5. Extreme values → flagged (keep, mark suspicious) ---------------
    high_mask = df["value"] > PM25_MAX_VALID
    high_count = high_mask.sum()
    if high_count:
        df.loc[high_mask, "flagged"] = True
        df.loc[high_mask, "flag_reason"] = "extreme_value_gt_999"
        log_entries.append({
            "city": city, "layer": "pm25",
            "rule": "range_check_high",
            "action": "flag",
            "rows_affected": int(high_count),
            "explanation": f"Flagged {high_count} PM2.5 values > {PM25_MAX_VALID} µg/m³ as suspicious; values retained."
        })

    # ---- 6. Rename value column for clarity --------------------------------
    df = df.rename(columns={"value": "pm25_ugm3"})

    # ---- 7. Select and order final columns ---------------------------------
    df = df[[
        "city", "location_id", "sensor_id", "timestamp_utc",
        "pm25_ugm3", "unit", "coordinates_lat", "coordinates_lon",
        "flagged", "flag_reason"
    ]]

    _log(log_entries)
    print(f"  [PM25] {city}: {original_len:,} raw → {len(df):,} cleaned "
          f"(dupes={dupes_removed}, neg={neg_count}, high_flag={high_count})")
    return df


# ---------------------------------------------------------------------------
# Weather cleaning
# ---------------------------------------------------------------------------

def clean_weather(city: str) -> pd.DataFrame:
    """Load, clean and return the weather DataFrame for one city."""
    raw_file = RAW_DIR / f"weather_{city}.parquet"
    if not raw_file.exists():
        print(f"  [SKIP] {raw_file.name} not found")
        return pd.DataFrame()

    df = pd.read_parquet(raw_file)
    log_entries = []

    # ---- 1. Timestamp normalisation ----------------------------------------
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["timestamp_utc"] = df["timestamp_utc"].dt.floor("h")

    # ---- 2. Deduplicate -----------------------------------------------------
    before = len(df)
    df = df.drop_duplicates(subset=["city", "timestamp_utc"], keep="first")
    dupes_removed = before - len(df)
    if dupes_removed:
        log_entries.append({
            "city": city, "layer": "weather",
            "rule": "deduplicate",
            "action": "fix",
            "rows_affected": dupes_removed,
            "explanation": f"Removed {dupes_removed} duplicate (city, timestamp_utc) weather rows."
        })

    # ---- 3. Range checks for each weather column ----------------------------
    df["flagged"] = False
    df["flag_reason"] = None

    checks = {
        "temperature":  TEMP_RANGE,
        "humidity":     HUMIDITY_RANGE,
        "wind_speed":   WIND_RANGE,
        "pressure":     PRESSURE_RANGE,
    }

    for col, (lo, hi) in checks.items():
        if col not in df.columns:
            continue
        mask = (df[col] < lo) | (df[col] > hi)
        count = mask.sum()
        if count:
            df.loc[mask, "flagged"] = True
            df.loc[mask, "flag_reason"] = f"{col}_out_of_range"
            log_entries.append({
                "city": city, "layer": "weather",
                "rule": f"range_check_{col}",
                "action": "flag",
                "rows_affected": int(count),
                "explanation": f"Flagged {count} rows where {col} outside [{lo}, {hi}]."
            })

    _log(log_entries)
    print(f"  [WTHR] {city}: {len(df):,} rows cleaned")
    return df


# ---------------------------------------------------------------------------
# DuckDB writer
# ---------------------------------------------------------------------------

def write_to_duckdb(
    pm25_frames: dict[str, pd.DataFrame],
    weather_frames: dict[str, pd.DataFrame],
) -> None:
    """Write all cleaned frames into DuckDB warehouse as cleaned_pm25 and cleaned_weather."""
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    # Combine all cities
    pm25_all = pd.concat(
        [df for df in pm25_frames.values() if not df.empty],
        ignore_index=True
    )
    weather_all = pd.concat(
        [df for df in weather_frames.values() if not df.empty],
        ignore_index=True
    )

    con = duckdb.connect(str(DB_PATH))

    # Drop and recreate tables for idempotent runs
    con.execute("DROP TABLE IF EXISTS cleaned_pm25")
    con.execute("DROP TABLE IF EXISTS cleaned_weather")

    con.execute("""
        CREATE TABLE cleaned_pm25 (
            city            VARCHAR,
            location_id     BIGINT,
            sensor_id       BIGINT,
            timestamp_utc   TIMESTAMPTZ,
            pm25_ugm3       DOUBLE,
            unit            VARCHAR,
            coordinates_lat DOUBLE,
            coordinates_lon DOUBLE,
            flagged         BOOLEAN,
            flag_reason     VARCHAR
        )
    """)

    con.execute("""
        CREATE TABLE cleaned_weather (
            timestamp_utc   TIMESTAMPTZ,
            city            VARCHAR,
            temperature     DOUBLE,
            humidity        DOUBLE,
            dew_point       DOUBLE,
            precipitation   DOUBLE,
            pressure        DOUBLE,
            cloud_cover     DOUBLE,
            wind_speed      DOUBLE,
            wind_direction  DOUBLE,
            latitude        DOUBLE,
            longitude       DOUBLE,
            flagged         BOOLEAN,
            flag_reason     VARCHAR
        )
    """)

    con.execute("INSERT INTO cleaned_pm25 SELECT * FROM pm25_all")
    con.execute("INSERT INTO cleaned_weather SELECT * FROM weather_all")

    # Summary stats
    pm25_count   = con.execute("SELECT COUNT(*) FROM cleaned_pm25").fetchone()[0]
    weather_count = con.execute("SELECT COUNT(*) FROM cleaned_weather").fetchone()[0]
    flagged_pm25  = con.execute("SELECT COUNT(*) FROM cleaned_pm25 WHERE flagged = TRUE").fetchone()[0]

    con.close()

    print(f"\n  [DB] cleaned_pm25    : {pm25_count:,} rows ({flagged_pm25:,} flagged)")
    print(f"  [DB] cleaned_weather : {weather_count:,} rows")
    print(f"  [DB] Saved → {DB_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 72)
    print("PHASE 1C / 2A  —  CLEANING LAYER")
    print("=" * 72)

    pm25_frames: dict[str, pd.DataFrame] = {}
    weather_frames: dict[str, pd.DataFrame] = {}

    print("\n[PM2.5]")
    for city in CITIES:
        pm25_frames[city] = clean_pm25(city)

    print("\n[WEATHER]")
    for city in CITIES:
        weather_frames[city] = clean_weather(city)

    print("\n[WRITING TO DUCKDB]")
    write_to_duckdb(pm25_frames, weather_frames)

    print("\n" + "=" * 72)
    print("[OK] Cleaning complete.")
    print(f"     Warehouse : {DB_PATH}")
    print(f"     Clean log : {LOG_PATH}")
    print("=" * 72)


if __name__ == "__main__":
    main()
