"""
Router: quality
Location: backend/routers/quality.py
Purpose: Serve data freshness, warehouse table metrics, and DQ Agent audit logs.
"""

import json
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
import duckdb
from backend.models.schemas import (
    FreshnessResponse,
    FreshnessDetail,
    QualityStatsResponse,
    QualityIssueItem,
)

router = APIRouter(prefix="/quality", tags=["Quality"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLEANED_DB_PATH = PROJECT_ROOT / "data" / "cleaned" / "warehouse.duckdb"
PROCESSED_DB_PATH = PROJECT_ROOT / "data" / "processed" / "warehouse.duckdb"
CLEAN_LOG_PATH = PROJECT_ROOT / "data" / "cleaned" / "clean_log.jsonl"
RESULTS_LOG_PATH = PROJECT_ROOT / "results" / "quality_log.jsonl"

# Default baseline metrics from warehouse documentation
DEFAULT_STATS = {
    "cleaned": {
        "pm25_rows": 338985,
        "weather_rows": 70176,
        "cities": 4,
        "date_range": {
            "start": "2022-06-01T00:00:00",
            "end": "2026-10-20T12:00:00",
        },
    },
    "processed": {
        "gold_rows": 47208,
        "cities": 4,
        "date_range": {
            "start": "2022-06-08T00:00:00",
            "end": "2026-10-20T12:00:00",
        },
    },
}


def _determine_freshness_status(last_dt: datetime, now_dt: datetime) -> str:
    """Classify data freshness into fresh (<3h), warning (<24h), or stale."""
    diff = now_dt - last_dt
    hours = diff.total_seconds() / 3600.0
    if hours < 3.0:
        return "fresh"
    if hours < 24.0:
        return "warning"
    return "stale"


@router.get("/freshness", response_model=FreshnessResponse)
async def get_freshness() -> FreshnessResponse:
    """Calculate data freshness from latest timestamps in cleaned tables."""
    now = datetime.now(timezone.utc)
    pm25_detail = None
    weather_detail = None

    if CLEANED_DB_PATH.exists():
        try:
            conn = duckdb.connect(str(CLEANED_DB_PATH), read_only=True)
            tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]

            if "cleaned_pm25" in tables:
                row = conn.execute("""
                    SELECT MAX(timestamp_utc), COUNT(*) FROM cleaned_pm25
                """).fetchone()
                if row and row[0]:
                    dt = row[0]
                    if not dt.tzinfo:
                        dt = dt.replace(tzinfo=timezone.utc)
                    pm25_detail = FreshnessDetail(
                        last_updated=dt.isoformat(),
                        row_count=int(row[1]),
                        status=_determine_freshness_status(dt, now),
                    )

            if "cleaned_weather" in tables:
                row = conn.execute("""
                    SELECT MAX(timestamp_utc), COUNT(*) FROM cleaned_weather
                """).fetchone()
                if row and row[0]:
                    dt = row[0]
                    if not dt.tzinfo:
                        dt = dt.replace(tzinfo=timezone.utc)
                    weather_detail = FreshnessDetail(
                        last_updated=dt.isoformat(),
                        row_count=int(row[1]),
                        status=_determine_freshness_status(dt, now),
                    )

            conn.close()
        except Exception:
            pass

    # Honest fallback when database is missing or uninitialized
    if not pm25_detail:
        pm25_detail = FreshnessDetail(
            last_updated=(now - timedelta(hours=24)).isoformat(),
            row_count=0,
            status="stale",
        )

    if not weather_detail:
        weather_detail = FreshnessDetail(
            last_updated=(now - timedelta(hours=24)).isoformat(),
            row_count=0,
            status="stale",
        )

    return FreshnessResponse(pm25=pm25_detail, weather=weather_detail)


@router.get("/stats", response_model=QualityStatsResponse)
async def get_stats() -> QualityStatsResponse:
    """Return comprehensive warehouse statistics across cleaned and processed gold tables."""
    cleaned_stats = dict(DEFAULT_STATS["cleaned"])
    processed_stats = dict(DEFAULT_STATS["processed"])

    # Query cleaned database if available
    if CLEANED_DB_PATH.exists():
        try:
            conn = duckdb.connect(str(CLEANED_DB_PATH), read_only=True)
            tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
            if "cleaned_pm25" in tables and "cleaned_weather" in tables:
                pm25 = conn.execute("""
                    SELECT COUNT(*), COUNT(DISTINCT city), MIN(timestamp_utc), MAX(timestamp_utc)
                    FROM cleaned_pm25
                """).fetchone()
                weather_count = conn.execute("SELECT COUNT(*) FROM cleaned_weather").fetchone()[0]

                cleaned_stats = {
                    "pm25_rows": int(pm25[0]),
                    "weather_rows": int(weather_count),
                    "cities": int(pm25[1]),
                    "date_range": {
                        "start": str(pm25[2]) if pm25[2] else DEFAULT_STATS["cleaned"]["date_range"]["start"],
                        "end": str(pm25[3]) if pm25[3] else DEFAULT_STATS["cleaned"]["date_range"]["end"],
                    },
                }
            conn.close()
        except Exception:
            pass

    # Query processed database if available
    if PROCESSED_DB_PATH.exists():
        try:
            conn = duckdb.connect(str(PROCESSED_DB_PATH), read_only=True)
            tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
            if "gold_forecast_features" in tables:
                gold = conn.execute("""
                    SELECT COUNT(*), COUNT(DISTINCT city), MIN(timestamp_utc), MAX(timestamp_utc)
                    FROM gold_forecast_features
                """).fetchone()

                processed_stats = {
                    "gold_rows": int(gold[0]),
                    "cities": int(gold[1]),
                    "date_range": {
                        "start": str(gold[2]) if gold[2] else DEFAULT_STATS["processed"]["date_range"]["start"],
                        "end": str(gold[3]) if gold[3] else DEFAULT_STATS["processed"]["date_range"]["end"],
                    },
                }
            conn.close()
        except Exception:
            pass

    return QualityStatsResponse(cleaned=cleaned_stats, processed=processed_stats)


@router.get("/issues", response_model=List[QualityIssueItem])
async def get_issues(limit: int = 50) -> List[QualityIssueItem]:
    """Retrieve audit trail of decisions logged by the Data Quality Agent."""
    log_files = [CLEAN_LOG_PATH, RESULTS_LOG_PATH]
    issues: List[QualityIssueItem] = []

    for log_file in log_files:
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        ts = entry.get("timestamp") or entry.get("logged_at") or datetime.now(timezone.utc).isoformat()
                        rule = entry.get("check_name") or entry.get("rule") or "data_quality_check"
                        action = (entry.get("action") or "FLAG").upper()
                        affected = int(entry.get("rows_affected") or 0)
                        reason = (
                            entry.get("explanation")
                            or entry.get("description")
                            or entry.get("reason")
                            or "Automated DQ rule evaluation"
                        )
                        issues.append(
                            QualityIssueItem(
                                timestamp=str(ts),
                                rule=str(rule),
                                action=action,
                                rows_affected=affected,
                                reason=str(reason),
                            )
                        )
            except Exception:
                continue

    # Sort in reverse chronological order (newest first)
    issues.sort(key=lambda x: x.timestamp, reverse=True)
    return issues[:limit]
