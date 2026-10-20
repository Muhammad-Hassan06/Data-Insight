"""
Test Suite: FastAPI Backend Endpoints
Location: tests/test_backend.py
Purpose: Test assertions for CORS, endpoint schemas, HTTP status codes, and error responses.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint responds with 200 OK and docs link."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "/docs" in data["docs"]


def test_health_check_returns_ok():
    """Verify health endpoint responds with 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_forecast_cities_contract():
    """Verify /api/forecast/cities returns expected candidate cities list."""
    response = client.get("/api/forecast/cities")
    assert response.status_code == 200
    cities = response.json()
    assert "Lahore" in cities
    assert "Karachi" in cities
    assert "Islamabad" in cities
    assert "Peshawar" in cities


def test_get_city_forecast_valid():
    """Verify /api/forecast/{city} returns 24 forecast points with uncertainty."""
    response = client.get("/api/forecast/Lahore")
    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "Lahore"
    assert len(data["forecasts"]) == 24
    first_pt = data["forecasts"][0]
    assert "pm25_median" in first_pt
    assert "pm25_lower" in first_pt
    assert "pm25_upper" in first_pt
    assert first_pt["pm25_lower"] <= first_pt["pm25_median"] <= first_pt["pm25_upper"]


def test_unknown_city_returns_404():
    """Verify querying an unsupported city returns HTTP 404."""
    response = client.get("/api/forecast/UnknownCity123")
    assert response.status_code == 404
    assert "not recognized" in response.json()["detail"]


def test_all_forecasts_endpoint():
    """Verify /api/forecast/all/latest returns forecasts for all 4 cities."""
    response = client.get("/api/forecast/all/latest")
    assert response.status_code == 200
    data = response.json()
    assert len(data["forecasts"]) == 4


def test_quality_freshness_endpoint():
    """Verify /api/quality/freshness returns pm25 and weather status."""
    response = client.get("/api/quality/freshness")
    assert response.status_code == 200
    data = response.json()
    assert "pm25" in data
    assert "weather" in data
    assert data["pm25"]["status"] in ["fresh", "warning", "stale"]
    assert data["weather"]["status"] in ["fresh", "warning", "stale"]


def test_quality_stats_endpoint():
    """Verify /api/quality/stats returns warehouse volume metrics."""
    response = client.get("/api/quality/stats")
    assert response.status_code == 200
    data = response.json()
    assert "cleaned" in data
    assert "processed" in data
    assert data["cleaned"]["cities"] == 4
    assert data["processed"]["gold_rows"] > 0


def test_quality_issues_endpoint():
    """Verify /api/quality/issues returns audit logs."""
    response = client.get("/api/quality/issues?limit=10")
    assert response.status_code == 200
    issues = response.json()
    assert isinstance(issues, list)


def test_agent_corpus_info_endpoint():
    """Verify /api/agent/corpus-info returns document counts."""
    response = client.get("/api/agent/corpus-info")
    assert response.status_code == 200
    data = response.json()
    assert data["total_chunks"] >= 200
    assert "WHO Air Quality Guidelines" in data["sources"]


def test_agent_ask_valid_query():
    """Verify /api/agent/ask returns cited answer with data point grounding."""
    response = client.post("/api/agent/ask", json={"question": "What is the WHO PM2.5 air quality guideline?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["answer"]) > 20
    assert len(data["citations"]) > 0


def test_agent_ask_requires_valid_question():
    """Verify /api/agent/ask validates request payload with Pydantic."""
    # Empty or too short question should fail with 422 Unprocessable Entity
    response = client.post("/api/agent/ask", json={"question": "a"})
    assert response.status_code == 422


def test_agent_ask_off_topic_guardrail():
    """Verify off-topic questions return the rule-mandated 'I don't know' response."""
    response = client.post("/api/agent/ask", json={"question": "What is the capital of France?"})
    assert response.status_code == 200
    data = response.json()
    assert "I don't know" in data["answer"]
    assert data["citations"] == []
