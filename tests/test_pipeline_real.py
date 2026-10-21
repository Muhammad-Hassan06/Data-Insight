"""
Test script to verify the updated hourly pipeline works correctly
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_config_exists():
    """Test that pipeline configuration exists"""
    config_path = project_root / "config" / "pipeline_config.json"
    assert config_path.exists(), "Config file missing"
    
    import json
    with open(config_path, "r") as f:
        config = json.load(f)
    
    assert "cities" in config
    assert len(config["cities"]) == 4
    assert "fetch_settings" in config
    assert "model_settings" in config
    
    print("✓ Config file valid")


def test_models_exist():
    """Test that all 6 trained models exist"""
    models_dir = project_root / "models"
    
    required_models = [
        "lgb_median.pkl",
        "lgb_lower.pkl",
        "lgb_upper.pkl",
        "cb_median.cbm",
        "cb_lower.cbm",
        "cb_upper.cbm"
    ]
    
    for model_file in required_models:
        model_path = models_dir / model_file
        assert model_path.exists(), f"Model missing: {model_file}"
    
    print("✓ All 6 models present")


def test_warehouse_exists():
    """Test that processed warehouse exists"""
    warehouse_path = project_root / "data" / "processed" / "warehouse.duckdb"
    assert warehouse_path.exists(), "Processed warehouse missing"
    
    import duckdb
    conn = duckdb.connect(str(warehouse_path), read_only=True)
    
    # Check gold table exists
    tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
    assert "gold_forecast_features" in tables
    
    # Check row count
    count = conn.execute("SELECT COUNT(*) FROM gold_forecast_features").fetchone()[0]
    assert count > 0, "Gold table is empty"
    
    conn.close()
    print(f"✓ Warehouse ready ({count} rows)")


def test_pipeline_imports():
    """Test that pipeline imports work"""
    try:
        from src.flows.hourly_pipeline import (
            fetch_new_data,
            clean_data,
            process_data,
            run_quality_gates,
            update_forecasts,
            hourly_pipeline
        )
        print("✓ Pipeline imports successful")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        raise


def test_forecast_generation():
    """Test forecast generation with trained models"""
    print("\n" + "=" * 70)
    print("Testing forecast generation...")
    print("=" * 70)
    
    from src.flows.hourly_pipeline import update_forecasts
    
    # Run forecast generation
    result = update_forecasts()
    
    print(f"\nResult: {result}")
    
    assert result["status"] == "success", f"Forecast failed: {result}"
    assert result["forecast_count"] > 0, "No forecasts generated"
    assert result["cities"] == 4, "Should have 4 cities"
    assert result["forecast_hours"] == 24, "Should forecast 24 hours"
    
    # Check output file exists
    forecast_file = project_root / "predictions" / "latest_forecast.parquet"
    assert forecast_file.exists(), "Forecast file not created"
    
    import pandas as pd
    df = pd.read_parquet(forecast_file)
    
    assert len(df) == 96, f"Expected 96 forecasts (4 cities × 24h), got {len(df)}"
    assert "model_version" in df.columns, "Model version not tracked"
    
    print(f"\n✓ Forecast generation successful!")
    print(f"  - Generated: {len(df)} forecasts")
    print(f"  - Cities: {df['city'].nunique()}")
    print(f"  - Model: {df['model_version'].iloc[0]}")
    
    # Show sample forecasts
    print("\nSample forecasts:")
    for city in df['city'].unique():
        city_df = df[df['city'] == city]
        median = city_df['pm25_median'].iloc[0]
        lower = city_df['pm25_lower'].iloc[0]
        upper = city_df['pm25_upper'].iloc[0]
        print(f"  {city:12} → {median:6.2f} µg/m³ (range: {lower:.2f}-{upper:.2f})")


if __name__ == "__main__":
    print("Testing Updated Hourly Pipeline\n")
    
    try:
        test_config_exists()
        test_models_exist()
        test_warehouse_exists()
        test_pipeline_imports()
        test_forecast_generation()
        
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED! ✓")
        print("=" * 70)
        print("\nYour pipeline is ready to:")
        print("  1. Fetch real data from OpenAQ + Open-Meteo APIs")
        print("  2. Generate forecasts using your trained LightGBM + CatBoost models")
        print("  3. Serve predictions through the backend API")
        print("\nNext steps:")
        print("  - Run: python -m src.flows.hourly_pipeline")
        print("  - Or setup cron job for hourly execution")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
