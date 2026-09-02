import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import { Send, Bot, User, Sparkles, MessageCircle, Loader2, AlertCircle, RefreshCw } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

// Simple markdown-to-JSX renderer for chat responses
function renderMarkdown(text) {
  if (!text) return null

  const lines = text.split('\n')
  const elements = []
  let inList = false
  let listItems = []
  let inTable = false
  let tableRows = []
  let tableHeaders = []
  let key = 0

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(<ul key={`list-${key++}`} className="chat-list">{listItems}</ul>)
      listItems = []
      inList = false
    }
  }

  const flushTable = () => {
    if (tableRows.length > 0) {
      elements.push(
        <div key={`table-wrap-${key++}`} className="chat-table-wrap">
          <table className="chat-table">
            {tableHeaders.length > 0 && (
              <thead>
                <tr>{tableHeaders.map((h, i) => <th key={i}>{formatInline(h.trim())}</th>)}</tr>
              </thead>
            )}
            <tbody>
              {tableRows.map((row, ri) => (
                <tr key={ri}>{row.map((cell, ci) => <td key={ci}>{formatInline(cell.trim())}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      tableRows = []
      tableHeaders = []
      inTable = false
    }
  }

  const formatInline = (str) => {
    // Bold
    str = str.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    // Italic
    str = str.replace(/\*(.*?)\*/g, '<em>$1</em>')
    // Inline code
    str = str.replace(/`(.*?)`/g, '<code>$1</code>')
    // Rupee formatting
    str = str.replace(/₹([\d,]+\.?\d*)/g, '₹$1')
    return <span dangerouslySetInnerHTML={{ __html: str }} />
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // Table rows
    if (line.includes('|') && line.trim().startsWith('|')) {
      const cells = line.split('|').filter(c => c.trim() !== '')
      // Check if separator row
      if (cells.every(c => /^[\s-:]+$/.test(c))) {
        continue // skip separator row
      }
      if (!inTable) {
        flushList()
        inTable = true
        tableHeaders = cells
      } else {
        tableRows.push(cells)
      }
      continue
    } else if (inTable) {
      flushTable()
    }

    // Headers
    if (line.startsWith('### ')) {
      flushList()
      elements.push(<h4 key={key++} className="chat-h4">{formatInline(line.slice(4))}</h4>)
      continue
    }
    if (line.startsWith('## ')) {
      flushList()
      elements.push(<h3 key={key++} className="chat-h3">{formatInline(line.slice(3))}</h3>)
      continue
    }
    if (line.startsWith('# ')) {
      flushList()
      elements.push(<h3 key={key++} className="chat-h3">{formatInline(line.slice(2))}</h3>)
      continue
    }

    // List items
    if (/^\s*[-*•]\s/.test(line)) {
      inList = true
      const content = line.replace(/^\s*[-*•]\s/, '')
      listItems.push(<li key={`li-${key++}`}>{formatInline(content)}</li>)
      continue
    }
    // Numbered list
    if (/^\s*\d+[.)]\s/.test(line)) {
      inList = true
      const content = line.replace(/^\s*\d+[.)]\s/, '')
      listItems.push(<li key={`li-${key++}`}>{formatInline(content)}</li>)
      continue
    }

    if (inList && line.trim() === '') {
      flushList()
      continue
    }
    if (inList) {
      flushList()
    }

    // Empty line
    if (line.trim() === '') {
      elements.push(<br key={key++} />)
      continue
    }

    // Regular paragraph
    elements.push(<p key={key++} className="chat-p">{formatInline(line)}</p>)
  }

  flushList()
  flushTable()

  return elements
}


// Typing indicator with animated dots
function TypingIndicator() {
  return (
    <motion.div
      className="chat-bubble assistant"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
    >
      <div className="chat-avatar">
        <Bot size={16} />
      </div>
      <div className="chat-bubble-content">
        <div className="typing-indicator">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </motion.div>
  )
}


export default function ChatAssistant() {
  const [messages, setMessages] = useState(() => {
    const saved = sessionStorage.getItem('chatMessages')
    if (saved) {
      try { return JSON.parse(saved) } catch (e) { return [] }
    }
    return []
  })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const [error, setError] = useState(null)
  const [importedPrediction, setImportedPrediction] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    sessionStorage.setItem('chatMessages', JSON.stringify(messages))
  }, [messages])

  // Detect forwarded prediction context from Predictor page
  useEffect(() => {
    const pending = sessionStorage.getItem('pendingPredictionContext')
    if (pending) {
      try {
        const ctx = JSON.parse(pending)
        sessionStorage.removeItem('pendingPredictionContext')
        setImportedPrediction(ctx)
        // Auto-send after a short delay so the UI has time to mount
        setTimeout(() => {
          sendMessage(ctx.message)
        }, 600)
      } catch (e) { /* ignore */ }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Load suggestions on mount
  useEffect(() => {
    api.getChatSuggestions()
      .then(data => setSuggestions(data.suggestions || []))
      .catch(() => {
        // Use fallback suggestions if API fails
        setSuggestions([
          {
            category: "Risk Analysis",
            questions: [
              "Which projects have critical risk scores?",
              "Show me the top 10 riskiest projects",
            ]
          },
          {
            category: "Cost Analysis",
            questions: [
              "Which projects have the highest cost overruns?",
              "Compare cost overrun rates across sectors",
            ]
          },
          {
            category: "Sector & Ministry",
            questions: [
              "Which ministry has the most troubled projects?",
              "Compare Railways vs Highways performance",
            ]
          },
        ])
      })
  }, [])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const sendMessage = async (text) => {
    const msg = text || input.trim()
    if (!msg || loading) return

    setInput('')
    setError(null)

    // Add user message
    const userMsg = { role: 'user', content: msg }
    const updatedMessages = [...messages, userMsg]
    setMessages(updatedMessages)
    setLoading(true)

    try {
      // Build history for context (only user/assistant, no system)
      const history = updatedMessages.map(m => ({
        role: m.role,
        content: m.content
      }))

      const data = await api.chat(msg, history)
      const assistantMsg = { role: 'assistant', content: data.response }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      const errorText = err.message || 'Failed to get response'
      setError(errorText)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ I encountered an error processing your request. Please try again.',
        isError: true,
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const clearChat = () => {
    setMessages([])
    setError(null)
    inputRef.current?.focus()
  }

  const hasMessages = messages.length > 0

  return (
    <div className="chat-page">
      {/* Header */}
      <div className="page-header">
        <div>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Sparkles style={{ color: 'var(--accent-purple)' }} />
            Project Intelligence Assistant
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: '4px', fontSize: '14px' }}>
            Ask questions about infrastructure projects in natural language — powered by LLM
          </p>
        </div>
        {hasMessages && (
          <button className="btn-ghost" onClick={clearChat} title="Clear conversation">
            <RefreshCw size={16} />
            New Chat
          </button>
        )}
      </div>

      {/* Imported Prediction Banner */}
      {importedPrediction && (
        <div style={{
          margin: '0 0 16px 0',
          padding: '16px 20px',
          borderRadius: '16px',
          background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.1), rgba(168, 85, 247, 0.1))',
          border: '1px solid rgba(56, 189, 248, 0.3)',
          display: 'flex',
          alignItems: 'center',
          gap: '14px',
          animation: 'fadeIn 0.4s ease',
        }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '12px', flexShrink: 0,
            background: 'linear-gradient(135deg, #38bdf8, #a855f7)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Bot size={20} color="#fff" />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '3px' }}>
              📊 Prediction Data Imported
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
              <strong style={{ color: 'var(--accent-blue)' }}>{importedPrediction.result?.risk_category} Risk</strong>
              {' '}({importedPrediction.result?.risk_score}/100) — {importedPrediction.form?.sector} | {importedPrediction.form?.state} |
              {' '}₹{importedPrediction.form?.revised_cost_cr} Cr revised cost · {importedPrediction.form?.physical_progress_pct}% progress
            </div>
          </div>
          <button
            onClick={() => setImportedPrediction(null)}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '18px', padding: '4px', lineHeight: 1 }}
          >×</button>
        </div>
      )}

      {/* Chat Container */}
      <div className="chat-container">
        <div className="chat-messages">
          {/* Welcome screen when no messages */}
          {!hasMessages && (
            <motion.div
              className="chat-welcome"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <div className="chat-welcome-icon">
                <Bot size={40} />
              </div>
              <h3>PAIMANA AI Assistant</h3>
              <p>
                I can answer questions about India's {'\u20B9'}42+ lakh crore infrastructure project portfolio.
                Ask me about project risks, cost overruns, delays, sector comparisons, and more.
              </p>

              {/* Suggestion chips */}
              <div className="chat-suggestions">
                {suggestions.map((group, gi) => (
                  <div key={gi} className="suggestion-group">
                    <span className="suggestion-category">{group.category}</span>
                    <div className="suggestion-chips">
                      {group.questions.map((q, qi) => (
                        <button
                          key={qi}
                          className="suggestion-chip"
                          onClick={() => sendMessage(q)}
                        >
                          <MessageCircle size={13} />
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* Messages */}
          <AnimatePresence>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                className={`chat-bubble ${msg.role} ${msg.isError ? 'error' : ''}`}
                initial={{ opacity: 0, y: 14, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="chat-avatar">
                  {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                </div>
                <div className="chat-bubble-content">
                  {msg.role === 'user' ? (
                    <p>{msg.content}</p>
                  ) : (
                    <div className="chat-markdown">
                      {renderMarkdown(msg.content)}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Typing indicator */}
          <AnimatePresence>
            {loading && <TypingIndicator />}
          </AnimatePresence>

          <div ref={messagesEndRef} />
        </div>

        {/* Error banner */}
        {error && (
          <motion.div
            className="chat-error-banner"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
          >
            <AlertCircle size={14} />
            {error}
          </motion.div>
        )}

        {/* Input area */}
        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <textarea
              ref={inputRef}
              className="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about projects, risks, cost overruns, sectors..."
              rows={1}
              disabled={loading}
            />
            <button
              className="chat-send-btn"
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
            >
              {loading ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
            </button>
          </div>
          <div className="chat-input-hint">
            Press Enter to send · Shift+Enter for new line · Powered by Groq + Llama 3.3
          </div>
        </div>
      </div>
    </div>
  )
}
