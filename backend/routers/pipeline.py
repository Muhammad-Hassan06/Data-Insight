"""
Router: pipeline
Location: backend/routers/pipeline.py
Purpose: Provide pipeline control endpoints for manual triggering and live stats monitoring.
"""

from typing import Dict, Any
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, BackgroundTasks, HTTPException
import subprocess
import sys
import os

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])

# Track running pipeline jobs
_pipeline_status = {
    "is_running": False,
    "last_run": None,
    "last_status": None,
    "last_error": None,
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run_pipeline_job():
    """Background task to execute the hourly pipeline."""
    global _pipeline_status
    _pipeline_status["is_running"] = True
    _pipeline_status["last_error"] = None
    
    try:
        # Find Python executable (use same Python running this FastAPI server)
        python_exe = sys.executable
        
        # Run pipeline as subprocess
        result = subprocess.run(
            [python_exe, "-m", "src.flows.hourly_pipeline"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )
        
        if result.returncode == 0:
            _pipeline_status["last_status"] = "success"
        else:
            _pipeline_status["last_status"] = "failed"
            _pipeline_status["last_error"] = result.stderr[-500:] if result.stderr else "Unknown error"
            
    except subprocess.TimeoutExpired:
        _pipeline_status["last_status"] = "timeout"
        _pipeline_status["last_error"] = "Pipeline execution exceeded 10 minute timeout"
    except Exception as e:
        _pipeline_status["last_status"] = "error"
        _pipeline_status["last_error"] = str(e)
    finally:
        _pipeline_status["is_running"] = False
        _pipeline_status["last_run"] = datetime.now(timezone.utc).isoformat()


@router.post("/trigger")
async def trigger_pipeline(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Manually trigger the hourly data pipeline.
    
    Runs in background: fetch new data → clean → process → generate forecasts.
    Returns immediately with job status.
    """
    if _pipeline_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="Pipeline is already running. Please wait for current job to complete."
        )
    
    # Queue the pipeline job as a background task
    background_tasks.add_task(_run_pipeline_job)
    
    return {
        "status": "triggered",
        "message": "Pipeline job started in background",
        "estimated_duration": "5-10 minutes",
        "check_status_at": "/api/pipeline/status",
    }


@router.get("/status")
async def get_pipeline_status() -> Dict[str, Any]:
    """
    Get current pipeline execution status.
    
    Returns whether a job is running, last run time, and last execution result.
    """
    return {
        "is_running": _pipeline_status["is_running"],
        "last_run": _pipeline_status["last_run"],
        "last_status": _pipeline_status["last_status"],
        "last_error": _pipeline_status["last_error"],
    }


@router.get("/stats/live")
async def get_live_stats() -> Dict[str, Any]:
    """
    Get live dataset growth statistics.
    
    Returns:
        - Records added in the last hour
        - Total record counts
        - Growth rate metrics
    """
    try:
        import duckdb
        
        cleaned_db = PROJECT_ROOT / "data" / "cleaned" / "warehouse.duckdb"
        processed_db = PROJECT_ROOT / "data" / "processed" / "warehouse.duckdb"
        
        if not cleaned_db.exists() or not processed_db.exists():
            raise HTTPException(
                status_code=404,
                detail="Database files not found. Run pipeline first."
            )
        
        # Query cleaned data stats
        con_clean = duckdb.connect(str(cleaned_db), read_only=True)
        
        # Total PM2.5 records
        total_pm25 = con_clean.execute(
            "SELECT COUNT(*) as cnt FROM cleaned_pm25"
        ).fetchone()[0]
        
        # Total weather records
        total_weather = con_clean.execute(
            "SELECT COUNT(*) as cnt FROM cleaned_weather"
        ).fetchone()[0]
        
        # Records added in last hour (based on timestamp_utc column)
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        pm25_last_hour = con_clean.execute(
            f"SELECT COUNT(*) as cnt FROM cleaned_pm25 WHERE timestamp_utc >= '{one_hour_ago}'"
        ).fetchone()[0]
        
        weather_last_hour = con_clean.execute(
            f"SELECT COUNT(*) as cnt FROM cleaned_weather WHERE timestamp_utc >= '{one_hour_ago}'"
        ).fetchone()[0]
        
        # Latest timestamps
        latest_pm25 = con_clean.execute(
            "SELECT MAX(timestamp_utc) FROM cleaned_pm25"
        ).fetchone()[0]
        
        latest_weather = con_clean.execute(
            "SELECT MAX(timestamp_utc) FROM cleaned_weather"
        ).fetchone()[0]
        
        con_clean.close()
        
        # Query processed data stats
        con_proc = duckdb.connect(str(processed_db), read_only=True)
        
        total_gold = con_proc.execute(
            "SELECT COUNT(*) as cnt FROM gold_forecast_features"
        ).fetchone()[0]
        
        gold_last_hour = con_proc.execute(
            f"SELECT COUNT(*) as cnt FROM gold_forecast_features WHERE timestamp_utc >= '{one_hour_ago}'"
        ).fetchone()[0]
        
        con_proc.close()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "totals": {
                "pm25_records": total_pm25,
                "weather_records": total_weather,
                "gold_records": total_gold,
            },
            "last_hour": {
                "pm25_added": pm25_last_hour,
                "weather_added": weather_last_hour,
                "gold_added": gold_last_hour,
            },
            "latest_data": {
                "pm25_timestamp": str(latest_pm25) if latest_pm25 else None,
                "weather_timestamp": str(latest_weather) if latest_weather else None,
            },
            "growth_rate": {
                "pm25_per_hour": round(pm25_last_hour, 2),
                "weather_per_hour": round(weather_last_hour, 2),
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve live stats: {str(e)}"
        )
