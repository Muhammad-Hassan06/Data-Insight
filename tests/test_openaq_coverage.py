"""
Test suite for OpenAQ coverage audit module.
Location: tests/test_openaq_coverage.py
"""

import pytest
import datetime
from src.fetch.openaq_coverage import OpenAQCoverageAuditor, SensorCoverage


def test_auditor_instantiation():
    """Test that the auditor can be created without errors."""
    auditor = OpenAQCoverageAuditor(api_key=None)
    assert auditor is not None
    assert auditor.base_url == "https://api.openaq.org/v3"
    assert auditor.client is not None


def test_auditor_with_api_key():
    """Test auditor initialization with API key."""
    test_key = "test_api_key_12345"
    auditor = OpenAQCoverageAuditor(api_key=test_key)
    assert auditor.api_key == test_key
    assert 'X-API-Key' in auditor.client.headers


def test_sensor_coverage_dataclass():
    """Test SensorCoverage dataclass creation."""
    coverage = SensorCoverage(
        city="Lahore",
        location_id=12345,
        location_name="Test Station",
        parameter="pm25",
        first_datetime_utc=datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
        last_datetime_utc=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        total_hours_estimate=17520,
        licence_name="CC-BY-4.0",
        is_active=True
    )
    assert coverage.city == "Lahore"
    assert coverage.total_hours_estimate == 17520
    assert coverage.is_active is True


def test_parse_sensor_metadata_with_pm25():
    """Test parsing location record containing PM2.5 sensor."""
    auditor = OpenAQCoverageAuditor()
    
    location_record = {
        'id': 12345,
        'name': 'Test Location Lahore',
        'sensors': [
            {
                'parameter': {'name': 'pm25'},
                'datetimeFirst': '2022-01-01T00:00:00Z',
                'datetimeLast': '2024-10-19T00:00:00Z',
            }
        ],
        'provider': {
            'license': 'CC-BY-4.0'
        }
    }
    
    coverages = auditor.parse_sensor_metadata(location_record, 'Lahore')
    
    assert len(coverages) == 1
    assert coverages[0].city == 'Lahore'
    assert coverages[0].parameter == 'pm25'
    assert coverages[0].location_id == 12345


def test_parse_sensor_metadata_filters_non_pm25():
    """Test that non-PM2.5 parameters are filtered out."""
    auditor = OpenAQCoverageAuditor()
    
    location_record = {
        'id': 12345,
        'name': 'Test Location',
        'sensors': [
            {
                'parameter': {'name': 'no2'},
                'datetimeFirst': '2022-01-01T00:00:00Z',
                'datetimeLast': '2024-10-19T00:00:00Z',
            },
            {
                'parameter': {'name': 'o3'},
                'datetimeFirst': '2022-01-01T00:00:00Z',
                'datetimeLast': '2024-10-19T00:00:00Z',
            }
        ],
        'provider': {
            'license': 'Open Data'
        }
    }
    
    coverages = auditor.parse_sensor_metadata(location_record, 'Karachi')
    
    assert len(coverages) == 0


def test_parse_sensor_metadata_calculates_hours():
    """Test total hours calculation using location-level datetime fields (v3 API structure)."""
    auditor = OpenAQCoverageAuditor()
    
    location_record = {
        'id': 12345,
        'name': 'Test Station',
        # datetimeFirst/Last are at location level in OpenAQ v3, as {"utc": ..., "local": ...}
        'datetimeFirst': {'utc': '2022-01-01T00:00:00Z', 'local': '2022-01-01T05:00:00+05:00'},
        'datetimeLast':  {'utc': '2022-01-02T00:00:00Z', 'local': '2022-01-02T05:00:00+05:00'},
        'sensors': [
            {
                'id': 1,
                'name': 'pm25 ug/m3',
                'parameter': {'id': 2, 'name': 'pm25', 'units': 'ug/m3'}
            }
        ],
        'licenses': None,
        'provider': {'license': 'Open'}
    }
    
    coverages = auditor.parse_sensor_metadata(location_record, 'Test City')
    
    assert len(coverages) == 1
    assert coverages[0].total_hours_estimate == 24


def test_city_coordinates_defined():
    """Test that Pakistani city coordinates are defined."""
    auditor = OpenAQCoverageAuditor()
    
    assert 'Lahore' in auditor.CITY_COORDINATES
    assert 'Karachi' in auditor.CITY_COORDINATES
    assert 'Islamabad' in auditor.CITY_COORDINATES
    assert 'Peshawar' in auditor.CITY_COORDINATES
    
    # Check coordinate structure
    lahore = auditor.CITY_COORDINATES['Lahore']
    assert 'lat' in lahore
    assert 'lon' in lahore
    assert 'radius' in lahore


def test_rate_limit_wait():
    """Test rate limiting mechanism."""
    import time
    auditor = OpenAQCoverageAuditor()
    
    start_time = time.time()
    auditor._rate_limit_wait()
    auditor._rate_limit_wait()
    elapsed = time.time() - start_time
    
    # Should have waited at least the minimum interval
    assert elapsed >= auditor.min_request_interval


def test_dormant_station_flagged_inactive():
    """Verify that a station inactive for > 72 hours is marked is_active=False."""
    auditor = OpenAQCoverageAuditor()
    
    # Station with last update > 72 hours ago
    old_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=100)).isoformat()
    
    location_record = {
        'id': 99999,
        'name': 'Dormant Station',
        'sensors': [
            {
                'parameter': {'name': 'pm25'},
                'datetimeFirst': '2022-01-01T00:00:00Z',
                'datetimeLast': old_date,
            }
        ],
        'provider': {'license': 'Open'}
    }
    
    coverages = auditor.parse_sensor_metadata(location_record, 'Test City')
    
    assert len(coverages) == 1
    assert coverages[0].is_active is False


def test_missing_licence_flagged_for_verification():
    """Verify that absent licence explicitly alerts team to verify provider terms."""
    auditor = OpenAQCoverageAuditor()
    
    location_record = {
        'id': 12345,
        'name': 'Station Without License',
        'sensors': [
            {
                'parameter': {'name': 'pm25'},
                'datetimeFirst': '2022-01-01T00:00:00Z',
                'datetimeLast': '2024-10-19T00:00:00Z',
            }
        ],
        'provider': {}  # No license info
    }
    
    coverages = auditor.parse_sensor_metadata(location_record, 'Test City')
    
    assert len(coverages) == 1
    assert 'VERIFY' in coverages[0].licence_name
