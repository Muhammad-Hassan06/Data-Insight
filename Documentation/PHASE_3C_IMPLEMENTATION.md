# Phase 3-C Implementation Guide: FastAPI Backend + React Frontend

**Goal:** Build a full-stack web dashboard for PM2.5 forecasting system

**Stack:**
- **Backend:** FastAPI (Python) - REST API serving forecast data, quality status, RAG agent
- **Frontend:** React (Vite) - Interactive dashboard with charts and chat interface

**Estimated Time:** 3-4 hours per part (6-8 hours total)

---

## Project Structure

```
backend/
├── main.py                     # FastAPI app entry point
├── requirements.txt            # Python dependencies
├── routers/
│   ├── __init__.py
│   ├── forecast.py            # Forecast endpoints
│   ├── quality.py             # Quality/freshness endpoints
│   └── agent.py               # RAG agent endpoints
└── models/
    └── schemas.py             # Pydantic models

frontend/
├── package.json               # Node dependencies
├── vite.config.js             # Vite configuration
├── index.html                 # HTML entry point
└── src/
    ├── main.jsx              # React entry point
    ├── App.jsx               # Main app component
    ├── api/
    │   └── client.js         # API client
    ├── components/
    │   ├── CitySelector.jsx
    │   ├── ForecastChart.jsx
    │   ├── StatusPanel.jsx
    │   └── InsightChat.jsx
    └── styles/
        └── App.css
```

---

## Part 1: Backend (FastAPI)

### Step 1.1: Create Backend Directory Structure

```bash
mkdir backend
cd backend
mkdir routers models
touch main.py requirements.txt
touch routers/__init__.py routers/forecast.py routers/quality.py routers/agent.py
touch models/__init__.py models/schemas.py
```

### Step 1.2: Install Backend Dependencies

**`backend/requirements.txt`:**
```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6
pydantic==2.5.3
pandas==2.1.4
duckdb==0.10.0
pyarrow==15.0.0
python-dotenv==1.0.0
chromadb==0.4.22
sentence-transformers==2.3.1
```

Install:
```bash
pip install -r requirements.txt
```

### Step 1.3: Create Main FastAPI App

**`backend/main.py`:**
```python
"""
FastAPI Backend for HackInsight PM2.5 Forecasting System
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import forecast, quality, agent

# Create FastAPI app
app = FastAPI(
    title="HackInsight PM2.5 API",
    description="REST API for PM2.5 forecasting and air quality insights",
    version="1.0.0"
)

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative React port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(forecast.router, prefix="/api/forecast", tags=["Forecast"])
app.include_router(quality.router, prefix="/api/quality", tags=["Quality"])
app.include_router(agent.router, prefix="/api/agent", tags=["RAG Agent"])


@app.get("/")
def root():
    """API root endpoint"""
    return {
        "message": "HackInsight PM2.5 Forecasting API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "operational"
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
```

### Step 1.4: Create Pydantic Schemas

**`backend/models/schemas.py`:**
```python
"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ForecastPoint(BaseModel):
    """Single forecast data point"""
    timestamp: str
    forecast_hour: int
    pm25_median: float
    pm25_lower: float
    pm25_upper: float


class CityForecast(BaseModel):
    """Forecast for a city"""
    city: str
    forecasts: List[ForecastPoint]
    generated_at: str


class QualityMetric(BaseModel):
    """Quality metric for a dataset"""
    source: str
    last_updated: str
    row_count: int
    status: str


class PipelineStatus(BaseModel):
    """Pipeline run status"""
    run_time: str
    status: str
    fetch_records: int
    clean_records: int
    gold_records: int
    forecast_count: int


class QuestionRequest(BaseModel):
    """Request to ask RAG agent a question"""
    question: str = Field(..., min_length=1, max_length=500)


class AgentResponse(BaseModel):
    """Response from RAG agent"""
    answer: str
    citations: Optional[List[dict]] = None
    row_ids: Optional[List[int]] = None
    data_points: int = 0
```

### Step 1.5: Create Forecast Router

**`backend/routers/forecast.py`:**
```python
"""
Forecast endpoints
"""
from fastapi import APIRouter, HTTPException
import pandas as pd
from pathlib import Path
from typing import List

router = APIRouter()

PREDICTIONS_DIR = Path("../predictions")


@router.get("/cities")
def get_cities():
    """Get list of available cities"""
    return {
        "cities": ["Lahore", "Karachi", "Islamabad", "Peshawar"]
    }


@router.get("/{city}")
def get_city_forecast(city: str):
    """
    Get latest 24-hour forecast for a specific city
    
    Args:
        city: City name (Lahore, Karachi, Islamabad, or Peshawar)
    
    Returns:
        Forecast data with median, lower, and upper bounds
    """
    try:
        # Load latest forecast
        forecast_file = PREDICTIONS_DIR / "latest_forecast.parquet"
        
        if not forecast_file.exists():
            raise HTTPException(
                status_code=404,
                detail="No forecast data available. Run the pipeline first."
            )
        
        df = pd.read_parquet(forecast_file)
        
        # Filter by city
        city_data = df[df["city"] == city]
        
        if city_data.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No forecast found for city: {city}"
            )
        
        # Convert to dict
        forecasts = city_data[[
            "timestamp", "forecast_hour", 
            "pm25_median", "pm25_lower", "pm25_upper"
        ]].to_dict(orient="records")
        
        # Convert timestamps to strings
        for f in forecasts:
            f["timestamp"] = str(f["timestamp"])
        
        return {
            "city": city,
            "forecasts": forecasts,
            "generated_at": str(city_data.iloc[0]["generated_at"])
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all/latest")
def get_all_forecasts():
    """Get latest forecasts for all cities"""
    cities = ["Lahore", "Karachi", "Islamabad", "Peshawar"]
    results = []
    
    for city in cities:
        try:
            forecast = get_city_forecast(city)
            results.append(forecast)
        except HTTPException:
            continue
    
    return {"forecasts": results}
```

### Step 1.6: Create Quality Router

**`backend/routers/quality.py`:**
```python
"""
Data quality and pipeline status endpoints
"""
from fastapi import APIRouter, HTTPException
import duckdb
import json
from pathlib import Path
from datetime import datetime

router = APIRouter()

CLEANED_DB = Path("../data/cleaned/warehouse.duckdb")
PROCESSED_DB = Path("../data/processed/warehouse.duckdb")
QUALITY_LOG = Path("../data/cleaned/clean_log.jsonl")


@router.get("/freshness")
def get_data_freshness():
    """
    Check data freshness - when was data last updated
    """
    try:
        conn = duckdb.connect(str(CLEANED_DB), read_only=True)
        
        # Get latest PM2.5 timestamp
        pm25_latest = conn.execute("""
            SELECT MAX(timestamp_utc) as latest_time,
                   COUNT(*) as total_rows
            FROM cleaned_pm25
        """).fetchone()
        
        # Get latest weather timestamp
        weather_latest = conn.execute("""
            SELECT MAX(timestamp_utc) as latest_time,
                   COUNT(*) as total_rows
            FROM cleaned_weather
        """).fetchone()
        
        conn.close()
        
        return {
            "pm25": {
                "last_updated": str(pm25_latest[0]),
                "row_count": pm25_latest[1],
                "status": "fresh" if pm25_latest[0] else "stale"
            },
            "weather": {
                "last_updated": str(weather_latest[0]),
                "row_count": weather_latest[1],
                "status": "fresh" if weather_latest[0] else "stale"
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issues")
def get_quality_issues():
    """
    Get recent data quality issues from log
    """
    try:
        if not QUALITY_LOG.exists():
            return {"issues": [], "message": "No quality log found"}
        
        issues = []
        with open(QUALITY_LOG, "r") as f:
            for line in f:
                issues.append(json.loads(line))
        
        # Return last 20 issues
        return {"issues": issues[-20:], "total": len(issues)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def get_database_stats():
    """
    Get overall database statistics
    """
    try:
        # Cleaned database stats
        conn_clean = duckdb.connect(str(CLEANED_DB), read_only=True)
        
        pm25_stats = conn_clean.execute("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT city) as cities,
                MIN(timestamp_utc) as earliest,
                MAX(timestamp_utc) as latest
            FROM cleaned_pm25
        """).fetchone()
        
        weather_stats = conn_clean.execute("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT city) as cities
            FROM cleaned_weather
        """).fetchone()
        
        conn_clean.close()
        
        # Processed database stats
        conn_proc = duckdb.connect(str(PROCESSED_DB), read_only=True)
        
        gold_stats = conn_proc.execute("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT city) as cities,
                MIN(timestamp_utc) as earliest,
                MAX(timestamp_utc) as latest
            FROM gold_forecast_features
        """).fetchone()
        
        conn_proc.close()
        
        return {
            "cleaned": {
                "pm25_rows": pm25_stats[0],
                "weather_rows": weather_stats[0],
                "cities": pm25_stats[1],
                "date_range": {
                    "start": str(pm25_stats[2]),
                    "end": str(pm25_stats[3])
                }
            },
            "processed": {
                "gold_rows": gold_stats[0],
                "cities": gold_stats[1],
                "date_range": {
                    "start": str(gold_stats[2]),
                    "end": str(gold_stats[3])
                }
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Step 1.7: Create Agent Router

**`backend/routers/agent.py`:**
```python
"""
RAG Insight Agent endpoints
"""
from fastapi import APIRouter, HTTPException
from models.schemas import QuestionRequest, AgentResponse
import sys
from pathlib import Path

# Add parent directory to path to import src modules
sys.path.append(str(Path(__file__).parent.parent.parent))

router = APIRouter()

# Lazy load agent (only initialize when first question is asked)
_agent = None


def get_agent():
    """Lazy initialization of InsightAgent"""
    global _agent
    if _agent is None:
        try:
            from src.rag.query_agent import InsightAgent
            _agent = InsightAgent()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize RAG agent: {str(e)}"
            )
    return _agent


@router.post("/ask", response_model=AgentResponse)
def ask_agent(request: QuestionRequest):
    """
    Ask the RAG agent a question about air quality
    
    Args:
        request: Question to ask
    
    Returns:
        Answer with citations and row IDs
    """
    try:
        agent = get_agent()
        response = agent.generate_answer(request.question)
        
        return AgentResponse(
            answer=response.get("answer", ""),
            citations=response.get("citations", []),
            row_ids=response.get("row_ids", []),
            data_points=response.get("data_points", 0)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corpus-info")
def get_corpus_info():
    """Get information about the RAG corpus"""
    try:
        agent = get_agent()
        
        # Get collection stats
        collection = agent.collection
        count = collection.count()
        
        # Sample documents to get sources
        sample = collection.get(limit=min(count, 100))
        sources = {}
        for metadata in sample['metadatas']:
            source = metadata.get('source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        return {
            "total_chunks": count,
            "sources": sources,
            "status": "ready"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Step 1.8: Run Backend

```bash
# From backend directory
python main.py

# Or with uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Test endpoints:**
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Get cities: http://localhost:8000/api/forecast/cities

---

## Part 2: Frontend (React + Vite)

### Step 2.1: Create React App with Vite

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
```

### Step 2.2: Install Frontend Dependencies

```bash
npm install axios recharts lucide-react
```

**`frontend/package.json`** (should include):
```json
{
  "name": "hackinsight-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.5",
    "recharts": "^2.10.3",
    "lucide-react": "^0.312.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.8"
  }
}
```

### Step 2.3: Configure Vite

**`frontend/vite.config.js`:**
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

### Step 2.4: Create API Client

**`frontend/src/api/client.js`:**
```javascript
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Forecast API
export const forecastAPI = {
  getCities: () => api.get('/forecast/cities'),
  getCityForecast: (city) => api.get(`/forecast/${city}`),
  getAllForecasts: () => api.get('/forecast/all/latest'),
};

// Quality API
export const qualityAPI = {
  getFreshness: () => api.get('/quality/freshness'),
  getIssues: () => api.get('/quality/issues'),
  getStats: () => api.get('/quality/stats'),
};

// Agent API
export const agentAPI = {
  askQuestion: (question) => api.post('/agent/ask', { question }),
  getCorpusInfo: () => api.get('/agent/corpus-info'),
};

export default api;
```

### Step 2.5: Create City Selector Component

**`frontend/src/components/CitySelector.jsx`:**
```jsx
import React from 'react';

const CITIES = ['Lahore', 'Karachi', 'Islamabad', 'Peshawar'];

export default function CitySelector({ selectedCity, onCityChange }) {
  return (
    <div className="city-selector">
      <label htmlFor="city">Select City:</label>
      <select 
        id="city"
        value={selectedCity} 
        onChange={(e) => onCityChange(e.target.value)}
        className="city-dropdown"
      >
        {CITIES.map(city => (
          <option key={city} value={city}>{city}</option>
        ))}
      </select>
    </div>
  );
}
```

### Step 2.6: Create Forecast Chart Component

**`frontend/src/components/ForecastChart.jsx`:**
```jsx
import React, { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, 
  Tooltip, Legend, ResponsiveContainer, Area, ComposedChart
} from 'recharts';
import { forecastAPI } from '../api/client';

export default function ForecastChart({ city }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadForecast();
  }, [city]);

  const loadForecast = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await forecastAPI.getCityForecast(city);
      
      // Format data for chart
      const chartData = response.data.forecasts.map(f => ({
        hour: f.forecast_hour,
        time: new Date(f.timestamp).toLocaleTimeString('en-US', { 
          hour: '2-digit', 
          minute: '2-digit' 
        }),
        median: f.pm25_median.toFixed(2),
        lower: f.pm25_lower.toFixed(2),
        upper: f.pm25_upper.toFixed(2),
      }));
      
      setData(chartData);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load forecast');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading forecast...</div>;
  }

  if (error) {
    return <div className="error">Error: {error}</div>;
  }

  return (
    <div className="forecast-chart">
      <h2>24-Hour PM2.5 Forecast - {city}</h2>
      
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="time" 
            label={{ value: 'Time', position: 'insideBottom', offset: -5 }}
          />
          <YAxis 
            label={{ value: 'PM2.5 (μg/m³)', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip 
            formatter={(value) => `${value} μg/m³`}
            labelStyle={{ color: '#000' }}
          />
          <Legend />
          
          {/* Shaded confidence interval */}
          <Area
            type="monotone"
            dataKey="upper"
            stroke="none"
            fill="#fca5a5"
            fillOpacity={0.3}
          />
          <Area
            type="monotone"
            dataKey="lower"
            stroke="none"
            fill="#fff"
            fillOpacity={1}
          />
          
          {/* Forecast line */}
          <Line 
            type="monotone" 
            dataKey="median" 
            stroke="#ef4444" 
            strokeWidth={3}
            name="Forecast"
            dot={{ r: 4 }}
          />
          
          {/* Confidence bounds */}
          <Line 
            type="monotone" 
            dataKey="upper" 
            stroke="#fca5a5" 
            strokeWidth={1}
            strokeDasharray="5 5"
            name="Upper Bound (90%)"
            dot={false}
          />
          <Line 
            type="monotone" 
            dataKey="lower" 
            stroke="#fca5a5" 
            strokeWidth={1}
            strokeDasharray="5 5"
            name="Lower Bound (10%)"
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
      
      <div className="aqi-legend">
        <div className="legend-item">
          <span className="color-box good"></span> Good (0-12)
        </div>
        <div className="legend-item">
          <span className="color-box moderate"></span> Moderate (12-35)
        </div>
        <div className="legend-item">
          <span className="color-box unhealthy-sg"></span> Unhealthy SG (35-55)
        </div>
        <div className="legend-item">
          <span className="color-box unhealthy"></span> Unhealthy (55-150)
        </div>
      </div>
    </div>
  );
}
```

### Step 2.7: Create Status Panel Component

**`frontend/src/components/StatusPanel.jsx`:**
```jsx
import React, { useEffect, useState } from 'react';
import { qualityAPI } from '../api/client';
import { Clock, Database, AlertCircle, CheckCircle } from 'lucide-react';

export default function StatusPanel() {
  const [freshness, setFreshness] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [freshnessRes, statsRes] = await Promise.all([
        qualityAPI.getFreshness(),
        qualityAPI.getStats()
      ]);
      
      setFreshness(freshnessRes.data);
      setStats(statsRes.data);
    } catch (err) {
      console.error('Failed to load status:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="status-panel loading">Loading status...</div>;
  }

  return (
    <div className="status-panel">
      <h3>System Status</h3>
      
      <div className="status-grid">
        {/* Data Freshness */}
        <div className="status-card">
          <Clock size={24} />
          <h4>Data Freshness</h4>
          {freshness && (
            <>
              <div className="status-row">
                <span>PM2.5:</span>
                <span className={`status-badge ${freshness.pm25.status}`}>
                  {freshness.pm25.status}
                </span>
              </div>
              <div className="status-row">
                <span>Last Update:</span>
                <span>{new Date(freshness.pm25.last_updated).toLocaleString()}</span>
              </div>
            </>
          )}
        </div>

        {/* Database Stats */}
        <div className="status-card">
          <Database size={24} />
          <h4>Database</h4>
          {stats && (
            <>
              <div className="status-row">
                <span>PM2.5 Records:</span>
                <span>{stats.cleaned.pm25_rows.toLocaleString()}</span>
              </div>
              <div className="status-row">
                <span>Gold Table:</span>
                <span>{stats.processed.gold_rows.toLocaleString()}</span>
              </div>
              <div className="status-row">
                <span>Cities:</span>
                <span>{stats.cleaned.cities}</span>
              </div>
            </>
          )}
        </div>

        {/* Date Range */}
        <div className="status-card">
          <CheckCircle size={24} />
          <h4>Coverage</h4>
          {stats && (
            <>
              <div className="status-row">
                <span>Start:</span>
                <span>{new Date(stats.cleaned.date_range.start).toLocaleDateString()}</span>
              </div>
              <div className="status-row">
                <span>End:</span>
                <span>{new Date(stats.cleaned.date_range.end).toLocaleDateString()}</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
```

### Step 2.8: Create Insight Chat Component

**`frontend/src/components/InsightChat.jsx`:**
```jsx
import React, { useState } from 'react';
import { agentAPI } from '../api/client';
import { Send, Loader } from 'lucide-react';

export default function InsightChat() {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const askQuestion = async () => {
    if (!question.trim()) return;
    
    setLoading(true);
    setError(null);
    setResponse(null);
    
    try {
      const res = await agentAPI.askQuestion(question);
      setResponse(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to get answer');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      askQuestion();
    }
  };

  const exampleQuestions = [
    "What PM2.5 level is unhealthy?",
    "What's the current PM2.5 in Lahore?",
    "What are WHO air quality guidelines?",
    "What causes high PM2.5 in winter?"
  ];

  return (
    <div className="insight-chat">
      <h2>Ask the Air Quality Expert</h2>
      
      <div className="chat-input-container">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask a question about air quality..."
          rows={3}
          disabled={loading}
        />
        <button 
          onClick={askQuestion} 
          disabled={loading || !question.trim()}
          className="send-button"
        >
          {loading ? <Loader className="spin" /> : <Send />}
        </button>
      </div>

      {/* Example questions */}
      {!response && !loading && (
        <div className="example-questions">
          <p>Try asking:</p>
          {exampleQuestions.map((q, idx) => (
            <button
              key={idx}
              onClick={() => setQuestion(q)}
              className="example-btn"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="error-message">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Response */}
      {response && (
        <div className="agent-response">
          <div className="answer">
            <h4>Answer:</h4>
            <p>{response.answer}</p>
          </div>

          {response.citations && response.citations.length > 0 && (
            <div className="citations">
              <h4>Sources:</h4>
              <ul>
                {response.citations.map((cite, idx) => (
                  <li key={idx}>
                    {cite.source} (page {cite.page})
                  </li>
                ))}
              </ul>
            </div>
          )}

          {response.row_ids && response.row_ids.length > 0 && (
            <div className="data-ids">
              <small>
                📊 Data points: {response.data_points} | 
                Row IDs: {response.row_ids.slice(0, 5).join(', ')}
                {response.row_ids.length > 5 && '...'}
              </small>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

### Step 2.9: Create Main App Component

**`frontend/src/App.jsx`:**
```jsx
import { useState } from 'react';
import CitySelector from './components/CitySelector';
import ForecastChart from './components/ForecastChart';
import StatusPanel from './components/StatusPanel';
import InsightChat from './components/InsightChat';
import './styles/App.css';

function App() {
  const [selectedCity, setSelectedCity] = useState('Lahore');

  return (
    <div className="app">
      <header className="app-header">
        <h1>🌫️ HackInsight PM2.5 Forecasting System</h1>
        <p>Air Quality Monitoring & Prediction for Pakistani Cities</p>
      </header>

      <main className="app-main">
        {/* City Selection */}
        <div className="section">
          <CitySelector 
            selectedCity={selectedCity}
            onCityChange={setSelectedCity}
          />
        </div>

        {/* Forecast Chart */}
        <div className="section">
          <ForecastChart city={selectedCity} />
        </div>

        {/* Status Panel */}
        <div className="section">
          <StatusPanel />
        </div>

        {/* Insight Chat */}
        <div className="section">
          <InsightChat />
        </div>
      </main>

      <footer className="app-footer">
        <p>HackInsight 2026 | Team Data-Insight</p>
      </footer>
    </div>
  );
}

export default App;
```

### Step 2.10: Create Styles

**`frontend/src/styles/App.css`:**
```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
}

.app {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

/* Header */
.app-header {
  text-align: center;
  color: white;
  margin-bottom: 40px;
  padding: 30px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 15px;
  backdrop-filter: blur(10px);
}

.app-header h1 {
  font-size: 2.5rem;
  margin-bottom: 10px;
}

.app-header p {
  font-size: 1.2rem;
  opacity: 0.9;
}

/* Main Content */
.app-main {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.section {
  background: white;
  padding: 25px;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

/* City Selector */
.city-selector {
  display: flex;
  align-items: center;
  gap: 15px;
}

.city-selector label {
  font-weight: 600;
  font-size: 1.1rem;
}

.city-dropdown {
  padding: 10px 15px;
  font-size: 1rem;
  border: 2px solid #667eea;
  border-radius: 8px;
  background: white;
  cursor: pointer;
  transition: all 0.3s;
}

.city-dropdown:hover {
  border-color: #764ba2;
}

/* Forecast Chart */
.forecast-chart h2 {
  margin-bottom: 20px;
  color: #333;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #666;
  font-size: 1.1rem;
}

.error {
  padding: 20px;
  background: #fee;
  color: #c00;
  border-radius: 8px;
  border-left: 4px solid #c00;
}

/* AQI Legend */
.aqi-legend {
  display: flex;
  gap: 20px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.color-box {
  width: 30px;
  height: 20px;
  border-radius: 4px;
}

.color-box.good { background: #00e400; }
.color-box.moderate { background: #ffff00; }
.color-box.unhealthy-sg { background: #ff7e00; }
.color-box.unhealthy { background: #ff0000; }

/* Status Panel */
.status-panel h3 {
  margin-bottom: 20px;
  color: #333;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.status-card {
  padding: 20px;
  border: 1px solid #eee;
  border-radius: 8px;
  background: #fafafa;
}

.status-card svg {
  color: #667eea;
  margin-bottom: 10px;
}

.status-card h4 {
  margin-bottom: 15px;
  color: #555;
}

.status-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #eee;
}

.status-row:last-child {
  border-bottom: none;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.fresh {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.stale {
  background: #fee2e2;
  color: #991b1b;
}

/* Insight Chat */
.insight-chat h2 {
  margin-bottom: 20px;
  color: #333;
}

.chat-input-container {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.chat-input-container textarea {
  flex: 1;
  padding: 12px;
  border: 2px solid #ddd;
  border-radius: 8px;
  font-size: 1rem;
  font-family: inherit;
  resize: vertical;
  transition: border-color 0.3s;
}

.chat-input-container textarea:focus {
  outline: none;
  border-color: #667eea;
}

.send-button {
  padding: 12px 24px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.send-button:hover:not(:disabled) {
  background: #764ba2;
  transform: translateY(-2px);
}

.send-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Example Questions */
.example-questions {
  margin-top: 15px;
}

.example-questions p {
  margin-bottom: 10px;
  color: #666;
  font-size: 0.95rem;
}

.example-btn {
  display: block;
  width: 100%;
  padding: 12px;
  margin-bottom: 10px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 8px;
  text-align: left;
  cursor: pointer;
  transition: all 0.3s;
}

.example-btn:hover {
  background: #667eea;
  color: white;
  border-color: #667eea;
}

/* Agent Response */
.agent-response {
  margin-top: 20px;
  padding: 20px;
  background: #f9fafb;
  border-radius: 8px;
  border-left: 4px solid #667eea;
}

.agent-response .answer {
  margin-bottom: 15px;
}

.agent-response h4 {
  margin-bottom: 10px;
  color: #555;
}

.agent-response p {
  line-height: 1.6;
  color: #333;
}

.citations {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ddd;
}

.citations ul {
  list-style: none;
  padding: 0;
}

.citations li {
  padding: 8px 0;
  color: #666;
}

.data-ids {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ddd;
  color: #666;
  font-size: 0.9rem;
}

.error-message {
  padding: 15px;
  background: #fee;
  color: #c00;
  border-radius: 8px;
  margin-top: 15px;
}

/* Footer */
.app-footer {
  text-align: center;
  color: white;
  margin-top: 40px;
  padding: 20px;
  opacity: 0.8;
}

/* Responsive */
@media (max-width: 768px) {
  .app-header h1 {
    font-size: 1.8rem;
  }
  
  .status-grid {
    grid-template-columns: 1fr;
  }
  
  .aqi-legend {
    flex-direction: column;
  }
}
```

### Step 2.11: Run Frontend

```bash
# From frontend directory
npm run dev
```

**Open:** http://localhost:5173

---

## Testing the Full Stack

### 1. Start Backend
```bash
cd backend
python main.py
```

### 2. Start Frontend (in another terminal)
```bash
cd frontend
npm run dev
```

### 3. Test Endpoints

**Browser:**
- Dashboard: http://localhost:5173
- API docs: http://localhost:8000/docs

**Test Checklist:**
- ✅ City selector works
- ✅ Forecast chart loads for each city
- ✅ Status panel shows database stats
- ✅ Insight chat responds to questions
- ✅ Citations appear in responses
- ✅ All 4 cities have forecasts

---

## Deployment (Production)

### Backend Deployment (Heroku/Railway/Render)

1. Add `Procfile`:
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

2. Update CORS origins in `main.py`:
```python
allow_origins=[
    "http://localhost:5173",
    "https://your-frontend-domain.com",  # Add production URL
]
```

### Frontend Deployment (Vercel/Netlify)

1. Build:
```bash
npm run build
```

2. Deploy `dist/` folder

3. Update API base URL in production:
```javascript
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
```

4. Add environment variable: `VITE_API_URL=https://your-backend-domain.com/api`

---

## Success Criteria

- ✅ Backend API running on port 8000
- ✅ Frontend running on port 5173
- ✅ All 4 cities show forecasts
- ✅ Status panel displays fresh data
- ✅ RAG agent responds with citations
- ✅ Responsive design works on mobile
- ✅ No console errors

---

## Troubleshooting

### Backend Issues

**"Module not found" error:**
```bash
# Ensure you're in backend directory
cd backend
pip install -r requirements.txt
```

**"Failed to initialize RAG agent":**
```bash
# Build corpus first
cd ../
python -m src.rag.corpus_builder
```

**"Database not found":**
```bash
# Run pipeline to create databases
python -m src.flows.hourly_pipeline
```

### Frontend Issues

**"Network Error":**
- Check backend is running on port 8000
- Check CORS is configured correctly
- Verify API_BASE_URL in client.js

**"Cannot read property":**
- Check data structure from API matches component expectations
- Add null checks in components

**Charts not rendering:**
```bash
npm install recharts --save
```

---

## Next Steps After Implementation

1. **Test all features**
2. **Take screenshots**
3. **Run for 24 hours** (if part of hackathon requirements)
4. **Document any issues**
5. **Prepare demo script**

---

**Estimated Total Time:** 6-8 hours (3-4 hours backend + 3-4 hours frontend)

**Team Member Assignment:**
- Member 1: Backend (FastAPI + routers)
- Member 2: Frontend (React components)
- Member 3: Styling + testing
- Member 4: Integration + deployment

Good luck! 🚀
