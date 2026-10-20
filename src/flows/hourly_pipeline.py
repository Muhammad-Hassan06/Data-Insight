"""
Hourly PM2.5 Forecasting Pipeline with Prefect
Automated workflow for data fetching, processing, and forecasting
"""

from prefect import flow, task
from datetime import datetime, timedelta, timezone
from pathlib import Path
import duckdb
import pandas as pd
import pickle
from typing import Dict, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@task(name="fetch_new_data", retries=3, retry_delay_seconds=60)
def fetch_new_data() -> Dict[str, int]:
    """
    Fetch last 24 hours of PM2.5 and weather data from APIs.
    
    Returns:
        Dict with counts of new records fetched
    """
    from src.fetch.fetch_openaq import OpenAQFetcher
    from src.fetch.fetch_weather import WeatherFetcher
    
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)
    
    date_from = start_time.strftime("%Y-%m-%d")
    date_to = end_time.strftime("%Y-%m-%d")
    
    logger.info(f"Fetching data from {date_from} to {date_to}")
    
    cities = ["Lahore", "Karachi", "Islamabad", "Peshawar"]
    pm25_count = 0
    weather_count = 0
    
    # Initialize fetchers
    openaq_fetcher = OpenAQFetcher()
    weather_fetcher = WeatherFetcher()
    
    # Note: For incremental hourly runs, we'd need location_ids
    # For now, skip fetch since we already have historical data
    # In production, you'd store location_ids and use them here
    logger.info("Skipping API fetch - using existing historical data")
    logger.info("(In production, implement incremental fetch with stored location_ids)")
    
    # Fetch weather data (simpler API, no location_ids needed)
    for city in cities:
        try:
            data = weather_fetcher.fetch_city_weather(
                city_name=city,
                date_from=date_from,
                date_to=date_to
            )
            weather_count += len(data) if not data.empty else 0
            logger.info(f"Fetched {len(data) if not data.empty else 0} weather records for {city}")
        except Exception as e:
            logger.error(f"Error fetching weather for {city}: {e}")
    
    return {
        "pm25_records": pm25_count,
        "weather_records": weather_count,
        "fetch_time": datetime.now(timezone.utc).isoformat(),
        "note": "Using existing historical data for demo"
    }



@task(name="clean_data")
def clean_data() -> Dict[str, int]:
    """
    Run data cleaning on newly fetched data.
    
    Returns:
        Dict with counts of cleaned records
    """
    from src.clean.build_cleaned import main as clean_main
    
    logger.info("Starting data cleaning...")
    
    # Run the cleaning pipeline
    clean_main()
    
    # Count results from cleaned warehouse
    db_path = Path("data/cleaned/warehouse.duckdb")
    if db_path.exists():
        conn = duckdb.connect(str(db_path), read_only=True)
        pm25_count = conn.execute("SELECT COUNT(*) FROM cleaned_pm25").fetchone()[0]
        weather_count = conn.execute("SELECT COUNT(*) FROM cleaned_weather").fetchone()[0]
        conn.close()
        
        logger.info(f"Cleaned {pm25_count} PM2.5 rows")
        logger.info(f"Cleaned {weather_count} weather rows")
        
        return {
            "pm25_rows": pm25_count,
            "weather_rows": weather_count,
            "status": "success"
        }
    else:
        return {"status": "no_warehouse"}



@task(name="process_data")
def process_data() -> Dict[str, int]:
    """
    Update gold table with new rows and engineer features.
    
    Returns:
        Dict with counts of processed records
    """
    from src.process.build_processed import main as process_main
    
    logger.info("Starting feature engineering...")
    
    # Run the processing pipeline
    process_main()
    
    # Count results from processed warehouse
    db_path = Path("data/processed/warehouse.duckdb")
    if db_path.exists():
        conn = duckdb.connect(str(db_path), read_only=True)
        gold_count = conn.execute("SELECT COUNT(*) FROM gold_forecast_features").fetchone()[0]
        conn.close()
        
        logger.info(f"Processed {gold_count} rows in gold table")
        
        return {
            "gold_rows": gold_count,
            "status": "success"
        }
    else:
        return {"status": "no_warehouse"}



@task(name="run_quality_gates")
def run_quality_gates() -> Dict[str, List]:
    """
    Run data quality checks and log decisions.
    
    Returns:
        Dict with quality issues and decisions
    """
    logger.info("Running data quality gates...")
    
    # For now, basic quality check
    db_path = Path("data/processed/warehouse.duckdb")
    
    if not db_path.exists():
        logger.warning("Warehouse does not exist yet")
        return {"issues": [], "status": "skipped"}
    
    conn = duckdb.connect(str(db_path), read_only=True)
    
    # Check for nulls in critical columns
    query = """
        SELECT 
            COUNT(*) as total_rows,
            SUM(CASE WHEN pm25_ugm3 IS NULL THEN 1 ELSE 0 END) as null_pm25,
            SUM(CASE WHEN temperature IS NULL THEN 1 ELSE 0 END) as null_temp,
            MAX(timestamp_utc) as latest_timestamp
        FROM gold_forecast_features
    """
    
    result = conn.execute(query).fetchone()
    conn.close()
    
    issues = []
    if result[1] > 0:
        issues.append(f"{result[1]} null PM2.5 values")
    if result[2] > 0:
        issues.append(f"{result[2]} null temperature values")
    
    logger.info(f"Quality check: {len(issues)} issues found")
    logger.info(f"Latest data timestamp: {result[3]}")
    
    return {
        "total_rows": result[0],
        "issues": issues,
        "latest_timestamp": str(result[3]),
        "status": "passed" if len(issues) == 0 else "issues_found"
    }


@task(name="update_forecasts")
def update_forecasts() -> Dict[str, int]:
    """
    Generate next 24h predictions for all cities.
    
    Returns:
        Dict with forecast counts
    """
    logger.info("Generating forecasts...")
    
    # Load models
    models_dir = Path("models")
    model_median = pickle.load(open(models_dir / "lgb_median.pkl", "rb"))
    model_lower = pickle.load(open(models_dir / "lgb_lower.pkl", "rb"))
    model_upper = pickle.load(open(models_dir / "lgb_upper.pkl", "rb"))
    
    logger.info("Models loaded successfully")
    
    # Load latest data from warehouse
    db_path = Path("data/processed/warehouse.duckdb")
    conn = duckdb.connect(str(db_path), read_only=True)
    
    # Get last 168 hours (7 days) for each city to compute lags
    query = """
        SELECT *
        FROM gold_forecast_features
        WHERE timestamp_utc >= NOW() - INTERVAL '168 hours'
        ORDER BY city, timestamp_utc
    """
    
    data = conn.execute(query).fetchdf()
    conn.close()
    
    if data.empty:
        logger.warning("No data available for forecasting")
        return {"forecast_count": 0, "status": "no_data"}
    
    # Season encoding map (must match training)
    season_map = {'winter': 0, 'spring': 1, 'summer': 2, 'autumn': 3, 'fall': 3}
    
    # Feature columns to EXCLUDE (must match training script exactly)
    # From train_forecast.py: EXCLUDE_COLS includes sensor_count, is_weekend, any_flagged
    EXCLUDE_COLS = ['row_id', 'city', 'timestamp_utc', 'pm25_ugm3', 
                    'any_flagged', 'sensor_count', 'is_weekend']
    
    # Generate forecasts for next 24 hours
    forecast_hours = 24
    cities = data['city'].unique()
    all_forecasts = []
    
    for city in cities:
        city_data = data[data['city'] == city].copy()
        
        # Get the latest record
        latest = city_data.iloc[-1].copy()
        
        # Encode season to numeric if it's a string
        if 'season' in latest.index and isinstance(latest['season'], str):
            latest['season'] = season_map.get(latest['season'].lower(), 0)
        
        # Feature columns (must match training exactly)
        feature_cols = [col for col in city_data.columns if col not in EXCLUDE_COLS]
        
        for h in range(1, forecast_hours + 1):
            # Create forecast timestamp
            forecast_time = pd.to_datetime(latest['timestamp_utc']) + timedelta(hours=h)
            
            # Prepare features (simplified - in production would update lags properly)
            features = latest[feature_cols].values.reshape(1, -1)
            
            # Generate predictions
            pred_median = model_median.predict(features)[0]
            pred_lower = model_lower.predict(features)[0]
            pred_upper = model_upper.predict(features)[0]
            
            all_forecasts.append({
                'city': city,
                'timestamp': forecast_time,
                'forecast_hour': h,
                'pm25_median': pred_median,
                'pm25_lower': pred_lower,
                'pm25_upper': pred_upper,
                'generated_at': datetime.now(timezone.utc)
            })
    
    # Save forecasts
    forecasts_df = pd.DataFrame(all_forecasts)
    output_dir = Path("predictions")
    output_dir.mkdir(exist_ok=True)
    
    # Save latest forecast
    forecasts_df.to_parquet(output_dir / "latest_forecast.parquet", index=False)
    
    # Also save timestamped version
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    forecasts_df.to_parquet(output_dir / f"forecast_{timestamp_str}.parquet", index=False)
    
    logger.info(f"Generated {len(all_forecasts)} forecasts for {len(cities)} cities")
    
    return {
        "forecast_count": len(all_forecasts),
        "cities": len(cities),
        "hours": forecast_hours,
        "status": "success"
    }


@flow(name="hourly_forecast_flow", log_prints=True)
def hourly_pipeline():
    """
    Main pipeline flow that orchestrates all tasks.
    Runs hourly to fetch new data, clean, process, and generate forecasts.
    """
    logger.info("=" * 70)
    logger.info("Starting Hourly PM2.5 Forecasting Pipeline")
    logger.info(f"Pipeline run time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 70)
    
    # Task 1: Fetch new data
    fetch_result = fetch_new_data()
    logger.info(f"Fetch completed: {fetch_result}")
    
    # Task 2: Clean data
    clean_result = clean_data()
    logger.info(f"Clean completed: {clean_result}")
    
    # Task 3: Process data and engineer features
    process_result = process_data()
    logger.info(f"Process completed: {process_result}")
    
    # Task 4: Run quality gates
    quality_result = run_quality_gates()
    logger.info(f"Quality check completed: {quality_result}")
    
    # Task 5: Generate forecasts
    forecast_result = update_forecasts()
    logger.info(f"Forecast completed: {forecast_result}")
    
    logger.info("=" * 70)
    logger.info("Pipeline completed successfully!")
    logger.info("=" * 70)
    
    return {
        "pipeline_run_time": datetime.now(timezone.utc).isoformat(),
        "fetch": fetch_result,
        "clean": clean_result,
        "process": process_result,
        "quality": quality_result,
        "forecast": forecast_result
    }


if __name__ == "__main__":
    # Run the pipeline once for testing
    result = hourly_pipeline()
    print("\nPipeline Result:")
    print(result)
