"""
Module: openaq_coverage
Location: src/fetch/openaq_coverage.py
Purpose: Query OpenAQ API v3 to audit sensor stations, PM2.5 availability,
         date ranges, and licences for candidate Pakistani cities.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import datetime
import time
import os
import sys
import httpx
from dotenv import load_dotenv


@dataclass(frozen=True)
class SensorCoverage:
    city: str
    location_id: int
    location_name: str
    parameter: str
    first_datetime_utc: Optional[datetime.datetime]
    last_datetime_utc: Optional[datetime.datetime]
    total_hours_estimate: int
    licence_name: str
    is_active: bool


class OpenAQCoverageAuditor:
    """Audits OpenAQ v3 API coverage for target geographic areas."""

    # Pakistani cities with their approximate coordinates for bounding box queries
    # Radius in km (API max is 25km = 25000 meters)
    CITY_COORDINATES = {
        'Lahore': {'lat': 31.5497, 'lon': 74.3436, 'radius': 25},
        'Karachi': {'lat': 24.8607, 'lon': 67.0011, 'radius': 25},
        'Islamabad': {'lat': 33.6844, 'lon': 73.0479, 'radius': 25},
        'Peshawar': {'lat': 34.0151, 'lon': 71.5249, 'radius': 25},
    }

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.openaq.org/v3") -> None:
        """
        Initialize the auditor.
        
        Args:
            api_key: Optional OpenAQ API key loaded from .env.
            base_url: Base endpoint URL for OpenAQ v3.
        """
        self.base_url = base_url.rstrip('/')
        # If no key passed explicitly, try loading from environment
        self.api_key = api_key or os.getenv('OPENAQ_API_KEY')
        
        # Setup HTTP client with timeout and rate limiting consideration
        self.client = httpx.Client(
            timeout=30.0,
            headers={'X-API-Key': self.api_key} if self.api_key else {}
        )
        
        # Rate limiting: OpenAQ free tier typically 60 req/min
        self.min_request_interval = 1.0  # 1 second between requests to be safe
        self.last_request_time = 0.0

    def _rate_limit_wait(self) -> None:
        """Enforce minimum interval between API requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """
        Make HTTP request with exponential backoff on rate limit errors.
        
        Args:
            endpoint: API endpoint (e.g., '/locations')
            params: Query parameters
            max_retries: Maximum retry attempts on 429 errors
            
        Returns:
            Parsed JSON response
        """
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(max_retries):
            self._rate_limit_wait()
            
            try:
                response = self.client.get(url, params=params)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # Rate limited - exponential backoff
                    wait_time = (2 ** attempt) * 2  # 2, 4, 8 seconds
                    print(f"[WARNING] Rate limited (429). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    print(f"[WARNING] HTTP {response.status_code}: {response.text[:200]}")
                    return {}
                    
            except Exception as e:
                print(f"[WARNING] Request error: {e}")
                if attempt == max_retries - 1:
                    return {}
                time.sleep(2 ** attempt)
        
        return {}

    def fetch_locations_by_city(self, country_code: str, city_name: str) -> List[Dict[str, Any]]:
        """
        Query OpenAQ locations endpoint for a specific city.
        
        Args:
            country_code: ISO country code (e.g., 'PK' for Pakistan)
            city_name: Target city name
            
        Returns:
            List of location records from API
        """
        if city_name not in self.CITY_COORDINATES:
            print(f"[WARNING] No coordinates defined for {city_name}")
            return []
        
        coords = self.CITY_COORDINATES[city_name]
        
        # Build query parameters for locations endpoint
        # OpenAQ v3 API - simplified query for Pakistan locations with PM2.5
        params = {
            'limit': 1000,
            'page': 1,
            'country_id': 168,  # Pakistan country ID
            'radius': coords['radius'] * 1000,  # Convert km to meters (max 25000)
            'coordinates': f"{coords['lat']},{coords['lon']}"
        }
        
        print(f"[SEARCH] Querying locations near {city_name} ({coords['lat']}, {coords['lon']}) within {coords['radius']}km...")
        
        response_data = self._make_request('/locations', params)
        
        if not response_data or 'results' not in response_data:
            print(f"[WARNING] No results found for {city_name}")
            return []
        
        locations = response_data['results']
        print(f"[OK] Found {len(locations)} locations near {city_name}")
        
        return locations

    def parse_sensor_metadata(self, location_record: Dict[str, Any], city: str) -> List[SensorCoverage]:
        """
        Extract PM2.5 sensor coverage details from a location record.

        In OpenAQ v3, the actual datetime range (datetimeFirst / datetimeLast) sits at
        the TOP LEVEL of the location record, NOT inside the sensor object.
        Each value is a dict: {"utc": "...", "local": "..."}.
        Sensors only carry id, name, and parameter metadata.

        Args:
            location_record: Raw location data from OpenAQ API
            city: City name for tracking

        Returns:
            List of SensorCoverage objects (one per PM2.5 sensor found)
        """
        coverages = []

        location_id   = location_record.get('id', 0)
        location_name = location_record.get('name', 'Unknown')

        # ── datetime range is at LOCATION level, not sensor level ──────────────
        def _parse_dt(dt_field: Any) -> Optional[datetime.datetime]:
            """Extract UTC datetime from {"utc": "...", "local": "..."} or plain string."""
            if not dt_field:
                return None
            raw = dt_field.get('utc') if isinstance(dt_field, dict) else dt_field
            if not raw:
                return None
            try:
                return datetime.datetime.fromisoformat(raw.replace('Z', '+00:00'))
            except Exception:
                return None

        first_dt = _parse_dt(location_record.get('datetimeFirst'))
        last_dt  = _parse_dt(location_record.get('datetimeLast'))

        # ── license: v3 uses top-level "licenses" list (may be null) ───────────
        licence_name = 'VERIFY: check provider licence on openaq.org'
        licenses = location_record.get('licenses')          # list or None
        if licenses:
            # take the first entry; it may be a dict {"name": "CC-BY-4.0"} or a string
            first_lic = licenses[0]
            if isinstance(first_lic, dict):
                licence_name = first_lic.get('name', licence_name)
            else:
                licence_name = str(first_lic)
        else:
            # fallback: check provider sub-object
            provider = location_record.get('provider', {}) or {}
            lic = provider.get('license') or provider.get('licence')
            if lic:
                licence_name = lic.get('name', str(lic)) if isinstance(lic, dict) else str(lic)

        # ── iterate sensors to find PM2.5 ──────────────────────────────────────
        sensors = location_record.get('sensors', [])

        for sensor in sensors:
            param_obj  = sensor.get('parameter', {}) or {}
            param_name = ''

            if isinstance(param_obj, dict):
                # prefer the canonical 'name' field; id==2 is PM2.5 in OpenAQ v3
                param_name = param_obj.get('name', '').lower()
                if not param_name and param_obj.get('id') == 2:
                    param_name = 'pm25'
            elif isinstance(param_obj, str):
                param_name = param_obj.lower()

            if param_name not in ('pm25', 'pm2.5', 'pm 2.5'):
                continue

            # ── totals and active flag use location-level datetimes ────────────
            total_hours = 0
            if first_dt and last_dt:
                total_hours = int((last_dt - first_dt).total_seconds() / 3600)

            is_active = False
            if last_dt:
                age_hours = (
                    datetime.datetime.now(datetime.timezone.utc) - last_dt
                ).total_seconds() / 3600
                is_active = age_hours <= 72

            coverages.append(SensorCoverage(
                city=city,
                location_id=location_id,
                location_name=location_name,
                parameter='pm25',
                first_datetime_utc=first_dt,
                last_datetime_utc=last_dt,
                total_hours_estimate=total_hours,
                licence_name=str(licence_name),
                is_active=is_active,
            ))

        return coverages

    def generate_city_summary(self, target_cities: List[str], country_code: str = 'PK') -> Dict[str, Any]:
        """
        Generate aggregate audit report across all target Pakistani cities.
        
        Args:
            target_cities: List of city names to audit
            country_code: ISO country code (default: 'PK' for Pakistan)
            
        Returns:
            Comprehensive audit dictionary with coverage statistics
        """
        all_coverages = []
        city_stats = {}
        
        print(f"\n{'='*80}")
        print(f"OpenAQ PM2.5 Coverage Audit for Pakistan")
        print(f"{'='*80}\n")
        
        for city in target_cities:
            print(f"\n[*] Auditing {city}...")
            
            locations = self.fetch_locations_by_city(country_code, city)
            
            city_coverages = []
            for location in locations:
                coverages = self.parse_sensor_metadata(location, city)
                city_coverages.extend(coverages)
            
            all_coverages.extend(city_coverages)
            
            # Calculate city-level stats
            if city_coverages:
                active_count = sum(1 for c in city_coverages if c.is_active)
                total_hours = sum(c.total_hours_estimate for c in city_coverages)
                earliest = min((c.first_datetime_utc for c in city_coverages if c.first_datetime_utc), default=None)
                latest = max((c.last_datetime_utc for c in city_coverages if c.last_datetime_utc), default=None)
                
                city_stats[city] = {
                    'total_stations': len(city_coverages),
                    'active_stations': active_count,
                    'total_hours': total_hours,
                    'earliest_record': earliest,
                    'latest_record': latest,
                    'coverages': city_coverages
                }
                
                print(f"  * Stations: {len(city_coverages)} ({active_count} active)")
                print(f"  * Total hours: {total_hours:,}")
                if earliest and latest:
                    years = (latest - earliest).days / 365.25
                    print(f"  * Time span: {years:.1f} years ({earliest.date()} to {latest.date()})")
            else:
                print(f"  [WARNING] No PM2.5 sensors found for {city}")
                city_stats[city] = {
                    'total_stations': 0,
                    'active_stations': 0,
                    'total_hours': 0,
                    'earliest_record': None,
                    'latest_record': None,
                    'coverages': []
                }
        
        # Aggregate statistics
        total_stations = sum(stats['total_stations'] for stats in city_stats.values())
        total_active = sum(stats['active_stations'] for stats in city_stats.values())
        total_hours = sum(stats['total_hours'] for stats in city_stats.values())
        
        all_dates = [c.first_datetime_utc for c in all_coverages if c.first_datetime_utc] + \
                    [c.last_datetime_utc for c in all_coverages if c.last_datetime_utc]
        
        overall_earliest = min(all_dates) if all_dates else None
        overall_latest = max(all_dates) if all_dates else None
        
        # Validation against requirements
        meets_volume = total_hours >= 50000
        meets_time_span = False
        if overall_earliest and overall_latest:
            years_span = (overall_latest - overall_earliest).days / 365.25
            meets_time_span = years_span >= 2.0
        
        summary = {
            'audit_timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'country_code': country_code,
            'cities_audited': target_cities,
            'total_stations': total_stations,
            'active_stations': total_active,
            'total_hours_all_stations': total_hours,
            'earliest_record': overall_earliest.isoformat() if overall_earliest else None,
            'latest_record': overall_latest.isoformat() if overall_latest else None,
            'time_span_years': (overall_latest - overall_earliest).days / 365.25 if overall_earliest and overall_latest else 0,
            'meets_minimum_volume': meets_volume,
            'meets_minimum_timespan': meets_time_span,
            'city_breakdown': city_stats,
            'all_coverages': all_coverages
        }
        
        # Print summary
        self._print_summary(summary)
        
        return summary

    def _print_summary(self, summary: Dict[str, Any]) -> None:
        """Print formatted summary to console."""
        print(f"\n{'='*80}")
        print(f"AUDIT SUMMARY")
        print(f"{'='*80}\n")
        
        print(f"Total Stations Found: {summary['total_stations']}")
        print(f"Active Stations: {summary['active_stations']}")
        print(f"Total Hours (all stations): {summary['total_hours_all_stations']:,}")
        print(f"Time Span: {summary['time_span_years']:.1f} years")
        
        if summary['earliest_record'] and summary['latest_record']:
            print(f"Date Range: {summary['earliest_record'][:10]} to {summary['latest_record'][:10]}")
        
        print(f"\nMinimum Requirements Check:")
        print(f"  * >= 50,000 hours: {'PASS' if summary['meets_minimum_volume'] else 'FAIL'} ({summary['total_hours_all_stations']:,} hours)")
        print(f"  * >= 2 years span: {'PASS' if summary['meets_minimum_timespan'] else 'FAIL'} ({summary['time_span_years']:.1f} years)")
        
        print(f"\n{'='*80}\n")

    def export_to_json(self, summary: Dict[str, Any], output_path: str) -> None:
        """Export audit results to JSON file."""
        import json
        
        # Convert datetime objects to ISO strings for JSON serialization
        def datetime_converter(obj):
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            elif isinstance(obj, SensorCoverage):
                return asdict(obj)
            return obj
        
        # Prepare serializable summary
        export_data = {
            k: v for k, v in summary.items() 
            if k != 'all_coverages'  # Exclude raw coverages from main export
        }
        
        # Add coverages as serializable list
        export_data['coverages_detail'] = [
            {
                'city': c.city,
                'location_id': c.location_id,
                'location_name': c.location_name,
                'parameter': c.parameter,
                'first_datetime_utc': c.first_datetime_utc.isoformat() if c.first_datetime_utc else None,
                'last_datetime_utc': c.last_datetime_utc.isoformat() if c.last_datetime_utc else None,
                'total_hours_estimate': c.total_hours_estimate,
                'licence_name': c.licence_name,
                'is_active': c.is_active
            }
            for c in summary.get('all_coverages', [])
        ]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=datetime_converter)
        
        print(f"[OK] Audit results exported to: {output_path}")

    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()


def main():
    """Main execution entry point."""
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv('OPENAQ_API_KEY')
    if not api_key:
        print("[WARNING] OPENAQ_API_KEY not found in .env file")
        print("   Proceeding without API key (rate limits may apply)")
    
    # Instantiate auditor
    auditor = OpenAQCoverageAuditor(api_key=api_key)
    
    # Target Pakistani cities for PM2.5 coverage audit
    target_cities = ['Lahore', 'Karachi', 'Islamabad', 'Peshawar']
    
    # Run audit
    summary = auditor.generate_city_summary(target_cities, country_code='PK')
    
    # Export results
    output_path = 'docs/openaq_coverage_audit.json'
    os.makedirs('docs', exist_ok=True)
    auditor.export_to_json(summary, output_path)
    
    print(f"\n[OK] Coverage audit complete!")
    print(f"[SAVED] Detailed results saved to: {output_path}")
    print(f"\nNext steps:")
    print(f"  1. Review the audit results")
    print(f"  2. Update DATASET_DECLARATION.md with coverage details")
    print(f"  3. Proceed to implement data fetching (Phase 1B)")


if __name__ == "__main__":
    main()
