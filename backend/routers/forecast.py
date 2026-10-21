"""
Router: forecast
Location: backend/routers/forecast.py
Purpose: Serve hourly 24-hour ahead PM2.5 forecasts with prediction intervals for Pakistani cities.
"""

from typing import List
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
import pandas as pd
from backend.models.schemas import CityForecastResponse, AllForecastsResponse, ForecastItem

router = APIRouter(prefix="/forecast", tags=["Forecast"])

CITIES = ["Lahore", "Karachi", "Islamabad", "Peshawar"]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREDICTIONS_DIR = PROJECT_ROOT / "predictions"
PREDICTIONS_PATH = PREDICTIONS_DIR / "latest_forecast.parquet"


def _get_forecast_dataframe() -> pd.DataFrame:
    """Read the latest forecast dataframe from trained models."""
    if not PREDICTIONS_PATH.exists():
        raise FileNotFoundError(
            f"Forecast file not found at {PREDICTIONS_PATH}. "
            "Run the hourly pipeline first: python -m src.flows.hourly_pipeline"
        )
    try:
        return pd.read_parquet(PREDICTIONS_PATH)
    except Exception as e:
        raise RuntimeError(f"Failed to load forecast data: {e}")


@router.get("/cities", response_model=List[str])
async def get_cities() -> List[str]:
    """Return the list of monitored Pakistani cities."""
    return CITIES


@router.get("/{city}", response_model=CityForecastResponse)
async def get_city_forecast(city: str) -> CityForecastResponse:
    """
    Retrieve latest 24-hour prediction curve for a specific city.
    
    Args:
        city: City name (Lahore, Karachi, Islamabad, or Peshawar)
        
    Returns:
        Structured 24h predictions with 84% prediction intervals.
    """
    normalized_city = city.strip().title()
    if normalized_city not in CITIES:
        raise HTTPException(
            status_code=404,
            detail=f"City '{city}' not recognized. Supported cities: {', '.join(CITIES)}",
        )

    df = _get_forecast_dataframe()
    city_data = df[df["city"] == normalized_city].sort_values("forecast_hour")

    if city_data.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No forecast data available for {normalized_city}. Run the pipeline to generate forecasts."
        )

    forecast_items: List[ForecastItem] = []
    for _, row in city_data.iterrows():
        ts = str(row["timestamp"])
        forecast_items.append(
            ForecastItem(
                timestamp=ts,
                forecast_hour=int(row["forecast_hour"]),
                pm25_median=float(row["pm25_median"]),
                pm25_lower=float(row["pm25_lower"]),
                pm25_upper=float(row["pm25_upper"]),
            )
        )

    generated_at = str(city_data.iloc[0].get("generated_at", datetime.now(timezone.utc).isoformat()))

    return CityForecastResponse(
        city=normalized_city,
        forecasts=forecast_items,
        generated_at=generated_at,
    )


@router.get("/all/latest", response_model=AllForecastsResponse)
async def get_all_latest_forecasts() -> AllForecastsResponse:
    """Retrieve latest 24-hour predictions for all 4 cities simultaneously."""
    responses: List[CityForecastResponse] = []
    for city in CITIES:
        forecast_data = await get_city_forecast(city)
        responses.append(forecast_data)
    return AllForecastsResponse(forecasts=responses)
