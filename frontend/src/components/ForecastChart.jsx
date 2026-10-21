import React, { useEffect, useState, useCallback } from 'react';
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine
} from 'recharts';
import { forecastAPI } from '../api/client';
import { getMockCityForecast, CITY_META } from '../data/mockData';
import { AlertCircle, TrendingUp, Wind, Droplets, RefreshCw } from 'lucide-react';

// AQI breakpoints for PM2.5
function getAQICategory(pm25) {
  if (pm25 <= 12) return { label: 'Good', color: '#22c55e', bg: 'rgba(34,197,94,0.15)' };
  if (pm25 <= 35.4) return { label: 'Moderate', color: '#eab308', bg: 'rgba(234,179,8,0.15)' };
  if (pm25 <= 55.4) return { label: 'Unhealthy (SG)', color: '#f97316', bg: 'rgba(249,115,22,0.15)' };
  if (pm25 <= 150.4) return { label: 'Unhealthy', color: '#ef4444', bg: 'rgba(239,68,68,0.15)' };
  if (pm25 <= 250.4) return { label: 'Very Unhealthy', color: '#a855f7', bg: 'rgba(168,85,247,0.15)' };
  return { label: 'Hazardous', color: '#991b1b', bg: 'rgba(153,27,27,0.15)' };
}

// Custom tooltip
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;

  const median = payload.find(p => p.dataKey === 'median');
  const upper = payload.find(p => p.dataKey === 'upper');
  const lower = payload.find(p => p.dataKey === 'lower');
  const aqi = median ? getAQICategory(parseFloat(median.value)) : null;

  return (
    <div className="custom-tooltip">
      <div className="tooltip-label">{label}</div>
      {median && (
        <div className="tooltip-row">
          <span>
            <span className="tooltip-dot" style={{ background: '#8b5cf6' }}></span>
            Forecast
          </span>
          <span className="tooltip-value">{parseFloat(median.value).toFixed(1)} µg/m³</span>
        </div>
      )}
      {upper && (
        <div className="tooltip-row">
          <span>
            <span className="tooltip-dot" style={{ background: 'rgba(139,92,246,0.4)' }}></span>
            Upper (90%)
          </span>
          <span className="tooltip-value">{parseFloat(upper.value).toFixed(1)} µg/m³</span>
        </div>
      )}
      {lower && (
        <div className="tooltip-row">
          <span>
            <span className="tooltip-dot" style={{ background: 'rgba(139,92,246,0.4)' }}></span>
            Lower (10%)
          </span>
          <span className="tooltip-value">{parseFloat(lower.value).toFixed(1)} µg/m³</span>
        </div>
      )}
      {aqi && (
        <div className="tooltip-row" style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid rgba(148,163,184,0.1)' }}>
          <span>AQI Category</span>
          <span style={{ color: aqi.color, fontWeight: 700, fontSize: '0.75rem' }}>{aqi.label}</span>
        </div>
      )}
    </div>
  );
}

export default function ForecastChart({ city }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [generatedAt, setGeneratedAt] = useState('');
  const [useMock, setUseMock] = useState(false);
  const [connectionError, setConnectionError] = useState(false);

  const loadForecast = useCallback(async () => {
    setLoading(true);
    setError(null);
    setConnectionError(false);

    try {
      const response = await forecastAPI.getCityForecast(city);
      const result = response.data;
      formatAndSetData(result);
      setUseMock(false);
      setConnectionError(false);
    } catch (err) {
      console.error('Forecast API error:', err);
      setConnectionError(true);
      setError(err.response?.data?.detail || err.message || 'Failed to load forecast');
      
      // Fallback to mock data
      const mock = getMockCityForecast(city);
      formatAndSetData(mock);
      setUseMock(true);
    } finally {
      setLoading(false);
    }
  }, [city]);

  function formatAndSetData(result) {
    const chartData = result.forecasts.map(f => ({
      hour: f.forecast_hour,
      time: new Date(f.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      }),
      median: parseFloat(parseFloat(f.pm25_median).toFixed(1)),
      lower: parseFloat(parseFloat(f.pm25_lower).toFixed(1)),
      upper: parseFloat(parseFloat(f.pm25_upper).toFixed(1)),
    }));

    setData(chartData);
    setGeneratedAt(result.generated_at);
  }

  useEffect(() => {
    loadForecast();
  }, [loadForecast]);

  // Calculate current AQI from latest median
  const currentPM25 = data.length > 0 ? data[0].median : 0;
  const currentAQI = getAQICategory(currentPM25);
  const maxPM25 = data.length > 0 ? Math.max(...data.map(d => d.median)) : 0;
  const minPM25 = data.length > 0 ? Math.min(...data.map(d => d.median)) : 0;
  const avgPM25 = data.length > 0 ? (data.reduce((s, d) => s + d.median, 0) / data.length) : 0;

  if (loading) {
    return (
      <div className="glass-card chart-container">
        <div className="loading-container">
          <div className="spinner"></div>
          <span className="loading-text">Loading forecast for {city}...</span>
        </div>
      </div>
    );
  }

  if (error && !useMock) {
    return (
      <div className="glass-card chart-container">
        <div className="error-state">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="chart-container">
      {/* Connection Status Warning */}
      {connectionError && (
        <div style={{
          background: 'rgba(234, 179, 8, 0.1)',
          border: '1px solid rgba(234, 179, 8, 0.3)',
          borderRadius: '8px',
          padding: '12px 16px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <AlertCircle size={20} style={{ color: '#eab308', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, color: '#eab308', marginBottom: '4px' }}>
              Backend Connection Failed
            </div>
            <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              Showing demo data. Error: {error}
            </div>
          </div>
          <button
            onClick={loadForecast}
            style={{
              background: 'rgba(234, 179, 8, 0.2)',
              border: '1px solid rgba(234, 179, 8, 0.4)',
              borderRadius: '6px',
              padding: '6px 12px',
              color: '#eab308',
              cursor: 'pointer',
              fontSize: '0.875rem',
              fontWeight: 500
            }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Current status bar */}
      <div className="dashboard-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 'var(--space-lg)' }}>
        <div className="stat-card accent">
          <div className="stat-icon accent">
            <Wind size={20} />
          </div>
          <div className="stat-label">Current PM2.5</div>
          <div className="stat-value" style={{ color: currentAQI.color }}>
            {currentPM25.toFixed(1)}
          </div>
          <div className="stat-change" style={{ background: currentAQI.bg, color: currentAQI.color }}>
            {currentAQI.label}
          </div>
        </div>

        <div className="stat-card info">
          <div className="stat-icon info">
            <TrendingUp size={20} />
          </div>
          <div className="stat-label">24h Average</div>
          <div className="stat-value">{avgPM25.toFixed(1)}</div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>µg/m³</span>
        </div>

        <div className="stat-card warning">
          <div className="stat-icon warning">
            <AlertCircle size={20} />
          </div>
          <div className="stat-label">Peak (24h)</div>
          <div className="stat-value">{maxPM25.toFixed(1)}</div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>µg/m³</span>
        </div>

        <div className="stat-card success">
          <div className="stat-icon success">
            <Droplets size={20} />
          </div>
          <div className="stat-label">Low (24h)</div>
          <div className="stat-value">{minPM25.toFixed(1)}</div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>µg/m³</span>
        </div>
      </div>

      {/* Chart */}
      <div className="chart-wrapper">
        <div className="card-header">
          <div>
            <div className="card-title">
              <span>{CITY_META[city]?.flag}</span>
              24-Hour PM2.5 Forecast — {city}
            </div>
            <div className="card-subtitle">
              {useMock && <span style={{ color: '#eab308', fontWeight: 600 }}>⚠️ Demo Mode • </span>}
              Generated {generatedAt ? new Date(generatedAt).toLocaleString() : 'N/A'}
            </div>
          </div>
          <button
            onClick={loadForecast}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 16px',
              background: loading ? 'var(--bg-secondary)' : 'var(--accent-gradient)',
              border: 'none',
              borderRadius: '8px',
              color: loading ? 'var(--text-muted)' : 'white',
              fontSize: '0.875rem',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              opacity: loading ? 0.6 : 1,
            }}
            onMouseEnter={(e) => {
              if (!loading) e.target.style.transform = 'translateY(-1px)';
            }}
            onMouseLeave={(e) => {
              e.target.style.transform = 'translateY(0)';
            }}
          >
            <RefreshCw size={16} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        <ResponsiveContainer width="100%" height={380}>
          <ComposedChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
            <defs>
              <linearGradient id="gradientArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="gradientLine" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#6366f1" />
                <stop offset="50%" stopColor="#8b5cf6" />
                <stop offset="100%" stopColor="#a78bfa" />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(148,163,184,0.06)"
              vertical={false}
            />

            <XAxis
              dataKey="time"
              tick={{ fill: '#64748b', fontSize: 11, fontFamily: 'Inter' }}
              axisLine={{ stroke: 'rgba(148,163,184,0.1)' }}
              tickLine={false}
              interval={2}
            />

            <YAxis
              tick={{ fill: '#64748b', fontSize: 11, fontFamily: 'Inter' }}
              axisLine={false}
              tickLine={false}
              label={{
                value: 'PM2.5 (µg/m³)',
                angle: -90,
                position: 'insideLeft',
                offset: 0,
                style: { fill: '#64748b', fontSize: 11, fontFamily: 'Inter' },
              }}
            />

            <Tooltip content={<CustomTooltip />} />

            {/* WHO 24h guideline reference line */}
            <ReferenceLine
              y={15}
              stroke="#22c55e"
              strokeDasharray="6 4"
              strokeWidth={1}
              label={{
                value: 'WHO 24h',
                position: 'right',
                fill: '#22c55e',
                fontSize: 10,
                fontFamily: 'Inter',
              }}
            />

            <ReferenceLine
              y={35}
              stroke="#eab308"
              strokeDasharray="6 4"
              strokeWidth={1}
              label={{
                value: 'Moderate',
                position: 'right',
                fill: '#eab308',
                fontSize: 10,
                fontFamily: 'Inter',
              }}
            />

            {/* Confidence interval area */}
            <Area
              type="monotone"
              dataKey="upper"
              stroke="none"
              fill="url(#gradientArea)"
              fillOpacity={1}
              isAnimationActive={true}
              animationDuration={1200}
            />
            <Area
              type="monotone"
              dataKey="lower"
              stroke="none"
              fill="var(--bg-primary)"
              fillOpacity={0.9}
              isAnimationActive={true}
              animationDuration={1200}
            />

            {/* Upper bound line */}
            <Line
              type="monotone"
              dataKey="upper"
              stroke="rgba(139,92,246,0.3)"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
              name="Upper (90%)"
              isAnimationActive={true}
              animationDuration={1200}
            />

            {/* Lower bound line */}
            <Line
              type="monotone"
              dataKey="lower"
              stroke="rgba(139,92,246,0.3)"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
              name="Lower (10%)"
              isAnimationActive={true}
              animationDuration={1200}
            />

            {/* Median forecast line */}
            <Line
              type="monotone"
              dataKey="median"
              stroke="url(#gradientLine)"
              strokeWidth={3}
              dot={{ r: 3, fill: '#8b5cf6', stroke: '#6366f1', strokeWidth: 2 }}
              activeDot={{ r: 6, fill: '#a78bfa', stroke: '#6366f1', strokeWidth: 2 }}
              name="Forecast"
              isAnimationActive={true}
              animationDuration={1500}
              animationEasing="ease-out"
            />

            <Legend
              wrapperStyle={{ fontSize: 12, fontFamily: 'Inter', color: '#94a3b8' }}
              iconType="line"
            />
          </ComposedChart>
        </ResponsiveContainer>

        {/* AQI Legend */}
        <div className="aqi-zones">
          <div className="aqi-zone">
            <div className="zone-color good"></div>
            <span>Good (0–12)</span>
          </div>
          <div className="aqi-zone">
            <div className="zone-color moderate"></div>
            <span>Moderate (12–35)</span>
          </div>
          <div className="aqi-zone">
            <div className="zone-color usg"></div>
            <span>Unhealthy SG (35–55)</span>
          </div>
          <div className="aqi-zone">
            <div className="zone-color unhealthy"></div>
            <span>Unhealthy (55–150)</span>
          </div>
          <div className="aqi-zone">
            <div className="zone-color very-unhealthy"></div>
            <span>Very Unhealthy (150–250)</span>
          </div>
          <div className="aqi-zone">
            <div className="zone-color hazardous"></div>
            <span>Hazardous (250+)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
