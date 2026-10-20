"""
Module: validator
Location: src/dq_agent/validator.py
Purpose: Pandera schemas and issue-detection functions for the DQ Agent.

Each check returns a list of ValidationIssue dataclasses describing
exactly what was found — no fixes are applied here. The decision_engine
decides what to do with each issue.
"""

from __future__ import annotations

import duckdb
import pandas as pd
import pandera as pa
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent
CLEANED_DB   = PROJECT_ROOT / "data" / "cleaned" / "warehouse.duckdb"
PROCESSED_DB = PROJECT_ROOT / "data" / "processed" / "warehouse.duckdb"

CITIES = ["Lahore", "Karachi", "Islamabad", "Peshawar"]

# Thresholds
PM25_MAX_SUSPICIOUS  = 999.0   # µg/m³
PM25_MIN_VALID       = 0.0
GAP_FILL_THRESHOLD_H = 2       # gaps ≤ this many hours → eligible for fill
GAP_FLAG_THRESHOLD_H = 24      # gaps > this → flag as long outage
STALENESS_HOURS      = 48      # source not updated in 48h → stale flag


# ---------------------------------------------------------------------------
# ValidationIssue
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """Represents one data quality finding."""
    check_name:    str           # machine-readable rule name
    layer:         str           # "cleaned_pm25" | "cleaned_weather" | "gold"
    city:          str           # affected city, or "all"
    severity:      str           # "error" | "warning" | "info"
    rows_affected: int
    description:   str           # human-readable summary
    details:       dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pandera schemas
# ---------------------------------------------------------------------------

PM25_SCHEMA = pa.DataFrameSchema(
    columns={
        "city": pa.Column(str, pa.Check.isin(CITIES)),
        "timestamp_utc": pa.Column("datetime64[us, UTC]"),
        "pm25_ugm3": pa.Column(
            float,
            checks=[
                pa.Check.ge(PM25_MIN_VALID, error="pm25_below_zero"),
                pa.Check.le(PM25_MAX_SUSPICIOUS, error="pm25_above_999"),
            ],
            nullable=True,
        ),
        "flagged": pa.Column(bool),
    },
    coerce=True,
)

WEATHER_SCHEMA = pa.DataFrameSchema(
    columns={
        "city":        pa.Column(str,   pa.Check.isin(CITIES)),
        "timestamp_utc": pa.Column("datetime64[us, UTC]"),
        "temperature": pa.Column(float, pa.Check.in_range(-20, 55),  nullable=True),
        "humidity":    pa.Column(float, pa.Check.in_range(0,  100),  nullable=True),
        "wind_speed":  pa.Column(float, pa.Check.in_range(0,  60),   nullable=True),
        "pressure":    pa.Column(float, pa.Check.in_range(850, 1100), nullable=True),
    },
    coerce=True,
)

GOLD_SCHEMA = pa.DataFrameSchema(
    columns={
        "row_id":       pa.Column(int,   pa.Check.ge(1)),
        "city":         pa.Column(str,   pa.Check.isin(CITIES)),
        "timestamp_utc": pa.Column("datetime64[us, UTC]"),
        "pm25_ugm3":    pa.Column(float, pa.Check.ge(0), nullable=True),
        "pm25_lag_1h":  pa.Column(float, nullable=True),
        "pm25_lag_24h": pa.Column(float, nullable=True),
        "pm25_lag_168h": pa.Column(float, nullable=True),
        "hour":         pa.Column(int,   pa.Check.in_range(0, 23)),
        "month":        pa.Column(int,   pa.Check.in_range(1, 12)),
        "is_weekend":   pa.Column(int,   pa.Check.isin([0, 1])),
    },
    coerce=True,
)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_cleaned_pm25() -> pd.DataFrame:
    con = duckdb.connect(str(CLEANED_DB), read_only=True)
    df = con.execute("SELECT * FROM cleaned_pm25").df()
    con.close()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df


def _load_cleaned_weather() -> pd.DataFrame:
    con = duckdb.connect(str(CLEANED_DB), read_only=True)
    df = con.execute("SELECT * FROM cleaned_weather").df()
    con.close()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df


def _load_gold() -> pd.DataFrame:
    con = duckdb.connect(str(PROCESSED_DB), read_only=True)
    df = con.execute("SELECT * FROM gold_forecast_features").df()
    con.close()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------

def check_schema_pm25(df: pd.DataFrame) -> list[ValidationIssue]:
    """Validate PM2.5 DataFrame against pandera schema."""
    issues = []
    try:
        PM25_SCHEMA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        for _, row in exc.failure_cases.iterrows():
            issues.append(ValidationIssue(
                check_name="schema_pm25",
                layer="cleaned_pm25",
                city="all",
                severity="error",
                rows_affected=1,
                description=f"Schema violation: {row.get('check', '')} on column '{row.get('column', '')}'",
                details={"failure_case": str(row.get("failure_case", ""))},
            ))
    return issues


def check_schema_weather(df: pd.DataFrame) -> list[ValidationIssue]:
    """Validate weather DataFrame against pandera schema."""
    issues = []
    try:
        WEATHER_SCHEMA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        for _, row in exc.failure_cases.iterrows():
            issues.append(ValidationIssue(
                check_name="schema_weather",
                layer="cleaned_weather",
                city="all",
                severity="error",
                rows_affected=1,
                description=f"Schema violation: {row.get('check', '')} on column '{row.get('column', '')}'",
                details={"failure_case": str(row.get("failure_case", ""))},
            ))
    return issues


def check_schema_gold(df: pd.DataFrame) -> list[ValidationIssue]:
    """Validate gold table against pandera schema."""
    issues = []
    try:
        GOLD_SCHEMA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        for _, row in exc.failure_cases.iterrows():
            issues.append(ValidationIssue(
                check_name="schema_gold",
                layer="gold",
                city="all",
                severity="error",
                rows_affected=1,
                description=f"Schema violation: {row.get('check', '')} on column '{row.get('column', '')}'",
                details={"failure_case": str(row.get("failure_case", ""))},
            ))
    return issues


def check_duplicates(df: pd.DataFrame, layer: str, key_cols: list[str]) -> list[ValidationIssue]:
    """Detect duplicate rows on key columns."""
    issues = []
    dupes = df.duplicated(subset=key_cols, keep=False)
    count = dupes.sum()
    if count:
        issues.append(ValidationIssue(
            check_name="duplicate_rows",
            layer=layer,
            city="all",
            severity="error",
            rows_affected=int(count),
            description=f"Found {count} duplicate rows on {key_cols} in {layer}.",
            details={"key_cols": key_cols},
        ))
    return issues


def check_temporal_gaps(df: pd.DataFrame, city: str) -> list[ValidationIssue]:
    """
    Detect gaps in the hourly PM2.5 series for one city.

    Returns separate issues for:
      - short gaps (1–GAP_FILL_THRESHOLD_H hours) → eligible for fill
      - long gaps  (> GAP_FLAG_THRESHOLD_H hours) → flag
    """
    issues = []

    city_df = (
        df[df["city"] == city]
        .drop_duplicates(subset=["timestamp_utc"])
        .set_index("timestamp_utc")
        .sort_index()
    )

    if city_df.empty:
        return issues

    # Resample to hourly, count missing slots
    full_range = pd.date_range(
        start=city_df.index.min(),
        end=city_df.index.max(),
        freq="h",
        tz="UTC",
    )
    missing_hours = full_range.difference(city_df.index)

    if missing_hours.empty:
        return issues

    # Group consecutive missing hours into gap runs
    gaps: list[tuple[pd.Timestamp, int]] = []
    if len(missing_hours):
        gap_start = missing_hours[0]
        run_len   = 1
        for i in range(1, len(missing_hours)):
            diff = (missing_hours[i] - missing_hours[i - 1]).total_seconds() / 3600
            if diff == 1:
                run_len += 1
            else:
                gaps.append((gap_start, run_len))
                gap_start = missing_hours[i]
                run_len   = 1
        gaps.append((gap_start, run_len))

    short_gaps = [(s, l) for s, l in gaps if 1 <= l <= GAP_FILL_THRESHOLD_H]
    long_gaps  = [(s, l) for s, l in gaps if l > GAP_FLAG_THRESHOLD_H]

    if short_gaps:
        total_short = sum(l for _, l in short_gaps)
        issues.append(ValidationIssue(
            check_name="temporal_gap_short",
            layer="cleaned_pm25",
            city=city,
            severity="warning",
            rows_affected=total_short,
            description=(
                f"{city}: {len(short_gaps)} short gap(s) totalling {total_short} missing hour(s). "
                f"Eligible for linear interpolation (≤{GAP_FILL_THRESHOLD_H}h each)."
            ),
            details={"gap_count": len(short_gaps), "total_missing_hours": total_short,
                     "gaps": [(str(s), l) for s, l in short_gaps[:5]]},
        ))

    if long_gaps:
        total_long = sum(l for _, l in long_gaps)
        issues.append(ValidationIssue(
            check_name="temporal_gap_long",
            layer="cleaned_pm25",
            city=city,
            severity="warning",
            rows_affected=total_long,
            description=(
                f"{city}: {len(long_gaps)} long gap(s) totalling {total_long} missing hour(s). "
                f"Too uncertain to interpolate (>{GAP_FLAG_THRESHOLD_H}h). Will be flagged."
            ),
            details={"gap_count": len(long_gaps), "total_missing_hours": total_long,
                     "longest_gap_hours": max(l for _, l in long_gaps),
                     "gaps": [(str(s), l) for s, l in long_gaps[:5]]},
        ))

    return issues


def check_staleness(df: pd.DataFrame, city: str) -> list[ValidationIssue]:
    """Flag if latest data for a city is older than STALENESS_HOURS."""
    issues = []
    city_df = df[df["city"] == city]
    if city_df.empty:
        return issues

    latest = city_df["timestamp_utc"].max()
    now    = pd.Timestamp.now(tz="UTC")
    age_h  = (now - latest).total_seconds() / 3600

    if age_h > STALENESS_HOURS:
        issues.append(ValidationIssue(
            check_name="data_staleness",
            layer="cleaned_pm25",
            city=city,
            severity="warning",
            rows_affected=0,
            description=(
                f"{city}: latest PM2.5 reading is {age_h:.1f}h old "
                f"(threshold: {STALENESS_HOURS}h). Source may have stopped updating."
            ),
            details={"latest_timestamp": str(latest), "age_hours": round(age_h, 1)},
        ))
    return issues


def check_pm25_distribution(df: pd.DataFrame, city: str) -> list[ValidationIssue]:
    """
    Detect distribution anomalies per city:
      - Suspiciously high values (> 500 µg/m³)
      - Zero-runs (≥ 6 consecutive zero readings — likely sensor offline)
    """
    issues = []
    city_df = df[df["city"] == city].copy()

    # High spike check
    spike_mask = city_df["pm25_ugm3"] > 500
    spike_count = spike_mask.sum()
    if spike_count:
        issues.append(ValidationIssue(
            check_name="pm25_spike",
            layer="cleaned_pm25",
            city=city,
            severity="warning",
            rows_affected=int(spike_count),
            description=(
                f"{city}: {spike_count} readings exceed 500 µg/m³ "
                f"(max={city_df['pm25_ugm3'].max():.1f}). "
                f"Consistent with severe smog events; retained but flagged."
            ),
            details={"spike_count": int(spike_count),
                     "max_value": float(city_df["pm25_ugm3"].max())},
        ))

    # Zero-run check (hourly city-level series)
    hourly = (
        city_df.groupby("timestamp_utc")["pm25_ugm3"]
        .median()
        .sort_index()
    )
    zero_run = 0
    max_zero_run = 0
    for val in hourly:
        if val == 0.0:
            zero_run += 1
            max_zero_run = max(max_zero_run, zero_run)
        else:
            zero_run = 0

    if max_zero_run >= 6:
        issues.append(ValidationIssue(
            check_name="pm25_zero_run",
            layer="cleaned_pm25",
            city=city,
            severity="warning",
            rows_affected=max_zero_run,
            description=(
                f"{city}: longest consecutive run of zero PM2.5 = {max_zero_run}h. "
                f"May indicate sensor offline rather than truly clean air."
            ),
            details={"max_zero_run_hours": max_zero_run},
        ))

    return issues


def check_weather_completeness(df: pd.DataFrame) -> list[ValidationIssue]:
    """Ensure weather covers the full PM2.5 date range for every city."""
    issues = []
    con = duckdb.connect(str(CLEANED_DB), read_only=True)
    pm25_ranges = con.execute("""
        SELECT city,
               MIN(timestamp_utc) AS pm25_min,
               MAX(timestamp_utc) AS pm25_max
        FROM cleaned_pm25
        GROUP BY city
    """).df()
    con.close()

    for _, row in pm25_ranges.iterrows():
        city   = row["city"]
        w_city = df[df["city"] == city]
        if w_city.empty:
            continue
        w_min = w_city["timestamp_utc"].min()
        w_max = w_city["timestamp_utc"].max()
        pm_min = pd.Timestamp(row["pm25_min"]).tz_convert("UTC") if pd.Timestamp(row["pm25_min"]).tzinfo else pd.Timestamp(row["pm25_min"], tz="UTC")
        pm_max = pd.Timestamp(row["pm25_max"]).tz_convert("UTC") if pd.Timestamp(row["pm25_max"]).tzinfo else pd.Timestamp(row["pm25_max"], tz="UTC")

        if w_min > pm_min or w_max < pm_max:
            issues.append(ValidationIssue(
                check_name="weather_coverage_gap",
                layer="cleaned_weather",
                city=city,
                severity="warning",
                rows_affected=0,
                description=(
                    f"{city}: weather range [{w_min} → {w_max}] does not fully "
                    f"cover PM2.5 range [{pm_min} → {pm_max}]."
                ),
                details={
                    "weather_min": str(w_min), "weather_max": str(w_max),
                    "pm25_min": str(pm_min),   "pm25_max": str(pm_max),
                },
            ))
    return issues


def check_gold_row_id_stability(df: pd.DataFrame) -> list[ValidationIssue]:
    """Verify row_ids are unique and sequential from 1."""
    issues = []
    expected = set(range(1, len(df) + 1))
    actual   = set(df["row_id"].tolist())
    if expected != actual:
        issues.append(ValidationIssue(
            check_name="gold_row_id_unstable",
            layer="gold",
            city="all",
            severity="error",
            rows_affected=len(expected.symmetric_difference(actual)),
            description="Gold table row_ids are not sequential from 1. Row IDs must be stable for citation.",
            details={},
        ))
    return issues


def check_no_future_leakage(df: pd.DataFrame) -> list[ValidationIssue]:
    """
    Verify lag features only use past data.
    lag_1h at time T must equal pm25_ugm3 at time T-1 for the same city.
    Spot-checks the first 1000 rows per city.
    """
    issues = []
    for city in CITIES:
        city_df = df[df["city"] == city].sort_values("timestamp_utc").head(1000).copy()
        city_df = city_df.set_index("timestamp_utc")
        mismatches = 0
        for ts, row in city_df.iterrows():
            prev_ts = ts - pd.Timedelta(hours=1)
            if prev_ts in city_df.index:
                expected_lag = city_df.loc[prev_ts, "pm25_ugm3"]
                actual_lag   = row["pm25_lag_1h"]
                if pd.notna(expected_lag) and pd.notna(actual_lag):
                    if abs(expected_lag - actual_lag) > 0.01:
                        mismatches += 1
        if mismatches:
            issues.append(ValidationIssue(
                check_name="data_leakage",
                layer="gold",
                city=city,
                severity="error",
                rows_affected=mismatches,
                description=(
                    f"{city}: {mismatches} rows where lag_1h != pm25[T-1]. "
                    f"Possible data leakage detected."
                ),
                details={"mismatches": mismatches},
            ))
    return issues


# ---------------------------------------------------------------------------
# Master runner
# ---------------------------------------------------------------------------

def run_all_checks() -> list[ValidationIssue]:
    """Run every validation check and return the full list of issues."""
    print("  [VAL] Loading data...")
    pm25    = _load_cleaned_pm25()
    weather = _load_cleaned_weather()
    gold    = _load_gold()

    all_issues: list[ValidationIssue] = []

    print("  [VAL] Schema checks...")
    all_issues += check_schema_pm25(pm25)
    all_issues += check_schema_weather(weather)
    all_issues += check_schema_gold(gold)

    print("  [VAL] Duplicate checks...")
    all_issues += check_duplicates(
        pm25, "cleaned_pm25",
        ["city", "location_id", "sensor_id", "timestamp_utc"]
    )
    all_issues += check_duplicates(
        weather, "cleaned_weather",
        ["city", "timestamp_utc"]
    )

    print("  [VAL] Temporal gap checks...")
    for city in CITIES:
        all_issues += check_temporal_gaps(pm25, city)

    print("  [VAL] Staleness checks...")
    for city in CITIES:
        all_issues += check_staleness(pm25, city)

    print("  [VAL] Distribution checks...")
    for city in CITIES:
        all_issues += check_pm25_distribution(pm25, city)

    print("  [VAL] Weather completeness...")
    all_issues += check_weather_completeness(weather)

    print("  [VAL] Gold table integrity...")
    all_issues += check_gold_row_id_stability(gold)
    all_issues += check_no_future_leakage(gold)

    return all_issues
