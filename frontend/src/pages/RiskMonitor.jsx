import { useState, useEffect } from 'react'
import { api } from '../api'
import { Search, Filter, Shield, AlertTriangle, ArrowRight } from 'lucide-react'

function RiskBadge({ score }) {
  if (score >= 80) return <span className="risk-badge critical">Critical ({score})</span>
  if (score >= 60) return <span className="risk-badge high">High ({score})</span>
  if (score >= 30) return <span className="risk-badge medium">Medium ({score})</span>
  return <span className="risk-badge low">Low ({score})</span>
}

export default function RiskMonitor() {
  const [projects, setProjects] = useState([])
  const [filters, setFilters] = useState({ sectors: [], ministries: [], states: [] })
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)

  const [search, setSearch] = useState('')
  const [selectedSector, setSelectedSector] = useState('')
  const [selectedRisk, setSelectedRisk] = useState('')

  useEffect(() => {
    api.getFilters().then(setFilters).catch(console.error)
  }, [])

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const res = await api.getProjects({
          page,
          page_size: 20,
          sector: selectedSector,
          risk_category: selectedRisk,
          sort_by: 'risk_score',
          sort_order: 'desc'
        })
        setProjects(res.data || [])
        setTotalPages(res.total_pages || 1)
        setTotal(res.total || 0)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    const timer = setTimeout(load, 300)
    return () => clearTimeout(timer)
  }, [page, search, selectedSector, selectedRisk])

  const formatCrore = (val) => val ? `₹${Number(val).toFixed(0)} Cr` : '-'

  return (
    <div>
      <div className="page-header">
        <h2>🛡️ Project Risk Monitor</h2>
        <p>Prioritize interventions based on AI-generated risk scores (0-100)</p>
      </div>

      <div className="filter-bar">
        <div className="search-wrapper">
          <Search size={18} />
          <input
            type="text"
            className="search-input"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="filter-select"
          value={selectedSector}
          onChange={(e) => { setSelectedSector(e.target.value); setPage(1); }}
        >
          <option value="">All Sectors</option>
          {filters.sectors.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          className="filter-select"
          value={selectedRisk}
          onChange={(e) => { setSelectedRisk(e.target.value); setPage(1); }}
        >
          <option value="">All Risk Levels</option>
          <option value="Critical">Critical (80-100)</option>
          <option value="High">High (60-79)</option>
          <option value="Medium">Medium (30-59)</option>
          <option value="Low">Low (0-29)</option>
        </select>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>High-Risk Projects</h3>
          <span className="card-badge">{total} Found</span>
        </div>
        
        {loading ? (
          <div className="loading"><div className="loading-spinner"></div> Loading projects...</div>
        ) : (
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Project Name</th>
                  <th>Sector</th>
                  <th>Cost (Orig → Rev)</th>
                  <th>Progress</th>
                  <th>ML Risk Score</th>
                  <th>Probabilities</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((p, i) => (
                  <tr key={i} className="animate-in">
                    <td style={{ maxWidth: '300px', whiteSpace: 'normal', lineHeight: '1.4' }}>
                      <div style={{ fontWeight: '500' }}>{p.project_name}</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        {p.agency} • {p.state}
                      </div>
                    </td>
                    <td>{p.sector}</td>
                    <td>
                      <div>{formatCrore(p.original_cost_cr)}</div>
                      <div style={{ color: p.has_cost_overrun ? 'var(--risk-critical)' : 'var(--text-muted)', fontSize: '12px' }}>
                        → {formatCrore(p.revised_cost_cr)}
                        {p.has_cost_overrun && ` (+${p.cost_overrun_pct}%)`}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '60px' }}>{p.physical_progress_pct}%</div>
                        <div className="progress-bar" style={{ width: '80px' }}>
                          <div
                            className={`progress-fill ${p.physical_progress_pct < 30 ? 'red' : p.physical_progress_pct < 60 ? 'yellow' : 'green'}`}
                            style={{ width: `${p.physical_progress_pct}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td><RiskBadge score={p.risk_score} /></td>
                    <td>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Cost: <span style={{ color: p.cost_overrun_probability > 50 ? 'var(--risk-critical)' : 'inherit' }}>{p.cost_overrun_probability}%</span>
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Time: <span style={{ color: p.time_overrun_probability > 50 ? 'var(--risk-critical)' : 'inherit' }}>{p.time_overrun_probability}%</span>
                      </div>
                    </td>
                    <td>
                      <button style={{
                        background: 'transparent',
                        border: '1px solid var(--border-color)',
                        color: 'var(--text-primary)',
                        padding: '6px 12px',
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        fontSize: '13px'
                      }}>
                        View <ArrowRight size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
                {projects.length === 0 && (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '40px' }}>
                      No projects found matching the criteria.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {!loading && totalPages > 1 && (
          <div className="pagination">
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
            <span className="page-info">Page {page} of {totalPages}</span>
            <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Next</button>
          </div>
        )}
      </div>
    </div>
  )
}
