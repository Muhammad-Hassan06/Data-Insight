"""
Module: fetch_openaq
Location: src/fetch/fetch_openaq.py
Purpose: Fetch hourly PM2.5 measurements from OpenAQ API v3 for Pakistani cities.
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
from dotenv import load_dotenv


class OpenAQFetcher:
    """Fetches hourly PM2.5 data from OpenAQ API v3."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the fetcher.
        
        Args:
            api_key: OpenAQ API key (loads from env if not provided)
        """
        load_dotenv()
        self.api_key = api_key or os.getenv('OPENAQ_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAQ_API_KEY not found in environment")
        
        self.client = httpx.Client(
            timeout=60.0,
            headers={'X-API-Key': self.api_key}
        )
        self.base_url = "https://api.openaq.org/v3"
        self.min_request_interval = 1.0  # Rate limiting: 60 req/min
        self.last_request_time = 0.0

    def _rate_limit_wait(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make API request with rate limiting and retry logic.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response data
        """
        url = f"{self.base_url}{endpoint}"
        max_retries = 3
        
        for attempt in range(max_retries):
            self._rate_limit_wait()
            
            try:
                response = self.client.get(url, params=params)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    wait_time = (2 ** attempt) * 2
                    print(f"[WARN] Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"[WARN] HTTP {response.status_code}: {response.text[:100]}")
                    return {}
            except Exception as e:
                print(f"[ERROR] Request failed: {e}")
                if attempt == max_retries - 1:
                    return {}
                time.sleep(2 ** attempt)
        
        return {}

    def fetch_measurements(
        self,
        location_id: int,
        date_from: str,
        date_to: str,
        parameter: str = 'pm25'
    ) -> List[Dict[str, Any]]:
        """
        Fetch hourly measurements for a specific location.
        
        Args:
            location_id: OpenAQ location ID
            date_from: Start date (ISO format: YYYY-MM-DD)
            date_to: End date (ISO format: YYYY-MM-DD)
            parameter: Parameter to fetch (default: pm25)
            
        Returns:
            List of measurement records
        """
        all_results = []
        page = 1
        
        while True:
            params = {
                'location_id': location_id,
                'parameters_id': 2,  # PM2.5
                'date_from': date_from,
                'date_to': date_to,
                'limit': 1000,
                'page': page
            }
            
            response = self._make_request('/measurements', params)
            
            if not response or 'results' not in response:
                break
            
            results = response['results']
            if not results:
                break
            
            all_results.extend(results)
            
            # Check if there are more pages
            meta = response.get('meta', {})
            if page >= meta.get('pages', 1):
                break
            
            page += 1
            print(f"  [FETCH] Page {page}, total records: {len(all_results)}")
        
        return all_results

    def fetch_city_data(
        self,
        city_name: str,
        location_ids: List[int],
        date_from: str,
        date_to: str
    ) -> pd.DataFrame:
        """
        Fetch data for all locations in a city.
        
        Args:
            city_name: City name
            location_ids: List of OpenAQ location IDs
            date_from: Start date (ISO format)
            date_to: End date (ISO format)
            
        Returns:
            DataFrame with measurements
        """
        all_measurements = []
        
        print(f"\n[*] Fetching {city_name} ({len(location_ids)} locations)...")
        
        for i, location_id in enumerate(location_ids, 1):
            print(f"  [{i}/{len(location_ids)}] Location {location_id}...", end=' ')
            
            measurements = self.fetch_measurements(
                location_id=location_id,
                date_from=date_from,
                date_to=date_to
            )
            
            if measurements:
                all_measurements.extend(measurements)
                print(f"✓ {len(measurements)} records")
            else:
                print("(no data)")
        
        if not all_measurements:
            print(f"  [WARN] No data retrieved for {city_name}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = self._parse_measurements(all_measurements, city_name)
        
        print(f"  [OK] {len(df)} total records for {city_name}")
        
        return df

    def _parse_measurements(self, measurements: List[Dict], city: str) -> pd.DataFrame:
        """
        Parse raw measurements into structured DataFrame.
        
        Args:
            measurements: Raw measurement records from API
            city: City name
            
        Returns:
            Cleaned DataFrame
        """
        records = []
        
        for m in measurements:
            # Extract datetime (v3 API uses nested structure)
            dt_obj = m.get('datetime', {})
            if isinstance(dt_obj, dict):
                timestamp_utc = dt_obj.get('utc')
            else:
                timestamp_utc = dt_obj
            
            if not timestamp_utc:
                continue
            
            # Extract value and unit
            value = m.get('value')
            if value is None:
                continue
            
            records.append({
                'location_id': m.get('locationId', m.get('location_id')),
                'location_name': m.get('locationName', m.get('location', {}).get('name', 'Unknown')),
                'city': city,
                'timestamp_utc': timestamp_utc,
                'parameter': 'pm25',
                'value': float(value),
                'unit': m.get('unit', 'µg/m³'),
                'coordinates_lat': m.get('coordinates', {}).get('latitude'),
                'coordinates_lon': m.get('coordinates', {}).get('longitude')
            })
        
        df = pd.DataFrame(records)
        
        if df.empty:
            return df
        
        # Convert timestamp to datetime
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'], utc=True)
        
        # Sort by timestamp
        df = df.sort_values(['city', 'location_id', 'timestamp_utc']).reset_index(drop=True)
        
        return df

    def save_to_parquet(self, df: pd.DataFrame, output_path: Path) -> str:
        """
        Save DataFrame to Parquet file and return SHA-256 hash.
        
        Args:
            df: DataFrame to save
            output_path: Output file path
            
        Returns:
            SHA-256 hash of the file
        """
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to Parquet
        table = pa.Table.from_pandas(df)
        pq.write_table(table, output_path, compression='snappy')
        
        # Calculate SHA-256
        sha256_hash = hashlib.sha256()
        with open(output_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()

    def update_manifest(
        self,
        manifest_path: Path,
        source: str,
        query_params: str,
        output_file: Path,
        sha256: str,
        row_count: int
    ) -> None:
        """
        Update manifest.csv with file metadata.
        
        Args:
            manifest_path: Path to manifest.csv
            source: Data source name
            query_params: Query parameters used
            output_file: Path to output file
            sha256: SHA-256 hash of file
            row_count: Number of rows in file
        """
        fetch_time_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Read existing manifest or create new
        if manifest_path.exists():
            manifest_df = pd.read_csv(manifest_path)
        else:
            manifest_df = pd.DataFrame(columns=[
                'source', 'query_or_url', 'fetch_time_utc', 'sha256', 
                'licence', 'row_count', 'output_file'
            ])
        
        # Append new entry
        new_entry = pd.DataFrame([{
            'source': source,
            'query_or_url': query_params,
            'fetch_time_utc': fetch_time_utc,
            'sha256': sha256,
            'licence': 'CC-BY-4.0',
            'row_count': row_count,
            'output_file': str(output_file.relative_to(manifest_path.parent))
        }])
        
        manifest_df = pd.concat([manifest_df, new_entry], ignore_index=True)
        
        # Save manifest
        manifest_df.to_csv(manifest_path, index=False)
        print(f"[OK] Manifest updated: {manifest_path}")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()


def main():
    """Main execution: Fetch PM2.5 data for Pakistani cities."""
    
    # Initialize fetcher
    fetcher = OpenAQFetcher()
    
    # Load location IDs from audit results
    project_root = Path(__file__).parent.parent.parent
    audit_file = project_root / 'docs' / 'openaq_coverage_audit.json'
    
    if audit_file.exists():
        import json
        with open(audit_file, 'r') as f:
            audit_data = json.load(f)
        
        # Extract top 10 active locations per city (or all if fewer)
        cities_config = {}
        for city_name in ['Lahore', 'Karachi', 'Islamabad', 'Peshawar']:
            city_data = audit_data['city_breakdown'].get(city_name, {})
            coverages = city_data.get('coverages', [])
            
            # Sort by is_active (True first), then by total_hours (descending)
            active_locations = sorted(
                coverages,
                key=lambda x: (x['is_active'], x['total_hours_estimate']),
                reverse=True
            )
            
            # Take top 10 locations
            location_ids = [loc['location_id'] for loc in active_locations[:10]]
            cities_config[city_name] = location_ids
            
        print(f"[INFO] Loaded location IDs from audit file")
    else:
        # Fallback: Use default location IDs
        print(f"[WARN] Audit file not found, using default location IDs")
        cities_config = {
            'Lahore': [8664, 1894641, 4515157, 4515158, 4515159],
            'Karachi': [8668, 1894644, 4515160, 4515161, 4515162],
            'Islamabad': [8665, 1894642, 4515163, 4515164, 4515165],
            'Peshawar': [4515166, 4515167, 4515168, 4515169, 4515170]
        }
    
    # Date range: Last 2 years (meets hackathon minimum requirement)
    date_to = datetime.date.today().isoformat()
    date_from = (datetime.date.today() - datetime.timedelta(days=730)).isoformat()
    
    print("="*80)
    print("OpenAQ PM2.5 Data Fetch")
    print("="*80)
    print(f"Date range: {date_from} to {date_to}")
    print(f"Cities: {list(cities_config.keys())}")
    for city, locs in cities_config.items():
        print(f"  {city}: {len(locs)} locations")
    print("="*80)
    
    # Setup paths
    raw_data_dir = project_root / 'data' / 'raw'
    manifest_path = project_root / 'manifest.csv'
    
    # Fetch data for each city
    for city_name, location_ids in cities_config.items():
        # Fetch data
        df = fetcher.fetch_city_data(
            city_name=city_name,
            location_ids=location_ids,
            date_from=date_from,
            date_to=date_to
        )
        
        if df.empty:
            print(f"  [SKIP] No data for {city_name}")
            continue
        
        # Save to Parquet
        output_file = raw_data_dir / f"openaq_pm25_{city_name.lower()}.parquet"
        sha256 = fetcher.save_to_parquet(df, output_file)
        
        print(f"  [SAVED] {output_file}")
        print(f"  [SHA256] {sha256}")
        
        # Update manifest
        query_params = f"locations={','.join(map(str, location_ids))};date_from={date_from};date_to={date_to}"
        fetcher.update_manifest(
            manifest_path=manifest_path,
            source='OpenAQ API v3',
            query_params=query_params,
            output_file=output_file,
            sha256=sha256,
            row_count=len(df)
        )
    
    print("\n" + "="*80)
    print("[OK] Data fetch complete!")
    print(f"[MANIFEST] {manifest_path}")
    print(f"[RAW DATA] {raw_data_dir}")
    print("="*80)


if __name__ == "__main__":
    main()
