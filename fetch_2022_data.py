#!/usr/bin/env python3
"""
Fetch PM2.5 and weather data from 2022-01-01 to today.
Run: python fetch_2022_data.py
"""
import sys
from pathlib import Path
import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.fetch.fetch_openaq import OpenAQFetcher
from src.fetch.fetch_weather import WeatherFetcher

def main():
    date_from = '2022-01-01'
    date_to = datetime.date.today().isoformat()
    
    project_root = Path(__file__).parent
    raw_dir = project_root / 'data' / 'raw'
    manifest = project_root / 'manifest.csv'
    
    print("="*80)
    print(f"Fetching data from {date_from} to {date_to}")
    print("="*80)
    
    # PM2.5 data
    print("\n[1/2] Fetching PM2.5 from OpenAQ...")
    fetcher = OpenAQFetcher()
    
    cities_config = {
        'Lahore':    [8664, 1894641, 4515157, 4527035, 4527173, 4527306, 4527402, 4554729, 4555745, 4557686],
        'Karachi':   [8668, 1894644, 4791924, 4837113, 4837117, 4838712, 4847173, 4840233, 4932783, 4985886],
        'Islamabad': [8665, 1894642, 4515644, 4554236, 4556719, 4565419, 4565932, 4566426, 4567363, 4567364],
        'Peshawar':  [4600078, 4605118, 4607067, 4608423, 4608419, 4609262, 4609354, 4609307, 4952332, 6135308],
    }
    
    for city, locs in cities_config.items():
        df = fetcher.fetch_city_data(city, locs, date_from, date_to)
        if df.empty:
            print(f"  [SKIP] No data for {city}")
            continue
        
        out = raw_dir / f'openaq_pm25_{city.lower()}.parquet'
        sha = fetcher.save_to_parquet(df, out)
        fetcher.update_manifest(
            manifest, 'OpenAQ v3', 
            f'{city};{date_from};{date_to}', 
            out, sha, len(df)
        )
        print(f'  [SAVED] {city}: {len(df)} rows')
    
    # Weather data
    print("\n[2/2] Fetching weather from Open-Meteo...")
    weather_fetcher = WeatherFetcher()
    
    for city in ['Lahore', 'Karachi', 'Islamabad', 'Peshawar']:
        df = weather_fetcher.fetch_city_weather(city, date_from, date_to)
        if df.empty:
            print(f"  [SKIP] No data for {city}")
            continue
        
        out = raw_dir / f'weather_{city.lower()}.parquet'
        sha = weather_fetcher.save_to_parquet(df, out)
        coords = weather_fetcher.CITY_COORDS[city]
        weather_fetcher.update_manifest(
            manifest, city, 
            f'lat={coords["lat"]};lon={coords["lon"]};start={date_from};end={date_to}',
            out, sha, len(df)
        )
        print(f'  [SAVED] {city}: {len(df)} rows')
    
    print("\n" + "="*80)
    print("[DONE] Data fetch complete!")
    print("Next steps:")
    print("  1. python -m src.clean.build_cleaned")
    print("  2. python -m src.process.build_processed")
    print("  3. python -m src.model.train_forecast")
    print("="*80)

if __name__ == '__main__':
    main()
