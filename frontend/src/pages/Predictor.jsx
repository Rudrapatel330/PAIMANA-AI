import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Zap, AlertTriangle, Clock, TrendingUp, Shield, ChevronRight, RotateCcw, Sparkles, MessageSquare, Bot } from 'lucide-react'

const presets = [
  {
    label: '🔴 High Risk Highway',
    data: {
      ministry: 'Ministry of Road Transport & Highways',
      sector: 'Roads & Highways',
      state: 'Maharashtra',
      original_cost_cr: 1200,
      revised_cost_cr: 2100,
      cumulative_expenditure_cr: 1800,
      physical_progress_pct: 45,
      planned_duration_months: 60,
      project_age_months: 72,
    }
  },
  {
    label: '🟢 On-Track Railway',
    data: {
      ministry: 'Ministry of Railways',
      sector: 'Railways',
      state: 'Gujarat',
      original_cost_cr: 800,
      revised_cost_cr: 850,
      cumulative_expenditure_cr: 620,
      physical_progress_pct: 78,
      planned_duration_months: 48,
      project_age_months: 36,
    }
  },
  {
    label: '🟡 Moderate Risk Power',
    data: {
      ministry: 'Ministry of Power',
      sector: 'Electricity Generation',
      state: 'Andhra Pradesh',
      original_cost_cr: 3500,
      revised_cost_cr: 4200,
      cumulative_expenditure_cr: 2100,
      physical_progress_pct: 55,
      planned_duration_months: 72,
      project_age_months: 60,
    }
  },
]

const defaultForm = {
  ministry: '',
  sector: '',
  state: '',
  original_cost_cr: '',
  revised_cost_cr: '',
  cumulative_expenditure_cr: '',
  physical_progress_pct: '',
  planned_duration_months: '',
  project_age_months: '',
}

export default function Predictor() {
  const navigate = useNavigate()
  const [options, setOptions] = useState({ ministries: [], sectors: [], states: [] })
  const [form, setForm] = useState(() => {
    try {
      const saved = sessionStorage.getItem('predictorForm')
      return saved ? JSON.parse(saved) : defaultForm
    } catch { return defaultForm }
  })
  const [result, setResult] = useState(() => {
    try {
      const saved = sessionStorage.getItem('predictorResult')
      return saved ? JSON.parse(saved) : null
    } catch { return null }
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getPredictOptions().then(setOptions).catch(console.error)
  }, [])

  // Persist form and result across navigation
  useEffect(() => {
    sessionStorage.setItem('predictorForm', JSON.stringify(form))
  }, [form])

  useEffect(() => {
    if (result) sessionStorage.setItem('predictorResult', JSON.stringify(result))
    else sessionStorage.removeItem('predictorResult')
  }, [result])

  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  const handlePreset = (preset) => {
    setForm(preset.data)
    setResult(null)
    setError(null)
  }

  const handleReset = () => {
    setForm(defaultForm)
    setResult(null)
    setError(null)
    sessionStorage.removeItem('predictorForm')
    sessionStorage.removeItem('predictorResult')
  }

  const handleDiscussWithAI = () => {
    // Build a rich context message to pass to the chat
    const context = {
      form,
      result,
      message: `I just ran an AI risk prediction on the PAIMANA portal. Here are the results:

**Project Parameters:**
- Ministry: ${form.ministry}
- Sector: ${form.sector}
- State: ${form.state}
- Original Cost: ₹${form.original_cost_cr} Cr
- Revised Cost: ₹${form.revised_cost_cr} Cr
- Expenditure: ₹${form.cumulative_expenditure_cr} Cr
- Physical Progress: ${form.physical_progress_pct}%
- Planned Duration: ${form.planned_duration_months} months
- Project Age: ${form.project_age_months} months

**AI Prediction Results:**
- Risk Score: ${result.risk_score}/100
- Risk Category: **${result.risk_category}**
- Cost Overrun Probability: ${result.cost_overrun_probability}%
- Time Overrun Probability: ${result.time_overrun_probability}%
- Predicted Delay: ${result.predicted_delay_months} months

Please give me a deep analysis of this project and what actions should be taken.`
    }
    sessionStorage.setItem('pendingPredictionContext', JSON.stringify(context))
    navigate('/chat')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const payload = {
        ministry: form.ministry,
        sector: form.sector,
        state: form.state,
        original_cost_cr: parseFloat(form.original_cost_cr) || 0,
        revised_cost_cr: parseFloat(form.revised_cost_cr) || 0,
        cumulative_expenditure_cr: parseFloat(form.cumulative_expenditure_cr) || 0,
        physical_progress_pct: parseFloat(form.physical_progress_pct) || 0,
        planned_duration_months: parseFloat(form.planned_duration_months) || 60,
        project_age_months: parseFloat(form.project_age_months) || 36,
      }
      const res = await api.predict(payload)
      setResult(res)
    } catch (err) {
      setError('Prediction failed. Please check your inputs and ensure the backend is running.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const getRiskColor = (category) => {
    switch (category) {
      case 'Critical': return 'var(--risk-critical)'
      case 'High': return 'var(--risk-high)'
      case 'Medium': return 'var(--risk-medium)'
      case 'Low': return 'var(--risk-low)'
      default: return 'var(--text-secondary)'
    }
  }

  const isFormValid = form.ministry && form.sector && form.state &&
    form.original_cost_cr && form.revised_cost_cr &&
    form.cumulative_expenditure_cr && form.physical_progress_pct

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>🧠 AI Risk Simulator & Predictor</h2>
          <p>Enter project parameters from the CUF (Common Upload Form) to get real-time AI predictions.</p>
        </div>
        <button
          onClick={() => {
            if (result) {
              handleDiscussWithAI()
            } else {
              navigate('/chat')
            }
          }}
          style={{
            padding: '10px 22px',
            borderRadius: '14px',
            border: 'none',
            background: 'linear-gradient(135deg, #38bdf8, #a855f7)',
            color: '#fff',
            fontSize: '14px',
            fontWeight: '700',
            fontFamily: 'inherit',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 4px 20px rgba(56, 189, 248, 0.35)',
            transition: 'all 0.2s ease',
            whiteSpace: 'nowrap',
          }}
          onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 8px 28px rgba(56, 189, 248, 0.55)' }}
          onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 20px rgba(56, 189, 248, 0.35)' }}
        >
          <MessageSquare size={16} />
          {result ? 'Discuss with AI' : 'Chat with AI'}
        </button>
      </div>

      {/* Preset Quick-Load Buttons */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '28px', flexWrap: 'wrap' }}>
        {presets.map((p, i) => (
          <button
            key={i}
            onClick={() => handlePreset(p)}
            style={{
              padding: '10px 20px',
              borderRadius: '12px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-glass)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: '600',
              fontFamily: 'inherit',
              transition: 'all 0.18s ease',
            }}
            onMouseEnter={e => { e.target.style.borderColor = 'var(--accent-blue)'; e.target.style.transform = 'translateY(-2px)' }}
            onMouseLeave={e => { e.target.style.borderColor = 'var(--border-color)'; e.target.style.transform = 'translateY(0)' }}
          >
            {p.label}
          </button>
        ))}
        <button
          onClick={handleReset}
          style={{
            padding: '10px 20px',
            borderRadius: '12px',
            border: '1px solid var(--border-color)',
            background: 'transparent',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: '600',
            fontFamily: 'inherit',
            display: 'flex', alignItems: 'center', gap: '6px',
          }}
        >
          <RotateCcw size={14} /> Reset
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: result ? 'repeat(auto-fit, minmax(350px, 1fr))' : '1fr', gap: '28px', alignItems: 'start' }}>
        {/* INPUT FORM */}
        <div className="card">
          <div className="card-header">
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={20} style={{ color: 'var(--accent-blue)' }} />
              Project Parameters (CUF Fields)
            </h3>
          </div>

          <form onSubmit={handleSubmit}>
            {/* Categorical Fields */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px' }}>
              <div>
                <label style={labelStyle}>Ministry / Department</label>
                <select className="filter-select" style={{ width: '100%' }} value={form.ministry} onChange={e => handleChange('ministry', e.target.value)}>
                  <option value="">Select Ministry</option>
                  {options.ministries.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label style={labelStyle}>Sector</label>
                <select className="filter-select" style={{ width: '100%' }} value={form.sector} onChange={e => handleChange('sector', e.target.value)}>
                  <option value="">Select Sector</option>
                  {options.sectors.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label style={labelStyle}>State / Location</label>
                <select className="filter-select" style={{ width: '100%' }} value={form.state} onChange={e => handleChange('state', e.target.value)}>
                  <option value="">Select State</option>
                  {options.states.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>

            {/* Financial Fields */}
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.6px', fontWeight: '700', marginBottom: '10px', marginTop: '8px' }}>
              Financial Parameters
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px' }}>
              <div>
                <label style={labelStyle}>Original Cost (₹ Cr)</label>
                <input type="number" step="0.01" placeholder="e.g. 1200" className="search-input" style={{ width: '100%', paddingLeft: '14px' }}
                  value={form.original_cost_cr} onChange={e => handleChange('original_cost_cr', e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Revised Cost (₹ Cr)</label>
                <input type="number" step="0.01" placeholder="e.g. 1800" className="search-input" style={{ width: '100%', paddingLeft: '14px' }}
                  value={form.revised_cost_cr} onChange={e => handleChange('revised_cost_cr', e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Expenditure (₹ Cr)</label>
                <input type="number" step="0.01" placeholder="e.g. 950" className="search-input" style={{ width: '100%', paddingLeft: '14px' }}
                  value={form.cumulative_expenditure_cr} onChange={e => handleChange('cumulative_expenditure_cr', e.target.value)} />
              </div>
            </div>

            {/* Progress & Timeline */}
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.6px', fontWeight: '700', marginBottom: '10px' }}>
              Progress &amp; Timeline
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '28px' }}>
              <div>
                <label style={labelStyle}>Physical Progress (%)</label>
                <input type="number" step="0.1" min="0" max="100" placeholder="e.g. 45" className="search-input" style={{ width: '100%', paddingLeft: '14px' }}
                  value={form.physical_progress_pct} onChange={e => handleChange('physical_progress_pct', e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Planned Duration (Months)</label>
                <input type="number" placeholder="e.g. 60" className="search-input" style={{ width: '100%', paddingLeft: '14px' }}
                  value={form.planned_duration_months} onChange={e => handleChange('planned_duration_months', e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>Project Age (Months)</label>
                <input type="number" placeholder="e.g. 42" className="search-input" style={{ width: '100%', paddingLeft: '14px' }}
                  value={form.project_age_months} onChange={e => handleChange('project_age_months', e.target.value)} />
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={!isFormValid || loading}
              style={{
                width: '100%',
                padding: '14px',
                borderRadius: '14px',
                border: 'none',
                background: isFormValid ? 'var(--accent-gradient)' : 'rgba(255,255,255,0.08)',
                color: isFormValid ? '#080c14' : 'var(--text-muted)',
                fontSize: '15px',
                fontWeight: '700',
                fontFamily: 'inherit',
                cursor: isFormValid ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '10px',
                transition: 'all 0.25s ease',
                boxShadow: isFormValid ? '0 4px 24px rgba(56, 189, 248, 0.35)' : 'none',
              }}
            >
              {loading ? (
                <><div className="loading-spinner" style={{ width: '20px', height: '20px', marginRight: '0' }}></div> Running AI Inference...</>
              ) : (
                <><Zap size={18} /> Predict Risk with AI</>
              )}
            </button>

            {error && (
              <div style={{ marginTop: '16px', padding: '14px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)', color: 'var(--risk-critical)', fontSize: '14px' }}>
                {error}
              </div>
            )}
          </form>
        </div>

        {/* RESULTS */}
        {result && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Risk Score Gauge */}
            <div className="card" style={{ textAlign: 'center', padding: '32px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: '700', marginBottom: '12px' }}>
                Composite Risk Score
              </div>
              <div style={{
                fontSize: '64px', fontWeight: '800', letterSpacing: '-2px',
                color: getRiskColor(result.risk_category),
                textShadow: `0 0 40px ${getRiskColor(result.risk_category)}40`,
              }}>
                {result.risk_score}
              </div>
              <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '12px' }}>out of 100</div>
              <span className={`risk-badge ${result.risk_category.toLowerCase()}`} style={{ fontSize: '14px', padding: '8px 24px' }}>
                {result.risk_category} Risk
              </span>
            </div>

            {/* Probability Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div className="stat-card">
                <div className="stat-icon red"><TrendingUp size={22} /></div>
                <div className="stat-label">Cost Overrun Risk</div>
                <div className="stat-value" style={{ color: result.cost_overrun_probability > 60 ? 'var(--risk-critical)' : result.cost_overrun_probability > 40 ? 'var(--risk-medium)' : 'var(--risk-low)' }}>
                  {result.cost_overrun_probability}%
                </div>
                <div className="stat-sub">{result.cost_overrun_prediction ? 'Overrun Predicted' : 'Within Budget'}</div>
              </div>
              <div className="stat-card">
                <div className="stat-icon orange"><Clock size={22} /></div>
                <div className="stat-label">Schedule Delay Risk</div>
                <div className="stat-value" style={{ color: result.time_overrun_probability > 60 ? 'var(--risk-critical)' : result.time_overrun_probability > 40 ? 'var(--risk-medium)' : 'var(--risk-low)' }}>
                  {result.time_overrun_probability}%
                </div>
                <div className="stat-sub">
                  {result.time_overrun_prediction ? `+${result.predicted_delay_months} months delay` : 'On Schedule'}
                </div>
              </div>
            </div>

            {/* Warnings */}
            {result.warnings && result.warnings.length > 0 && (
              <div className="card">
                <h3 style={{ fontSize: '16px', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <AlertTriangle size={18} style={{ color: 'var(--risk-medium)' }} /> Early Warning Alerts
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {result.warnings.map((w, i) => (
                    <div key={i} className="alert-item">
                      <div className={`alert-icon ${w.severity.toLowerCase()}`}>
                        {w.type.includes('COST') ? <TrendingUp size={18} /> : w.type.includes('TIME') ? <Clock size={18} /> : <AlertTriangle size={18} />}
                      </div>
                      <div className="alert-content" style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <h4 style={{ fontSize: '14px' }}>{w.type.split('_').join(' ')}</h4>
                          <span className={`severity-badge ${w.severity.toLowerCase()}`}>{w.severity}</span>
                        </div>
                        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>{w.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {result.recommendations && (
              <div className="card">
                <h3 style={{ fontSize: '16px', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Shield size={18} style={{ color: 'var(--accent-blue)' }} /> Prescriptive Recommendations
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {result.recommendations.map((r, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'flex-start', gap: '10px',
                      padding: '12px 16px', borderRadius: '10px',
                      background: 'rgba(56, 189, 248, 0.06)',
                      border: '1px solid rgba(56, 189, 248, 0.15)',
                      fontSize: '14px', color: 'var(--text-primary)', lineHeight: '1.5',
                    }}>
                      <ChevronRight size={16} style={{ color: 'var(--accent-blue)', flexShrink: 0, marginTop: '2px' }} />
                      {r}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Key Risk Drivers */}
            {result.top_drivers && (
              <div className="card">
                <h3 style={{ fontSize: '16px', marginBottom: '14px' }}>Key Risk Drivers</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {result.top_drivers.map((d, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--border-color)' }}>
                      <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>{d.feature}</span>
                      <span style={{ fontSize: '15px', fontWeight: '700', fontFamily: "'JetBrains Mono', monospace" }}>{d.value}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {/* Discuss with AI Button */}
            {result && (
              <div style={{
                background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.12) 0%, rgba(168, 85, 247, 0.12) 100%)',
                border: '1px solid rgba(56, 189, 248, 0.35)',
                borderRadius: '20px',
                padding: '24px',
                textAlign: 'center',
                position: 'relative',
                overflow: 'hidden',
              }}>
                {/* Glow effect */}
                <div style={{
                  position: 'absolute', top: '-30px', right: '-30px',
                  width: '100px', height: '100px',
                  background: 'radial-gradient(circle, rgba(168, 85, 247, 0.3), transparent)',
                  borderRadius: '50%', pointerEvents: 'none',
                }} />
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', marginBottom: '8px' }}>
                  <Bot size={22} style={{ color: 'var(--accent-blue)' }} />
                  <h4 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)' }}>Want a deeper analysis?</h4>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px', lineHeight: '1.5' }}>
                  Send this prediction to the AI Assistant for an in-depth conversation, audit recommendations, and what-if scenarios.
                </p>
                <button
                  onClick={handleDiscussWithAI}
                  style={{
                    padding: '12px 28px',
                    borderRadius: '14px',
                    border: 'none',
                    background: 'linear-gradient(135deg, #38bdf8, #a855f7)',
                    color: '#fff',
                    fontSize: '14px',
                    fontWeight: '700',
                    fontFamily: 'inherit',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                    boxShadow: '0 4px 20px rgba(56, 189, 248, 0.4)',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 8px 28px rgba(56, 189, 248, 0.55)' }}
                  onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 20px rgba(56, 189, 248, 0.4)' }}
                >
                  <MessageSquare size={16} />
                  Discuss with AI Assistant
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const labelStyle = {
  fontSize: '12px',
  color: 'var(--text-muted)',
  fontWeight: '600',
  display: 'block',
  marginBottom: '6px',
  letterSpacing: '0.3px',
}
