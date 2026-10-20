"""
Test script for the hourly pipeline
Verifies structure without running full data operations
"""

def test_imports():
    """Test that all imports work."""
    print("Testing imports...")
    
    try:
        from src.flows.hourly_pipeline import (
            fetch_new_data,
            clean_data,
            process_data,
            run_quality_gates,
            update_forecasts,
            hourly_pipeline
        )
        print("✓ All task imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_prefect_decorators():
    """Test that Prefect decorators are working."""
    print("\nTesting Prefect decorators...")
    
    try:
        from src.flows.hourly_pipeline import fetch_new_data, hourly_pipeline
        
        # Check if decorated as task
        if hasattr(fetch_new_data, '__prefect_task__') or hasattr(fetch_new_data, 'fn'):
            print("✓ Tasks are properly decorated")
        else:
            print("⚠ Tasks may not be properly decorated")
        
        # Check if flow is decorated
        if hasattr(hourly_pipeline, '__prefect_flow__') or hasattr(hourly_pipeline, 'fn'):
            print("✓ Flow is properly decorated")
        else:
            print("⚠ Flow may not be properly decorated")
        
        return True
    except Exception as e:
        print(f"✗ Decorator test error: {e}")
        return False


def test_pipeline_structure():
    """Test the pipeline DAG structure."""
    print("\nTesting pipeline structure...")
    
    try:
        from src.flows.hourly_pipeline import hourly_pipeline
        import inspect
        
        # Get the source code
        source = inspect.getsource(hourly_pipeline)
        
        # Check for expected task calls
        expected_tasks = [
            'fetch_new_data',
            'clean_data',
            'process_data',
            'run_quality_gates',
            'update_forecasts'
        ]
        
        all_found = True
        for task in expected_tasks:
            if task in source:
                print(f"  ✓ {task} called in pipeline")
            else:
                print(f"  ✗ {task} NOT found in pipeline")
                all_found = False
        
        return all_found
    except Exception as e:
        print(f"✗ Structure test error: {e}")
        return False


def test_model_files():
    """Test that model files exist."""
    print("\nTesting model files...")
    
    from pathlib import Path
    
    models_dir = Path("models")
    required_models = ["lgb_median.pkl", "lgb_lower.pkl", "lgb_upper.pkl"]
    
    all_exist = True
    for model_file in required_models:
        model_path = models_dir / model_file
        if model_path.exists():
            print(f"  ✓ {model_file} exists")
        else:
            print(f"  ✗ {model_file} NOT found")
            all_exist = False
    
    return all_exist


def test_database_paths():
    """Test that database paths are accessible."""
    print("\nTesting database paths...")
    
    from pathlib import Path
    
    paths = {
        "cleaned": Path("data/cleaned/warehouse.duckdb"),
        "processed": Path("data/processed/warehouse.duckdb")
    }
    
    for name, path in paths.items():
        if path.exists():
            print(f"  ✓ {name} warehouse exists")
        else:
            print(f"  ⚠ {name} warehouse NOT found (will be created on first run)")
    
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("HOURLY PIPELINE TEST SUITE")
    print("=" * 70)
    
    results = {
        "imports": test_imports(),
        "decorators": test_prefect_decorators(),
        "structure": test_pipeline_structure(),
        "models": test_model_files(),
        "databases": test_database_paths()
    }
    
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ Pipeline is ready to run!")
        print("\nTo run manually:")
        print("  python -m src.flows.hourly_pipeline")
        print("\nTo deploy with Prefect:")
        print("  1. Start Prefect server: prefect server start")
        print("  2. Deploy: prefect deploy src/flows/hourly_pipeline.py:hourly_pipeline")
    else:
        print(f"\n⚠ {total - passed} test(s) failed - review output above")
    
    print("=" * 70)
    
    return passed == total


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
