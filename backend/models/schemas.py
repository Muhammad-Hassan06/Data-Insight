"""Pydantic schemas defining request and response models for the FastAPI backend."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ForecastItem(BaseModel):
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of forecast target hour")
    forecast_hour: int = Field(..., ge=1, le=24, description="Step ahead from 1 to 24")
    pm25_median: float = Field(..., description="Median PM2.5 prediction in ug/m3")
    pm25_lower: float = Field(..., description="Lower bound of 84% prediction interval (q=0.08)")
    pm25_upper: float = Field(..., description="Upper bound of 84% prediction interval (q=0.92)")


class CityForecastResponse(BaseModel):
    city: str
    forecasts: List[ForecastItem]
    generated_at: str


class AllForecastsResponse(BaseModel):
    forecasts: List[CityForecastResponse]


class FreshnessDetail(BaseModel):
    last_updated: str
    row_count: int
    status: str = Field(..., description="'fresh', 'stale', or 'warning'")


class FreshnessResponse(BaseModel):
    pm25: FreshnessDetail
    weather: FreshnessDetail


class QualityStatsResponse(BaseModel):
    cleaned: Dict[str, Any]
    processed: Dict[str, Any]


class QualityIssueItem(BaseModel):
    timestamp: str
    rule: str
    action: str = Field(..., description="FIX, FILL, or FLAG")
    rows_affected: int
    reason: str


class AskQuestionRequest(BaseModel):
    question: str = Field(..., min_length=3, description="User query about air quality, smog, or guidelines")


class CitationItem(BaseModel):
    source: str
    page: Optional[int] = None
    section: Optional[str] = None


class AskQuestionResponse(BaseModel):
    answer: str
    citations: List[CitationItem]
    row_ids: List[int] = Field(default_factory=list, description="Traceable DuckDB gold row IDs")
    data_points: int


class CorpusInfoResponse(BaseModel):
    total_chunks: int
    sources: Dict[str, int]
    status: str
