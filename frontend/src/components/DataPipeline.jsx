import React from 'react';
import { PIPELINE_STAGES, CORPUS_INFO } from '../data/mockData';
import {
  Download, Sparkles, Layers, Brain, Zap,
  CheckCircle, Play, BookOpen, FileText
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
              {CORPUS_INFO.total_chunks} document chunks from {Object.keys(CORPUS_INFO.sources).length} trusted sources indexed in ChromaDB
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
