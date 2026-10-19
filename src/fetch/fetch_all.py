"""
Module: fetch_all
Location: src/fetch/fetch_all.py
Purpose: Orchestrate all data fetching (PM2.5 + Weather) for the pipeline.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.fetch.fetch_openaq import main as fetch_openaq_main
from src.fetch.fetch_weather import main as fetch_weather_main


def main():
    """Run all data fetchers in sequence."""
    
    print("\n" + "="*80)
    print("PHASE 1B: DATA ACQUISITION")
    print("="*80)
    print("\nThis will fetch:")
    print("  • PM2.5 measurements from OpenAQ (4 cities, last 2 years)")
    print("  • Weather data from Open-Meteo (4 cities, last 2 years)")
    print("\nEstimated time: 5-15 minutes")
    print("="*80 + "\n")
    
    input("Press Enter to continue or Ctrl+C to cancel...")
    
    try:
        # Step 1: Fetch PM2.5 data from OpenAQ
        print("\n[STEP 1/2] Fetching PM2.5 data from OpenAQ...")
        fetch_openaq_main()
        
        # Step 2: Fetch weather data from Open-Meteo
        print("\n[STEP 2/2] Fetching weather data from Open-Meteo...")
        fetch_weather_main()
        
        print("\n" + "="*80)
        print("✓ PHASE 1B COMPLETE")
        print("="*80)
        print("\nNext steps:")
        print("  1. Review raw data in data/raw/")
        print("  2. Check manifest.csv for file hashes")
        print("  3. Run: make data  (to build cleaned layer)")
        print("="*80 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Data fetch interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Data fetch failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
