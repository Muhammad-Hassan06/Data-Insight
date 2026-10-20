"""
Application: FastAPI Backend
Location: backend/main.py
Purpose: Main ASGI entry point serving PM2.5 forecasting, data quality metrics, and RAG agent endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import forecast, quality, agent

app = FastAPI(
    title="Data Insight - PM2.5 Forecasting API",
    description="Backend API serving 24-hour PM2.5 forecasts, uncertainty intervals, and grounded RAG insights.",
    version="1.0.0",
)

# Configure CORS to permit local Vite dev server and Vercel production hosting
origins = [
    "https://data-insight-two.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers under /api prefix matching frontend api/client.js expectations
app.include_router(forecast.router, prefix="/api")
app.include_router(quality.router, prefix="/api")
app.include_router(agent.router, prefix="/api")


@app.get("/")
async def root():
    """API root endpoint providing status and documentation link."""
    return {
        "message": "Data Insight PM2.5 Forecasting API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "operational",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint to verify API uptime."""
    return {"status": "ok", "service": "data-insight-api"}


if __name__ == "__main__":
    import uvicorn
    # Team can run: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
