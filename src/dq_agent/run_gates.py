"""
Module: run_gates
Location: src/dq_agent/run_gates.py
Purpose: Orchestrator for the Data Quality Agent.

Runs all validation checks, converts issues to decisions,
writes quality_log.jsonl, and prints a summary.

Usage:
    python -m src.dq_agent.run_gates
"""

import json
import sys
from pathlib import Path

from src.dq_agent.validator import run_all_checks
from src.dq_agent.decision_engine import process_issues, print_summary


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_PATH     = PROJECT_ROOT / "results" / "quality_log.jsonl"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 72)
    print("PHASE 2B  —  DATA QUALITY AGENT")
    print("=" * 72)

    # 1. Run all validation checks
    print("\n[1/3] Running validation checks...")
    issues = run_all_checks()
    print(f"  [FOUND] {len(issues)} issue(s) detected")

    # 2. Convert to decisions
    print("\n[2/3] Applying decision rules (fix / fill / flag)...")
    decisions = process_issues(issues)

    # 3. Write quality log
    print("\n[3/3] Writing quality_log.jsonl...")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Overwrite on each run (append would create duplicate entries)
    with open(LOG_PATH, "w", encoding="utf-8") as fh:
        for decision in decisions:
            fh.write(json.dumps(decision, default=str) + "\n")

    print(f"  [LOG] {len(decisions)} decisions written → {LOG_PATH}")

    # 4. Summary
    print_summary(decisions)

    # 5. Exit with error code if any errors found (useful in CI / Prefect)
    error_count = sum(1 for d in decisions if d["severity"] == "error")

    print("\n" + "=" * 72)
    if error_count:
        print(f"[WARN] {error_count} ERROR-level issue(s) found. Review before training.")
    else:
        print("[OK] Data Quality Agent complete — no errors detected.")
    print(f"      Log : {LOG_PATH}")
    print("=" * 72)

    if error_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
