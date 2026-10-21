import React, { useEffect, useState } from 'react';
import { pipelineAPI } from '../api/client';
import { PIPELINE_STAGES, CORPUS_INFO } from '../data/mockData';
import {
  Download, Sparkles, Layers, Brain, Zap,
  CheckCircle, Play, BookOpen, FileText, TrendingUp, Activity
} from 'lucide-react';

const STAGE_ICONS = {
  1: <Download size={20} />,
  2: <Sparkles size={20} />,
  3: <Layers size={20} />,
  4: <Brain size={20} />,
  5: <Zap size={20} />,
};

export default function DataPipeline() {
  return (
    <div className="tab-content" id="data-pipeline">
      {/* Dataset Summary - Replaced Live Stats */}
      <div className="glass-card" style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="card-header">
          <div>
            <div className="card-title">
              <div className="icon" style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>
                <Activity size={18} />
              </div>
              Dataset Summary
            </div>
            <div className="card-subtitle">
              Historical data volume from 2-year collection period
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--space-md)',
        }}>
          {/* Total PM2.5 Records */}
          <div style={{
            padding: 'var(--space-md)',
            background: 'var(--bg-secondary)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
          }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              PM2.5 Observations
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
              338,985
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              From OpenAQ sensors
            </div>
          </div>

          {/* Total Weather Records */}
          <div style={{
            padding: 'var(--space-md)',
            background: 'var(--bg-secondary)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
          }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Weather Records
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
              70,176
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              From Open-Meteo ERA5
            </div>
          </div>

          {/* Gold Table Records */}
          <div style={{
            padding: 'var(--space-md)',
            background: 'var(--bg-secondary)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
          }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Engineered Features
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
              47,208
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Gold table rows (20 features)
            </div>
          </div>

          {/* Cities Tracked */}
          <div style={{
            padding: 'var(--space-md)',
            background: 'linear-gradient(135deg, rgba(99,102,241,0.1) 0%, rgba(139,92,246,0.1) 100%)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid rgba(139,92,246,0.2)',
          }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Cities Monitored
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#8b5cf6', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              4
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Major Pakistani cities
            </div>
          </div>
        </div>

        {/* Date Range */}
        <div style={{
          marginTop: 'var(--space-lg)',
          padding: 'var(--space-md)',
          background: 'rgba(56,189,248,0.05)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid rgba(56,189,248,0.1)',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: 'var(--space-md)',
        }}>
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
              Collection Start
            </div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              May 24, 2025
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
              Collection End
            </div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Oct 18, 2026
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
              Duration
            </div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#22c55e' }}>
              17 months
            </div>
          </div>
        </div>
      </div>

      {/* Pipeline Flow */}
      <div className="glass-card" style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="card-header">
          <div>
            <div className="card-title">
              <div className="icon" style={{ background: 'rgba(56,189,248,0.15)', color: '#38bdf8' }}>
                <Zap size={18} />
              </div>
              Data Processing Pipeline
            </div>
            <div className="card-subtitle">
              End-to-end automated pipeline — from API ingestion to 24-hour forecasts
            </div>
          </div>
        </div>

        <div className="pipeline-flow">
          {PIPELINE_STAGES.map((stage) => (
            <div key={stage.id} className="pipeline-stage">
              <div className={`pipeline-number ${stage.status}`}>
                {stage.status === 'completed' ? (
                  <CheckCircle size={20} />
                ) : (
                  <Play size={16} />
                )}
              </div>

              <div className="pipeline-stage-content">
                <div className="pipeline-stage-title">
                  Step {stage.id}: {stage.title}
                </div>
                <div className="pipeline-stage-desc">
                  {stage.description}
                </div>
                <div className="pipeline-stats">
                  {Object.entries(stage.stats).map(([key, val]) => (
                    <div key={key} className="pipeline-stat">
                      <div className="pipeline-stat-value">{val}</div>
                      <div className="pipeline-stat-label">{key.replace(/_/g, ' ')}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* RAG Corpus Info */}
      <div className="glass-card">
        <div className="card-header">
          <div>
            <div className="card-title">
              <div className="icon" style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>
                <BookOpen size={18} />
              </div>
              RAG Knowledge Corpus
            </div>
            <div className="card-subtitle">
              {CORPUS_INFO.total_chunks.toLocaleString()} document chunks from {Object.keys(CORPUS_INFO.sources).length} trusted sources indexed in ChromaDB
            </div>
          </div>
          <div className={`status-badge ${CORPUS_INFO.status === 'ready' ? 'fresh' : 'stale'}`}>
            {CORPUS_INFO.status}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--space-md)' }}>
          {Object.entries(CORPUS_INFO.sources).map(([source, chunks]) => (
            <div
              key={source}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-md)',
                padding: 'var(--space-md)',
                background: 'var(--bg-secondary)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div style={{
                width: 36,
                height: 36,
                borderRadius: 'var(--radius-sm)',
                background: 'var(--accent-glow)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-primary)',
                flexShrink: 0,
              }}>
                <FileText size={16} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}>
                  {source}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  {chunks} chunks indexed
                </div>
              </div>
              <div style={{
                width: '100%',
                maxWidth: 60,
                height: 4,
                background: 'var(--bg-card)',
                borderRadius: 'var(--radius-full)',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${(chunks / CORPUS_INFO.total_chunks) * 100}%`,
                  height: '100%',
                  background: 'var(--accent-gradient)',
                  borderRadius: 'var(--radius-full)',
                }}></div>
              </div>
            </div>
          ))}
        </div>

        {/* Features list */}
        <div style={{
          marginTop: 'var(--space-lg)',
          padding: 'var(--space-md)',
          background: 'rgba(34,197,94,0.05)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid rgba(34,197,94,0.1)',
        }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 'var(--space-sm)' }}>
            RAG Agent Capabilities
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-sm)' }}>
            {[
              'Semantic search with sentence-transformers',
              'Data integration with DuckDB warehouse',
              'Citation tracking (source + page)',
              'Row ID traceability for data claims',
              'Honest "I don\'t know" for unknown queries',
              'Multi-source answer synthesis',
            ].map((feat, i) => (
              <div key={i} style={{
                fontSize: '0.78rem',
                color: 'var(--text-secondary)',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}>
                <CheckCircle size={12} style={{ color: 'var(--success)', flexShrink: 0 }} />
                {feat}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
