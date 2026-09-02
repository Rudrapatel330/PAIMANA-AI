import { useState, useEffect } from 'react'
import { api } from '../api'
import { AlertTriangle, Clock, TrendingUp } from 'lucide-react'

export default function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [selectedSeverity, setSelectedSeverity] = useState('')
  const [selectedType, setSelectedType] = useState('')

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const res = await api.getAlerts({
          page,
          page_size: 20,
          severity: selectedSeverity,
          alert_type: selectedType
        })
        setAlerts(res.data || [])
        setSummary(res.summary)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [page, selectedSeverity, selectedType])

  const getAlertIcon = (type) => {
    if (type.includes('TIME') || type.includes('STAGNATION')) return <Clock size={20} />
    if (type.includes('COST') || type.includes('GAP')) return <TrendingUp size={20} />
    return <AlertTriangle size={20} />
  }

  const formatType = (type) => {
    return type.split('_').map(w => w.charAt(0) + w.slice(1).toLowerCase()).join(' ')
  }

  return (
    <div>
      <div className="page-header">
        <h2>⚠️ Early Warning Alert System</h2>
        <p>Proactive alerts for cost escalation, schedule delays, and implementation risks.</p>
      </div>

      <div className="filter-bar">
        <select
          className="filter-select"
          value={selectedSeverity}
          onChange={(e) => { setSelectedSeverity(e.target.value); setPage(1); }}
        >
          <option value="">All Severities</option>
          <option value="CRITICAL">Critical</option>
          <option value="WARNING">Warning</option>
        </select>
        
        <select
          className="filter-select"
          value={selectedType}
          onChange={(e) => { setSelectedType(e.target.value); setPage(1); }}
        >
          <option value="">All Alert Types</option>
          <option value="COST_ESCALATION">Cost Escalation</option>
          <option value="TIME_OVERRUN">Time Overrun</option>
          <option value="EXPENDITURE_LAG">Expenditure Lag</option>
          <option value="PROGRESS_STAGNATION">Progress Stagnation</option>
          <option value="MULTI_MONTH_STAGNATION">Multi-Month Stagnation</option>
          <option value="PF_GAP">Physical-Financial Gap</option>
          <option value="HIGH_RISK_ML">High Risk (ML)</option>
        </select>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 350px), 1fr))', gap: '24px', alignItems: 'start' }}>
        <div>
          <div className="card" style={{ minHeight: '520px' }}>
            <div className="card-header">
              <h3>Active Alerts</h3>
              <span className="card-badge">{alerts.length} on this page</span>
            </div>
            
            {loading ? (
              <div className="loading" style={{ minHeight: '380px' }}>
                <div className="loading-spinner"></div> Loading alerts...
              </div>
            ) : alerts.length === 0 ? (
              <div style={{ padding: '60px 40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                No alerts found matching your criteria.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {alerts.map((alert, i) => (
                  <div
                    key={i}
                    className="alert-item"
                  >
                    <div className={`alert-icon ${alert.severity.toLowerCase()}`}>
                      {getAlertIcon(alert.type)}
                    </div>
                    <div className="alert-content" style={{ flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <h4>{formatType(alert.type)}</h4>
                          <div style={{ color: 'var(--text-primary)', fontSize: '14px', marginBottom: '6px', fontWeight: '500' }}>
                            {alert.project_name}
                          </div>
                          <p>{alert.message}</p>
                          <div className="alert-meta">
                            {alert.sector} • {alert.ministry} • ML Risk Score: {alert.risk_score}
                          </div>
                        </div>
                        <span className={`severity-badge ${alert.severity.toLowerCase()}`}>
                          {alert.severity}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {!loading && alerts.length > 0 && (
              <div className="pagination">
                <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
                <span className="page-info">Page {page}</span>
                <button onClick={() => setPage(p => p + 1)}>Next</button>
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="card">
            <h3 style={{ marginBottom: '18px', fontSize: '16px' }}>Summary</h3>
            
            {summary ? (
              <>
                <div style={{ marginBottom: '24px' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.6px', fontWeight: '700', marginBottom: '10px' }}>
                    By Severity
                  </div>
                  {Object.entries(summary.by_severity || {}).map(([sev, count]) => (
                    <div key={sev} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px', fontSize: '14px' }}>
                      <span style={{ color: sev === 'CRITICAL' ? 'var(--risk-critical)' : 'var(--risk-medium)', fontWeight: '600' }}>
                        {sev}
                      </span>
                      <span style={{ fontWeight: '700' }}>{count}</span>
                    </div>
                  ))}
                </div>

                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.6px', fontWeight: '700', marginBottom: '10px' }}>
                    By Alert Type
                  </div>
                  {Object.entries(summary.by_type || {})
                    .sort((a, b) => b[1] - a[1])
                    .map(([type, count]) => (
                    <div key={type} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '9px', fontSize: '13px' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>{formatType(type)}</span>
                      <span style={{ fontWeight: '600' }}>{count}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Loading summary...</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
