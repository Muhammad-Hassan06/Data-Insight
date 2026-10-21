import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, RadialBarChart,
  RadialBar, Legend, PieChart, Pie
} from 'recharts';
import { MODEL_METRICS, BASELINE_METRICS, CITY_META } from '../data/mockData';
import {
  Target, TrendingDown, Gauge, Award,
  ArrowDown, BarChart3, Brain, Layers
} from 'lucide-react';

const CITY_COLORS = {
  Karachi: '#22c55e',
  Islamabad: '#38bdf8',
  Lahore: '#ef4444',
  Peshawar: '#f59e0b',
};

// Custom bar tooltip
function BarTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="custom-tooltip">
      <div className="tooltip-label">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="tooltip-row">
          <span>
            <span className="tooltip-dot" style={{ background: p.fill || p.color }}></span>
            {p.name}
          </span>
          <span className="tooltip-value">{parseFloat(p.value).toFixed(2)} µg/m³</span>
        </div>
      ))}
    </div>
  );
}

export default function ModelPerformance() {
  const { accuracy, uncertainty, fairness, data, model_params } = MODEL_METRICS;

  // City comparison data
  const cityComparisonData = fairness.by_city.map(c => ({
    city: c.city,
    our_mae: c.mae,
    baseline_mae: BASELINE_METRICS.by_city.find(b => b.city === c.city)?.mae || 0,
    coverage: c.coverage_pct,
    fill: CITY_COLORS[c.city],
  }));

  // Improvement data for visualization
  const improvementData = [
    { name: 'MAE', baseline: accuracy.baseline_mae, ours: accuracy.mae, unit: 'µg/m³' },
    { name: 'RMSE', baseline: BASELINE_METRICS.overall.rmse, ours: accuracy.rmse, unit: 'µg/m³' },
    { name: 'MAPE', baseline: BASELINE_METRICS.overall.mape, ours: accuracy.mape, unit: '%' },
  ];

  return (
    <div className="tab-content" id="model-performance">
      {/* Key Metrics */}
      <div className="dashboard-grid" style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="stat-card accent">
          <div className="stat-icon accent">
            <Target size={20} />
          </div>
          <div className="stat-label">MAE (Error)</div>
          <div className="stat-value">{accuracy.mae}</div>
          <div className="stat-change positive">
            <ArrowDown size={12} /> {accuracy.improvement_pct}% vs baseline
          </div>
        </div>

        <div className="stat-card success">
          <div className="stat-icon success">
            <Gauge size={20} />
          </div>
          <div className="stat-label">Coverage</div>
          <div className="stat-value">{uncertainty.coverage_pct}%</div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Target: {uncertainty.target_coverage_pct}%
          </span>
        </div>

        <div className="stat-card info">
          <div className="stat-icon info">
            <Brain size={20} />
          </div>
          <div className="stat-label">Model Type</div>
          <div className="stat-value" style={{ fontSize: '1.1rem' }}>Hybrid</div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            LightGBM + CatBoost
          </span>
        </div>

        <div className="stat-card warning">
          <div className="stat-icon warning">
            <Layers size={20} />
          </div>
          <div className="stat-label">Features</div>
          <div className="stat-value">{data.n_features}</div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {data.train_samples.toLocaleString()} training samples
          </span>
        </div>
      </div>

      <div className="two-column">
        {/* Baseline vs Our Model Chart */}
        <div className="glass-card">
          <div className="card-header">
            <div>
              <div className="card-title">
                <div className="icon">
                  <BarChart3 size={18} />
                </div>
                Baseline vs. Our Model (MAE per City)
              </div>
              <div className="card-subtitle">
                Lower is better — MAE measured in µg/m³
              </div>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={cityComparisonData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" vertical={false} />
              <XAxis
                dataKey="city"
                tick={{ fill: '#94a3b8', fontSize: 12, fontFamily: 'Inter' }}
                axisLine={{ stroke: 'rgba(148,163,184,0.1)' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 11, fontFamily: 'Inter' }}
                axisLine={false}
                tickLine={false}
                label={{
                  value: 'MAE (µg/m³)',
                  angle: -90,
                  position: 'insideLeft',
                  style: { fill: '#64748b', fontSize: 11, fontFamily: 'Inter' },
                }}
              />
              <Tooltip content={<BarTooltip />} />
              <Bar
                dataKey="baseline_mae"
                fill="rgba(148,163,184,0.25)"
                name="Baseline (Persistence)"
                radius={[4, 4, 0, 0]}
                barSize={28}
              />
              <Bar dataKey="our_mae" name="Our Model" radius={[4, 4, 0, 0]} barSize={28}>
                {cityComparisonData.map((entry, index) => (
                  <Cell key={index} fill={entry.fill} fillOpacity={0.85} />
                ))}
              </Bar>
              <Legend wrapperStyle={{ fontSize: 12, fontFamily: 'Inter', color: '#94a3b8' }} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* City Details Table */}
        <div className="glass-card">
          <div className="card-header">
            <div>
              <div className="card-title">
                <div className="icon" style={{ background: 'rgba(245,158,11,0.15)', color: '#f59e0b' }}>
                  <Award size={18} />
                </div>
                Per-City Performance
              </div>
              <div className="card-subtitle">
                Detailed model accuracy breakdown
              </div>
            </div>
          </div>

          <table className="city-comparison-table">
            <thead>
              <tr>
                <th>City</th>
                <th>MAE</th>
                <th>RMSE</th>
                <th>Coverage</th>
                <th>Samples</th>
              </tr>
            </thead>
            <tbody>
              {fairness.by_city.map((c) => (
                <tr key={c.city}>
                  <td>
                    <div className="city-name">
                      <span>{CITY_META[c.city]?.flag}</span>
                      {c.city}
                    </div>
                  </td>
                  <td>
                    <span className="metric-val" style={{ color: CITY_COLORS[c.city] }}>
                      {c.mae.toFixed(2)}
                    </span>
                  </td>
                  <td>
                    <span className="metric-val">{c.rmse.toFixed(2)}</span>
                  </td>
                  <td>
                    <div>
                      <span className="metric-val">{c.coverage_pct}%</span>
                      <div className="progress-bar-container" style={{ marginTop: 4 }}>
                        <div
                          className="progress-bar-fill"
                          style={{ width: `${c.coverage_pct}%` }}
                        ></div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className="metric-val">{c.samples.toLocaleString()}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Overall improvement summary */}
          <div style={{
            marginTop: 'var(--space-lg)',
            padding: 'var(--space-md)',
            background: 'rgba(99,102,241,0.06)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid rgba(99,102,241,0.15)',
          }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
              Overall Improvement
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', fontWeight: 800, color: 'var(--success)' }}>
                  {accuracy.improvement_pct}%
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginLeft: 8 }}>
                  MAE reduction
                </span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--text-muted)', textDecoration: 'line-through' }}>
                  {accuracy.baseline_mae} µg/m³
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--success)', fontWeight: 700 }}>
                  {accuracy.mae} µg/m³
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Model Details */}
      <div className="glass-card" style={{ marginTop: 'var(--space-lg)' }}>
        <div className="card-header">
          <div>
            <div className="card-title">
              <div className="icon" style={{ background: 'rgba(139,92,246,0.15)', color: '#a78bfa' }}>
                <Brain size={18} />
              </div>
              Model Configuration
            </div>
            <div className="card-subtitle">{MODEL_METRICS.model}</div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-lg)' }}>
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 'var(--space-sm)' }}>
              Hyperparameters
            </div>
            {Object.entries(model_params).map(([key, val]) => (
              <div key={key} className="status-row">
                <span className="status-row-label">{key.replace(/_/g, ' ')}</span>
                <span className="status-row-value">
                  {Array.isArray(val) ? val.join(', ') : val}
                </span>
              </div>
            ))}
          </div>

          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 'var(--space-sm)' }}>
              Training Data
            </div>
            <div className="status-row">
              <span className="status-row-label">Train Samples</span>
              <span className="status-row-value">{data.train_samples.toLocaleString()}</span>
            </div>
            <div className="status-row">
              <span className="status-row-label">Test Samples</span>
              <span className="status-row-value">{data.test_samples.toLocaleString()}</span>
            </div>
            <div className="status-row">
              <span className="status-row-label">Num Features</span>
              <span className="status-row-value">{data.n_features}</span>
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 'var(--space-sm)' }}>
              Improvements Applied
            </div>
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {MODEL_METRICS.improvements.map((imp, i) => (
                <li key={i} style={{
                  fontSize: '0.8rem',
                  color: 'var(--text-secondary)',
                  padding: '4px 0',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}>
                  <span style={{ color: 'var(--success)', fontSize: '0.7rem' }}>✓</span>
                  {imp}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
