"""
Module: decision_engine
Location: src/dq_agent/decision_engine.py
Purpose: Map each ValidationIssue to a Fix/Fill/Flag decision with explanation.

Decision logic (matches hackathon guide table):
  fix   — certain, reversible correction (wrong type, duplicate, negative value)
  fill  — reasonable estimate, clearly marked (short gap ≤ 2h)
  flag  — do not guess; warn the user (long gap, spike, staleness, leakage)

Returns a list of Decision dicts ready to be written to quality_log.jsonl.
"""

from __future__ import annotations

import datetime
from typing import Any

from src.dq_agent.validator import ValidationIssue


# ---------------------------------------------------------------------------
# Decision rules table
# ---------------------------------------------------------------------------
# Maps check_name → (action, rationale_template)

_RULES: dict[str, tuple[str, str]] = {
    "schema_pm25": (
        "fix",
        "Schema violation corrected automatically during cleaning layer build. "
        "Type coercion or out-of-range values set to NULL.",
    ),
    "schema_weather": (
        "fix",
        "Schema violation corrected automatically during cleaning layer build.",
    ),
    "schema_gold": (
        "flag",
        "Gold table schema violation cannot be auto-corrected without rebuilding "
        "the processed layer. Manual review required.",
    ),
    "duplicate_rows": (
        "fix",
        "Duplicate rows removed by keeping the first occurrence per "
        "(city, location_id, sensor_id, timestamp_utc). "
        "Duplicates arise when sensors re-report corrected readings.",
    ),
    "temporal_gap_short": (
        "fill",
        "Gap is ≤2 hours in an otherwise smooth hourly series. "
        "Linear interpolation applied between flanking values. "
        "Filled values are marked with filled=True so they remain visible.",
    ),
    "temporal_gap_long": (
        "flag",
        "Gap exceeds 24 hours. Interpolating over this window would introduce "
        "unreliable estimates, especially during smog events where PM2.5 can "
        "change rapidly. Gap retained as NULL; user warned via dashboard.",
    ),
    "data_staleness": (
        "flag",
        "Source has not updated in over 48 hours. Data retained as-is but "
        "marked stale on the dashboard. EPO should check sensor connectivity.",
    ),
    "pm25_spike": (
        "flag",
        "Values >500 µg/m³ are physically possible during severe smog events "
        "in Pakistan (Lahore AQI regularly exceeds hazardous levels in winter). "
        "Values retained but flagged; they should not be silently removed.",
    ),
    "pm25_zero_run": (
        "flag",
        "Long consecutive run of zero PM2.5 readings likely indicates a sensor "
        "offline rather than genuinely clean air. Values flagged; "
        "exclude from model training or treat as missing.",
    ),
    "weather_coverage_gap": (
        "flag",
        "Weather data does not fully cover the PM2.5 date range. "
        "Rows outside weather coverage will have NULL weather features "
        "in the gold table, reducing usable training rows.",
    ),
    "gold_row_id_unstable": (
        "fix",
        "Row IDs rebuilt as sequential integers sorted by (city, timestamp_utc). "
        "Stable IDs are required for the RAG agent to cite specific rows.",
    ),
    "data_leakage": (
        "flag",
        "CRITICAL: lag_1h does not match PM2.5 at T-1. This indicates future "
        "information may have leaked into the feature set. "
        "Rebuild the gold table from scratch before any model training.",
    ),
}

# Severity → priority for sorting the log (lower = more urgent)
_PRIORITY = {"error": 0, "warning": 1, "info": 2}


# ---------------------------------------------------------------------------
# Decision dataclass (plain dict for JSON serialisation)
# ---------------------------------------------------------------------------

def make_decision(issue: ValidationIssue) -> dict[str, Any]:
    """
    Convert a ValidationIssue into a logged decision dict.

    Returns a dict with:
      timestamp, check_name, layer, city, severity,
      action (fix|fill|flag), rows_affected,
      description, explanation, details
    """
    rule = _RULES.get(issue.check_name)
    if rule:
        action, explanation = rule
    else:
        # Default: unknown checks are flagged for manual review
        action      = "flag"
        explanation = (
            f"No specific decision rule found for check '{issue.check_name}'. "
            f"Flagged for manual review."
        )

    return {
        "timestamp":     datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "check_name":    issue.check_name,
        "layer":         issue.layer,
        "city":          issue.city,
        "severity":      issue.severity,
        "action":        action,
        "rows_affected": issue.rows_affected,
        "description":   issue.description,
        "explanation":   explanation,
        "details":       issue.details,
    }


# ---------------------------------------------------------------------------
# Batch processor
# ---------------------------------------------------------------------------

def process_issues(issues: list[ValidationIssue]) -> list[dict[str, Any]]:
    """
    Convert a list of ValidationIssues into sorted decision dicts.
    Sorted by severity (errors first) then check_name for reproducibility.
    """
    decisions = [make_decision(issue) for issue in issues]
    decisions.sort(key=lambda d: (_PRIORITY.get(d["severity"], 9), d["check_name"]))
    return decisions


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def print_summary(decisions: list[dict[str, Any]]) -> None:
    """Print a human-readable summary of all decisions."""
    fix_count  = sum(1 for d in decisions if d["action"] == "fix")
    fill_count = sum(1 for d in decisions if d["action"] == "fill")
    flag_count = sum(1 for d in decisions if d["action"] == "flag")
    err_count  = sum(1 for d in decisions if d["severity"] == "error")

    print(f"\n  ┌─ DQ Agent Decision Summary ──────────────────────────┐")
    print(f"  │  Total issues   : {len(decisions):<5}                               │")
    print(f"  │  Errors         : {err_count:<5}  (schema / leakage)           │")
    print(f"  │  Actions → FIX  : {fix_count:<5}                               │")
    print(f"  │                   FILL : {fill_count:<5}  (interpolate short gaps) │")
    print(f"  │                   FLAG : {flag_count:<5}  (warn, do not guess)     │")
    print(f"  └──────────────────────────────────────────────────────┘")

    if err_count:
        print("\n  [!] ERRORS detected — review before training:")
        for d in decisions:
            if d["severity"] == "error":
                print(f"      • [{d['check_name']}] {d['description'][:80]}")

    print("\n  All decisions:")
    for d in decisions:
        icon = {"fix": "🔧", "fill": "🔄", "flag": "🚩"}.get(d["action"], "?")
        print(f"    {icon} [{d['action'].upper():4}] {d['city']:<12} "
              f"{d['check_name']:<30} rows={d['rows_affected']}")
