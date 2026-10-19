"""
Module: fetch_openaq
Location: src/fetch/fetch_openaq.py
Purpose: Fetch hourly PM2.5 measurements from OpenAQ API v3 for Pakistani cities.

OpenAQ v3 endpoint chain used:
  1. GET /v3/locations/{location_id}/sensors  → resolve location → pm25 sensor IDs
  2. GET /v3/sensors/{sensor_id}/hours        → fetch precomputed hourly averages
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

    BASE_URL = "https://api.openaq.org/v3"
    PM25_PARAMETER_NAMES = {"pm25", "pm2.5"}  # both spellings appear in the API

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the fetcher.

        Args:
            api_key: OpenAQ API key (loads from OPENAQ_API_KEY env var if not provided)
        """
        load_dotenv()
        self.api_key = api_key or os.getenv("OPENAQ_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAQ_API_KEY not found in environment")

        self.client = httpx.Client(
            timeout=60.0,
            headers={"X-API-Key": self.api_key},
        )
        self._min_interval = 1.0  # 60 req/min rate limit
        self._last_request_at = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_at = time.time()

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        GET request with rate limiting and simple retry logic.

        Returns the parsed JSON body on HTTP 200, or {} on any failure.
        """
        url = f"{self.BASE_URL}{endpoint}"
        max_retries = 3

        for attempt in range(max_retries):
            self._rate_limit()
            try:
                resp = self.client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 429:
                    wait = (2 ** attempt) * 2
                    print(f"    [WARN] Rate-limited. Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                # 404, 500, etc. – log briefly and stop retrying
                print(f"    [WARN] HTTP {resp.status_code}: {resp.text[:120]}")
                return {}
            except Exception as exc:
                print(f"    [ERROR] Request failed: {exc}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        return {}

    # ------------------------------------------------------------------
    # Step 1: Resolve pm25 sensor IDs for a location
    # ------------------------------------------------------------------

    def get_pm25_sensor_ids(self, location_id: int) -> List[int]:
        """
        Return all pm25 sensor IDs that belong to *location_id*.

        Calls GET /v3/locations/{location_id}/sensors and filters by parameter
        name. Returns an empty list if the location has no pm25 sensors or if
        the request fails.
        """
        data = self._get(f"/locations/{location_id}/sensors", {})
        if not data or "results" not in data:
            return []

        sensor_ids = []
        for sensor in data["results"]:
            param = sensor.get("parameter", {})
            param_name = param.get("name", "").lower()
            if param_name in self.PM25_PARAMETER_NAMES:
                sensor_ids.append(sensor["id"])

        return sensor_ids

    # ------------------------------------------------------------------
    # Step 2: Fetch hourly measurements for a sensor
    # ------------------------------------------------------------------

    def fetch_sensor_hours(
        self,
        sensor_id: int,
        date_from: str,
        date_to: str,
    ) -> List[Dict[str, Any]]:
        """
        Fetch precomputed hourly averages for *sensor_id* over the given range.

        Calls GET /v3/sensors/{sensor_id}/hours and pages through all results.

        Args:
            sensor_id: OpenAQ sensor ID
            date_from: ISO date string, e.g. "2024-10-19"
            date_to:   ISO date string, e.g. "2026-10-19"

        Returns:
            List of raw result dicts from the API.
        """
        all_results: List[Dict[str, Any]] = []
        page = 1
        PAGE_SIZE = 1000

        while True:
            params: Dict[str, Any] = {
                "datetime_from": date_from,
                "datetime_to": date_to,
                "limit": PAGE_SIZE,
                "page": page,
            }
            data = self._get(f"/sensors/{sensor_id}/hours", params)

            if not data or "results" not in data:
                break

            batch = data["results"]
            if not batch:
                break

            all_results.extend(batch)

            # Only stop when the API returns fewer items than we asked for —
            # that is the definitive signal that we've reached the last page.
            # A full batch of PAGE_SIZE always means more pages may exist.
            if len(batch) < PAGE_SIZE:
                break

            page += 1
            if page % 5 == 0:
                print(f"\n      [page {page}, {len(all_results)} records so far]", end=" ", flush=True)

        return all_results

    # ------------------------------------------------------------------
    # Step 3: Fetch all data for a city
    # ------------------------------------------------------------------

    def fetch_city_data(
        self,
        city_name: str,
        location_ids: List[int],
        date_from: str,
        date_to: str,
    ) -> pd.DataFrame:
        """
        Fetch hourly PM2.5 measurements for every location in a city.

        For each location:
          1. Resolve pm25 sensor IDs via /locations/{id}/sensors
          2. Pull hourly data for each sensor via /sensors/{id}/hours

        Returns a consolidated DataFrame or an empty DataFrame if no data.
        """
        all_records: List[Dict[str, Any]] = []

        print(f"\n[*] Fetching {city_name} ({len(location_ids)} locations)...")

        for i, location_id in enumerate(location_ids, 1):
            print(f"  [{i}/{len(location_ids)}] Location {location_id}...", end=" ", flush=True)

            # Resolve pm25 sensor IDs
            sensor_ids = self.get_pm25_sensor_ids(location_id)
            if not sensor_ids:
                print("(no pm25 sensors)")
                continue

            loc_total = 0
            for sensor_id in sensor_ids:
                hourly = self.fetch_sensor_hours(sensor_id, date_from, date_to)
                if hourly:
                    # Tag each record with its location / sensor context
                    for rec in hourly:
                        rec["_location_id"] = location_id
                        rec["_sensor_id"] = sensor_id
                        rec["_city"] = city_name
                    all_records.extend(hourly)
                    loc_total += len(hourly)

            if loc_total:
                print(f"✓ {loc_total} records")
            else:
                print("(no data)")

        if not all_records:
            print(f"  [WARN] No data retrieved for {city_name}")
            return pd.DataFrame()

        df = self._parse_hourly_records(all_records)
        print(f"  [OK] {len(df)} total records for {city_name}")
        return df

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_hourly_records(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Convert raw /sensors/{id}/hours result dicts into a clean DataFrame.

        The v3 hourly response shape:
            {
              "value": 42.1,
              "parameter": {"id": 2, "name": "pm25", "units": "µg/m³", ...},
              "period": {"label": "hour", "interval": "01:00:00",
                         "datetimeFrom": {"utc": "...", "local": "..."},
                         "datetimeTo":   {"utc": "...", "local": "..."}},
              "coordinates": {"latitude": ..., "longitude": ...},
              ...
              "_location_id": <int>,
              "_sensor_id":   <int>,
              "_city":        <str>
            }
        """
        rows = []
        for rec in records:
            value = rec.get("value")
            if value is None:
                continue

            # Timestamp: use the start of the hour period
            period = rec.get("period", {})
            dt_from = period.get("datetimeFrom", {})
            if isinstance(dt_from, dict):
                timestamp_utc = dt_from.get("utc")
            else:
                timestamp_utc = dt_from

            if not timestamp_utc:
                continue

            coords = rec.get("coordinates") or {}
            param = rec.get("parameter", {})

            rows.append({
                "location_id":     rec.get("_location_id"),
                "sensor_id":       rec.get("_sensor_id"),
                "city":            rec.get("_city"),
                "timestamp_utc":   timestamp_utc,
                "parameter":       param.get("name", "pm25"),
                "value":           float(value),
                "unit":            param.get("units", "µg/m³"),
                "coordinates_lat": coords.get("latitude"),
                "coordinates_lon": coords.get("longitude"),
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        df = df.sort_values(["city", "location_id", "sensor_id", "timestamp_utc"]).reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # Persistence helpers (unchanged from original)
    # ------------------------------------------------------------------

    def save_to_parquet(self, df: pd.DataFrame, output_path: Path) -> str:
        """Save DataFrame to Parquet (snappy) and return its SHA-256 hash."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pandas(df)
        pq.write_table(table, output_path, compression="snappy")

        sha256 = hashlib.sha256()
        with open(output_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def update_manifest(
        self,
        manifest_path: Path,
        source: str,
        query_params: str,
        output_file: Path,
        sha256: str,
        row_count: int,
    ) -> None:
        """Append an entry to manifest.csv."""
        fetch_time_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if manifest_path.exists():
            manifest_df = pd.read_csv(manifest_path)
        else:
            manifest_df = pd.DataFrame(columns=[
                "source", "query_or_url", "fetch_time_utc",
                "sha256", "licence", "row_count", "output_file",
            ])

        new_entry = pd.DataFrame([{
            "source":         source,
            "query_or_url":   query_params,
            "fetch_time_utc": fetch_time_utc,
            "sha256":         sha256,
            "licence":        "CC-BY-4.0",
            "row_count":      row_count,
            "output_file":    str(output_file.relative_to(manifest_path.parent)),
        }])

        manifest_df = pd.concat([manifest_df, new_entry], ignore_index=True)
        manifest_df.to_csv(manifest_path, index=False)
        print(f"  [MANIFEST] Updated: {manifest_path}")

    def __del__(self):
        if hasattr(self, "client"):
            self.client.close()


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    """Fetch PM2.5 hourly data for 4 Pakistani cities and save as Parquet."""

    fetcher = OpenAQFetcher()

    # ---- Load location IDs from prior audit ----
    project_root = Path(__file__).parent.parent.parent
    audit_file = project_root / "docs" / "openaq_coverage_audit.json"

    if audit_file.exists():
        import json
        with open(audit_file, "r") as fh:
            audit_data = json.load(fh)

        cities_config: Dict[str, List[int]] = {}
        for city in ["Lahore", "Karachi", "Islamabad", "Peshawar"]:
            city_data = audit_data["city_breakdown"].get(city, {})
            coverages = city_data.get("coverages", [])

            # Prefer active stations; within each group sort by most hours
            sorted_locs = sorted(
                coverages,
                key=lambda x: (x["is_active"], x["total_hours_estimate"]),
                reverse=True,
            )
            cities_config[city] = [loc["location_id"] for loc in sorted_locs[:10]]

        print("[INFO] Loaded location IDs from audit file")
    else:
        print("[WARN] Audit file not found, using fallback location IDs")
        cities_config = {
            "Lahore":    [8664, 1894641, 4515157, 4527035, 4527173,
                          4527306, 4527402, 4554729, 4555745, 4557686],
            "Karachi":   [8668, 1894644, 4791924, 4837113, 4837117,
                          4838712, 4847173, 4840233, 4932783, 4985886],
            "Islamabad": [8665, 1894642, 4515644, 4554236, 4556719,
                          4565419, 4565932, 4566426, 4567363, 4567364],
            "Peshawar":  [4600078, 4605118, 4607067, 4608423, 4608419,
                          4609262, 4609354, 4609307, 4952332, 6135308],
        }

    # ---- Date range: last 2 years ----
    date_to   = datetime.date.today().isoformat()
    date_from = (datetime.date.today() - datetime.timedelta(days=730)).isoformat()

    print("=" * 72)
    print("OpenAQ PM2.5 Data Fetch  (v3 API — sensor-hours endpoint)")
    print("=" * 72)
    print(f"Date range : {date_from}  →  {date_to}")
    print(f"Cities     : {list(cities_config.keys())}")
    for city, locs in cities_config.items():
        print(f"  {city}: {len(locs)} locations")
    print("=" * 72)

    raw_data_dir  = project_root / "data" / "raw"
    manifest_path = project_root / "manifest.csv"

    for city_name, location_ids in cities_config.items():
        df = fetcher.fetch_city_data(
            city_name=city_name,
            location_ids=location_ids,
            date_from=date_from,
            date_to=date_to,
        )

        if df.empty:
            print(f"  [SKIP] No data for {city_name}")
            continue

        output_file = raw_data_dir / f"openaq_pm25_{city_name.lower()}.parquet"
        sha256 = fetcher.save_to_parquet(df, output_file)

        print(f"  [SAVED]  {output_file}")
        print(f"  [SHA256] {sha256}")

        query_params = (
            f"locations={','.join(map(str, location_ids))};"
            f"date_from={date_from};date_to={date_to}"
        )
        fetcher.update_manifest(
            manifest_path=manifest_path,
            source="OpenAQ API v3 /sensors/{id}/hours",
            query_params=query_params,
            output_file=output_file,
            sha256=sha256,
            row_count=len(df),
        )

    print("\n" + "=" * 72)
    print("[OK] Data fetch complete!")
    print(f"[MANIFEST] {manifest_path}")
    print(f"[RAW DATA] {raw_data_dir}")
    print("=" * 72)


if __name__ == "__main__":
    main()
