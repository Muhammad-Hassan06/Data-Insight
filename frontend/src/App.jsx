import { useState, useEffect } from 'react';
import CitySelector from './components/CitySelector';
import ForecastChart from './components/ForecastChart';
import StatusPanel from './components/StatusPanel';
import InsightChat from './components/InsightChat';
import ModelPerformance from './components/ModelPerformance';
import DataPipeline from './components/DataPipeline';
import { MODEL_METRICS } from './data/mockData';
import {
  BarChart3, MessageCircle, Activity, Database,
  Brain, Zap, ExternalLink, Wind,
  CloudRain, Thermometer, MapPin
} from 'lucide-react';

const TABS = [
  { id: 'forecast', label: 'Forecast', icon: <BarChart3 size={16} /> },
  { id: 'model', label: 'Model Performance', icon: <Brain size={16} /> },
  { id: 'pipeline', label: 'Data Pipeline', icon: <Zap size={16} /> },
  { id: 'status', label: 'System Status', icon: <Activity size={16} /> },
  { id: 'chat', label: 'AI Insight Agent', icon: <MessageCircle size={16} /> },
];

function App() {
  const [selectedCity, setSelectedCity] = useState('Lahore');
  const [activeTab, setActiveTab] = useState('forecast');
  const [currentTime, setCurrentTime] = useState(new Date());

  // Update clock every minute
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header" id="app-header">
        <div className="header-content">
          <div className="header-left">
            <div className="header-logo">🌫️</div>
            <div className="header-title-group">
              <h1 className="header-title">HackInsight</h1>
              <span className="header-subtitle">
                PM2.5 Air Quality Forecasting System
              </span>
            </div>
          </div>

          <div className="header-right">
            <div className="header-badge" id="live-badge">
              <span className="pulse-dot"></span>
              <span>LIVE</span>
            </div>
            <div style={{
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
            }}>
              {currentTime.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: true,
              })}
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="nav-tabs" id="main-nav">
          {TABS.map(tab => (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </header>

      {/* ── Main Content ── */}
      <main className="main-content">
        {/* Forecast Tab */}
        {activeTab === 'forecast' && (
          <div className="tab-content" key="forecast">
            {/* City Selector */}
            <div className="section">
              <div className="section-header">
                <div className="section-title">
                  <MapPin size={18} />
                  Select City
                </div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm)',
                  fontSize: '0.78rem',
                  color: 'var(--text-muted)',
                }}>
                  <Wind size={14} />
                  4 cities monitored
                </div>
              </div>
              <CitySelector
                selectedCity={selectedCity}
                onCityChange={setSelectedCity}
              />
            </div>

            {/* Forecast Chart */}
            <div className="section">
              <ForecastChart city={selectedCity} />
            </div>
          </div>
        )}

        {/* Model Performance Tab */}
        {activeTab === 'model' && (
          <ModelPerformance key="model" />
        )}

        {/* Data Pipeline Tab */}
        {activeTab === 'pipeline' && (
          <DataPipeline key="pipeline" />
        )}

        {/* System Status Tab */}
        {activeTab === 'status' && (
          <div className="tab-content" key="status">
            <div className="section">
              <div className="section-header">
                <div className="section-title">
                  <Activity size={18} />
                  System Health & Data Quality
                </div>
              </div>
              <StatusPanel />
            </div>
          </div>
        )}

        {/* AI Insight Chat Tab */}
        {activeTab === 'chat' && (
          <div className="tab-content" key="chat">
            <InsightChat />
          </div>
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="app-footer" id="app-footer">
        <div className="footer-content">
          <span className="footer-text">
            HackInsight 2026 — Team Khubsoorat Shklein
          </span>
          <span className="footer-dot"></span>
          <span className="footer-text">
            Muhammad Feras Malik • Muhammad Hassan • Muhammad Ahmed Khan • Muhammad Sarim Umer
          </span>
          <span className="footer-dot"></span>
          <span className="footer-text" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Brain size={12} />
            LightGBM + CatBoost • {MODEL_METRICS.accuracy.improvement_pct}% improvement
          </span>
        </div>
      </footer>
    </div>
  );
}

export default App;
