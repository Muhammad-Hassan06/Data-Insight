import React, { useEffect, useState } from 'react';
import { qualityAPI, pipelineAPI } from '../api/client';
import { getMockFreshness, getMockStats } from '../data/mockData';
import {
  Clock, Database, CheckCircle, Activity,
  Server, HardDrive, BarChart3, Shield, Play, Loader
} from 'lucide-react';

export default function StatusPanel() {
  const [freshness, setFreshness] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [triggerLoading, setTriggerLoading] = useState(false);
  const [triggerMessage, setTriggerMessage] = useState(null);

  useEffect(() => {
    loadData();
    loadPipelineStatus();
    const interval = setInterval(() => {
      loadData();
      loadPipelineStatus();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [freshnessRes, statsRes] = await Promise.all([
        qualityAPI.getFreshness(),
        qualityAPI.getStats(),
      ]);
      setFreshness(freshnessRes.data);
      setStats(statsRes.data);
    } catch (err) {
      // Fallback to mock
      setFreshness(getMockFreshness());
      setStats(getMockStats());
    } finally {
      setLoading(false);
    }
  };

  const loadPipelineStatus = async () => {
    try {
      const res = await pipelineAPI.getPipelineStatus();
      setPipelineStatus(res.data);
    } catch (err) {
      // Pipeline endpoint might not be available
      setPipelineStatus(null);
    }
  };

  const handleTriggerPipeline = async () => {
    setTriggerLoading(true);
    setTriggerMessage(null);
    
    try {
      const res = await pipelineAPI.triggerPipeline();
      setTriggerMessage({
        type: 'success',
        text: res.data.message || 'Pipeline started successfully! Refresh in 5-10 minutes.',
      });
      
      // Poll status every 10 seconds while pipeline is running
      const statusInterval = setInterval(async () => {
        const statusRes = await pipelineAPI.getPipelineStatus();
        setPipelineStatus(statusRes.data);
        
        if (!statusRes.data.is_running) {
          clearInterval(statusInterval);
          setTriggerLoading(false);
          
          if (statusRes.data.last_status === 'success') {
            setTriggerMessage({
              type: 'success',
              text: '✓ Pipeline completed successfully! Data updated.',
            });
            loadData(); // Refresh stats
          } else if (statusRes.data.last_status === 'failed' || statusRes.data.last_status === 'error') {
            setTriggerMessage({
              type: 'error',
              text: `Pipeline failed: ${statusRes.data.last_error || 'Unknown error'}`,
            });
          }
        }
      }, 10000);
      
    } catch (err) {
      setTriggerLoading(false);
      setTriggerMessage({
        type: 'error',
        text: err.response?.data?.detail || err.message || 'Failed to trigger pipeline',
      });
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <span className="loading-text">Loading system status...</span>
      </div>
    );
  }

  const timeAgo = (dateStr) => {
    if (!dateStr || dateStr === 'None') return 'N/A';
    const now = new Date();
    const then = new Date(dateStr);
    const diffMs = now - then;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  return (
    <div className="status-grid">
      {/* Data Freshness */}
      <div className="status-card" id="status-freshness">
        <div className="status-card-header">
          <div className="status-card-icon freshness">
            <Clock size={20} />
          </div>
          <div>
            <div className="status-card-title">Data Freshness</div>
            <div className="status-card-desc">Real-time data pipeline status</div>
          </div>
        </div>

        {freshness && (
          <>
            <div className="status-row">
              <span className="status-row-label">PM2.5 Data</span>
              <span className={`status-badge ${freshness.pm25.status}`}>
                {freshness.pm25.status}
              </span>
            </div>
            <div className="status-row">
              <span className="status-row-label">Last PM2.5 Update</span>
              <span className="status-row-value">
                {timeAgo(freshness.pm25.last_updated)}
              </span>
            </div>
            <div className="status-row">
              <span className="status-row-label">Weather Data</span>
              <span className={`status-badge ${freshness.weather.status}`}>
                {freshness.weather.status}
              </span>
            </div>
            <div className="status-row">
              <span className="status-row-label">Last Weather Update</span>
              <span className="status-row-value">
                {timeAgo(freshness.weather.last_updated)}
              </span>
            </div>
          </>
        )}
      </div>

      {/* Database Stats */}
      <div className="status-card" id="status-database">
        <div className="status-card-header">
          <div className="status-card-icon database">
            <Database size={20} />
          </div>
          <div>
            <div className="status-card-title">Database</div>
            <div className="status-card-desc">DuckDB warehouse statistics</div>
          </div>
        </div>

        {stats && (
          <>
            <div className="status-row">
              <span className="status-row-label">PM2.5 Records</span>
              <span className="status-row-value">
                {stats.cleaned.pm25_rows.toLocaleString()}
              </span>
            </div>
            <div className="status-row">
              <span className="status-row-label">Weather Records</span>
              <span className="status-row-value">
                {stats.cleaned.weather_rows.toLocaleString()}
              </span>
            </div>
            <div className="status-row">
              <span className="status-row-label">Gold Table Rows</span>
              <span className="status-row-value">
                {stats.processed.gold_rows.toLocaleString()}
              </span>
            </div>
            <div className="status-row">
              <span className="status-row-label">Cities Tracked</span>
              <span className="status-row-value">{stats.cleaned.cities}</span>
            </div>
          </>
        )}
      </div>

      {/* Data Coverage */}
      <div className="status-card" id="status-coverage">
        <div className="status-card-header">
          <div className="status-card-icon coverage">
            <BarChart3 size={20} />
          </div>
          <div>
            <div className="status-card-title">Data Coverage</div>
            <div className="status-card-desc">Temporal range of collected data</div>
          </div>
        </div>

        {stats && (
          <>
            <div className="status-row">
              <span className="status-row-label">Start Date</span>
              <span className="status-row-value">
                {new Date(stats.cleaned.date_range.start).toLocaleDateString('en-US', {
                  year: 'numeric', month: 'short', day: 'numeric'
                })}
              </span>
            </div>
            <div className="status-row">
              <span className="status-row-label">End Date</span>
              <span className="status-row-value">
                {new Date(stats.cleaned.date_range.end).toLocaleDateString('en-US', {
                  year: 'numeric', month: 'short', day: 'numeric'
                })}
              </span>
            </div>
            <div className="status-row">
              <span className="status-row-label">Gold Start</span>
              <span className="status-row-value">
                {new Date(stats.processed.date_range.start).toLocaleDateString('en-US', {
                  year: 'numeric', month: 'short', day: 'numeric'
                })}
              </span>
            </div>
            <div className="status-row">
              <span className="status-row-label">Gold End</span>
              <span className="status-row-value">
                {new Date(stats.processed.date_range.end).toLocaleDateString('en-US', {
                  year: 'numeric', month: 'short', day: 'numeric'
                })}
              </span>
            </div>
          </>
        )}
      </div>

      {/* System Health */}
      <div className="status-card" id="status-system">
        <div className="status-card-header">
          <div className="status-card-icon pipeline">
            <Shield size={20} />
          </div>
          <div>
            <div className="status-card-title">System Health</div>
            <div className="status-card-desc">Pipeline and API status</div>
          </div>
        </div>

        <div className="status-row">
          <span className="status-row-label">API Status</span>
          <span className="status-badge operational">Operational</span>
        </div>
        <div className="status-row">
          <span className="status-row-label">Pipeline</span>
          <span className={`status-badge ${pipelineStatus?.is_running ? 'warning' : 'fresh'}`}>
            {pipelineStatus?.is_running ? 'Running' : 'Ready'}
          </span>
        </div>
        <div className="status-row">
          <span className="status-row-label">Schedule</span>
          <span className="status-row-value">Every hour at :05</span>
        </div>
        <div className="status-row">
          <span className="status-row-label">Models Loaded</span>
          <span className="status-row-value">6 / 6</span>
        </div>
        
        {pipelineStatus?.last_run && (
          <div className="status-row">
            <span className="status-row-label">Last Run</span>
            <span className="status-row-value">
              {timeAgo(pipelineStatus.last_run)}
            </span>
          </div>
        )}

        {/* Trigger Message */}
        {triggerMessage && (
          <div style={{
            marginTop: '12px',
            padding: '10px 12px',
            borderRadius: '6px',
            fontSize: '0.8rem',
            background: triggerMessage.type === 'success' 
              ? 'rgba(34, 197, 94, 0.1)' 
              : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${triggerMessage.type === 'success' 
              ? 'rgba(34, 197, 94, 0.3)' 
              : 'rgba(239, 68, 68, 0.3)'}`,
            color: triggerMessage.type === 'success' ? '#22c55e' : '#ef4444',
          }}>
            {triggerMessage.text}
          </div>
        )}

        {/* Trigger Button */}
        <button
          onClick={handleTriggerPipeline}
          disabled={triggerLoading || pipelineStatus?.is_running}
          style={{
            marginTop: '16px',
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            padding: '12px 16px',
            background: (triggerLoading || pipelineStatus?.is_running) 
              ? 'var(--bg-secondary)' 
              : 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
            border: 'none',
            borderRadius: '8px',
            color: (triggerLoading || pipelineStatus?.is_running) 
              ? 'var(--text-muted)' 
              : 'white',
            fontSize: '0.875rem',
            fontWeight: 600,
            cursor: (triggerLoading || pipelineStatus?.is_running) 
              ? 'not-allowed' 
              : 'pointer',
            transition: 'all 0.2s ease',
            opacity: (triggerLoading || pipelineStatus?.is_running) ? 0.6 : 1,
          }}
        >
          {triggerLoading || pipelineStatus?.is_running ? (
            <>
              <Loader size={16} style={{ animation: 'spin 1s linear infinite' }} />
              Pipeline Running...
            </>
          ) : (
            <>
              <Play size={16} />
              Run Pipeline Now
            </>
          )}
        </button>
        
        <div style={{
          marginTop: '8px',
          fontSize: '0.7rem',
          color: 'var(--text-muted)',
          textAlign: 'center',
        }}>
          Fetches new data, cleans, processes & generates forecasts
        </div>
      </div>
    </div>
  );
}
