import React, { useState, useRef, useEffect } from 'react';
import { agentAPI } from '../api/client';
import { getMockAgentResponse, CORPUS_INFO } from '../data/mockData';
import {
  Send, Loader, Bot, User, BookOpen,
  Sparkles, Database, MessageCircle
} from 'lucide-react';

export default function InsightChat() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const askQuestion = async () => {
    if (!question.trim() || loading) return;

    const userQ = question.trim();
    setQuestion('');
    setMessages(prev => [...prev, { type: 'user', text: userQ }]);
    setLoading(true);

    try {
      const res = await agentAPI.askQuestion(userQ);
      setMessages(prev => [
        ...prev,
        { type: 'assistant', ...res.data },
      ]);
    } catch (err) {
      // Fallback to mock
      const mock = getMockAgentResponse(userQ);
      setMessages(prev => [
        ...prev,
        { type: 'assistant', ...mock },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      askQuestion();
    }
  };

  // Auto-resize textarea
  const handleInput = (e) => {
    setQuestion(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  };

  const exampleQuestions = [
    "What PM2.5 level is unhealthy?",
    "Current air quality in Lahore?",
    "WHO air quality guidelines?",
    "Why is PM2.5 high in winter?",
    "Health impacts of air pollution?",
    "Which city has the worst air?",
  ];

  return (
    <div className="insight-chat" id="insight-chat">
      <div className="glass-card">
        <div className="card-header">
          <div>
            <div className="card-title">
              <div className="icon" style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>
                <Sparkles size={18} />
              </div>
              RAG Insight Agent
            </div>
            <div className="card-subtitle">
              Ask questions about air quality — powered by {CORPUS_INFO.total_chunks.toLocaleString()} document chunks from {Object.keys(CORPUS_INFO.sources).length} trusted sources
            </div>
          </div>
        </div>

        {/* Messages area */}
        <div className="chat-messages" id="chat-messages">
          {messages.length === 0 && (
            <div className="empty-state">
              <div className="empty-icon">
                <MessageCircle size={48} strokeWidth={1} />
              </div>
              <div className="empty-title">Ask the Air Quality Expert</div>
              <div className="empty-desc">
                Get instant answers about PM2.5 levels, health impacts, WHO guidelines, and air quality in Pakistani cities — with source citations.
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`chat-message ${msg.type}`}>
              <div className={`chat-avatar ${msg.type === 'user' ? 'user-avatar' : 'ai-avatar'}`}>
                {msg.type === 'user' ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div className="chat-body">
                {msg.type === 'user' ? (
                  <p className="message-text">{msg.text}</p>
                ) : (
                  <>
                    <p className="message-text">{msg.answer}</p>

                    {msg.urdu_summary && (
                      <div className="urdu-advisory-box" style={{
                        marginTop: '10px',
                        padding: '10px 14px',
                        background: 'rgba(34, 197, 94, 0.08)',
                        borderRight: '3px solid #22c55e',
                        borderRadius: '6px',
                        direction: 'rtl',
                        textAlign: 'right',
                        fontFamily: "'Noto Nastaliq Urdu', 'Jameel Noori Nastaleeq', 'Segoe UI', Tahoma, sans-serif",
                        fontSize: '0.92rem',
                        lineHeight: '1.6',
                        color: 'var(--text-primary)'
                      }}>
                        <div style={{ fontSize: '0.75rem', color: '#22c55e', fontWeight: 600, marginBottom: '4px' }}>
                          🇵🇰 اردو خلاصہ و ہیلتھ ایڈوائزری:
                        </div>
                        {msg.urdu_summary}
                      </div>
                    )}

                    {msg.citations && msg.citations.length > 0 && (
                      <div className="citations">
                        <div className="citations-title">
                          <BookOpen size={12} style={{ display: 'inline', marginRight: 4 }} />
                          Sources
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                          {msg.citations.map((cite, i) => (
                            <span key={i} className="citation-tag">
                              📄 {cite.source} {cite.page ? `p.${cite.page}` : ''}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {msg.row_ids && msg.row_ids.length > 0 && (
                      <div className="data-points-badge">
                        <Database size={12} />
                        {msg.data_points?.toLocaleString() || msg.row_ids.length} data points referenced
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="chat-message assistant">
              <div className="chat-avatar ai-avatar">
                <Bot size={16} />
              </div>
              <div className="chat-body">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)' }}>
                  <Loader size={16} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                  Analyzing data and searching corpus...
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Example questions */}
        {messages.length === 0 && (
          <div className="example-questions">
            {exampleQuestions.map((q, idx) => (
              <button
                key={idx}
                className="example-q-btn"
                onClick={() => {
                  setQuestion(q);
                  if (textareaRef.current) textareaRef.current.focus();
                }}
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input area */}
        <div className="chat-input-area" style={{ marginTop: 'var(--space-md)' }}>
          <div className="chat-input-wrapper">
            <textarea
              ref={textareaRef}
              id="chat-input"
              value={question}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="Ask about air quality, health impacts, WHO guidelines..."
              rows={1}
              disabled={loading}
            />
          </div>
          <button
            className="send-btn"
            id="send-button"
            onClick={askQuestion}
            disabled={loading || !question.trim()}
            title="Send message"
          >
            {loading ? <Loader size={18} style={{ animation: 'spin 1s linear infinite' }} /> : <Send size={18} />}
          </button>
        </div>
      </div>
    </div>
  );
}
