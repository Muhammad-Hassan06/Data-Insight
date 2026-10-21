"""
Module: fetch_weather
Location: src/fetch/fetch_weather.py
Purpose: Fetch hourly weather data from Open-Meteo API for Pakistani cities.
"""

import os
import time
import datetime
import hashlib
import httpx
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Dict, List, Any, Optional


class WeatherFetcher:
    """Fetches hourly weather data from Open-Meteo API."""

    # City coordinates
    CITY_COORDS = {
        'Lahore': {'lat': 31.5497, 'lon': 74.3436},
        'Karachi': {'lat': 24.8607, 'lon': 67.0011},
        'Islamabad': {'lat': 33.6844, 'lon': 73.0479},
        'Peshawar': {'lat': 34.0151, 'lon': 71.5249}
    }

    def __init__(self):
        """Initialize the weather fetcher."""
        self.client = httpx.Client(timeout=60.0)
        self.base_url = "https://archive-api.open-meteo.com/v1/archive"
        self.min_request_interval = 1.0
        self.last_request_time = 0.0

    def _rate_limit_wait(self) -> None:
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def fetch_city_weather(
        self,
        city_name: str,
        date_from: str,
        date_to: str
    ) -> pd.DataFrame:
        """
        Fetch hourly weather data for a city.
        
        Args:
            city_name: City name
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame with weather data
        """
        if city_name not in self.CITY_COORDS:
            raise ValueError(f"Unknown city: {city_name}")
        
        coords = self.CITY_COORDS[city_name]
        
        print(f"\n[*] Fetching weather for {city_name}...", end=' ')
        
        params = {
            'latitude': coords['lat'],
            'longitude': coords['lon'],
            'start_date': date_from,
            'end_date': date_to,
            'hourly': ','.join([
                'temperature_2m',
                'relative_humidity_2m',
                'dew_point_2m',
                'precipitation',
                'surface_pressure',
                'cloud_cover',
                'wind_speed_10m',
                'wind_direction_10m'
            ]),
            'timezone': 'UTC'
        }
        
        self._rate_limit_wait()
        
        try:
            response = self.client.get(self.base_url, params=params)
            
            if response.status_code != 200:
                print(f"[ERROR] HTTP {response.status_code}")
                return pd.DataFrame()
            
            data = response.json()
            
            # Parse hourly data
            hourly = data.get('hourly', {})
            
            df = pd.DataFrame({
                'timestamp_utc': pd.to_datetime(hourly['time'], utc=True),
                'city': city_name,
                'temperature': hourly['temperature_2m'],
                'humidity': hourly['relative_humidity_2m'],
                'dew_point': hourly['dew_point_2m'],
                'precipitation': hourly['precipitation'],
                'pressure': hourly['surface_pressure'],
                'cloud_cover': hourly['cloud_cover'],
                'wind_speed': hourly['wind_speed_10m'],
                'wind_direction': hourly['wind_direction_10m'],
                'latitude': coords['lat'],
                'longitude': coords['lon']
            })
            
            print(f"[OK] {len(df)} records")
            
            return df
            
        except Exception as e:
            print(f"[ERROR] {e}")
            return pd.DataFrame()

    def save_to_parquet(self, df: pd.DataFrame, output_path: Path) -> str:
        """
        Save DataFrame to Parquet and return SHA-256.
        
        Args:
            df: DataFrame to save
            output_path: Output file path
            
        Returns:
            SHA-256 hash
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        table = pa.Table.from_pandas(df)
        pq.write_table(table, output_path, compression='snappy')
        
        sha256_hash = hashlib.sha256()
        with open(output_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()

    def update_manifest(
        self,
        manifest_path: Path,
        city: str,
        query_params: str,
        output_file: Path,
        sha256: str,
        row_count: int
    ) -> None:
        """Update manifest.csv with weather file metadata."""
        fetch_time_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        if manifest_path.exists():
            manifest_df = pd.read_csv(manifest_path)
        else:
            manifest_df = pd.DataFrame(columns=[
                'source', 'query_or_url', 'fetch_time_utc', 'sha256',
                'licence', 'row_count', 'output_file'
            ])
        
        new_entry = pd.DataFrame([{
            'source': 'Open-Meteo Archive API',
            'query_or_url': query_params,
            'fetch_time_utc': fetch_time_utc,
            'sha256': sha256,
            'licence': 'CC-BY-4.0',
            'row_count': row_count,
            'output_file': str(output_file.relative_to(manifest_path.parent))
        }])
        
        manifest_df = pd.concat([manifest_df, new_entry], ignore_index=True)
        manifest_df.to_csv(manifest_path, index=False)
        
        print(f"  [MANIFEST] Updated")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()


def main():
    """Main execution: Fetch weather data for Pakistani cities."""
    
    fetcher = WeatherFetcher()
    
    # Date range: Last 2 years
    date_to = datetime.date.today().isoformat()
    date_from = (datetime.date.today() - datetime.timedelta(days=730)).isoformat()
    
    print("="*80)
    print("Open-Meteo Weather Data Fetch")
    print("="*80)
    print(f"Date range: {date_from} to {date_to}")
    print(f"Cities: {list(fetcher.CITY_COORDS.keys())}")
    print("="*80)
    
    # Setup paths
    project_root = Path(__file__).parent.parent.parent
    raw_data_dir = project_root / 'data' / 'raw'
    manifest_path = project_root / 'manifest.csv'
    
    # Fetch weather for each city
    for city_name in fetcher.CITY_COORDS.keys():
        df = fetcher.fetch_city_weather(
            city_name=city_name,
            date_from=date_from,
            date_to=date_to
        )
        
        if df.empty:
            print(f"  [SKIP] No data for {city_name}")
            continue
        
        # Save to Parquet
        output_file = raw_data_dir / f"weather_{city_name.lower()}.parquet"
        sha256 = fetcher.save_to_parquet(df, output_file)
        
        print(f"  [SAVED] {output_file}")
        print(f"  [SHA256] {sha256}")
        
        # Update manifest
        coords = fetcher.CITY_COORDS[city_name]
        query_params = f"lat={coords['lat']};lon={coords['lon']};start={date_from};end={date_to}"
        fetcher.update_manifest(
            manifest_path=manifest_path,
            city=city_name,
            query_params=query_params,
            output_file=output_file,
            sha256=sha256,
            row_count=len(df)
        )
    
    print("\n" + "="*80)
    print("[OK] Weather fetch complete!")
    print(f"[MANIFEST] {manifest_path}")
    print(f"[RAW DATA] {raw_data_dir}")
    print("="*80)


if __name__ == "__main__":
    main()
