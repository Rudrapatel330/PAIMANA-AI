const API_BASE = window.location.hostname === 'localhost' 
  ? 'http://localhost:8000/api' 
  : '/api'

async function fetchAPI(endpoint, params = {}) {
  const url = new URL(`${API_BASE}${endpoint}`)
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      url.searchParams.append(key, value)
    }
  })
  
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return await res.json()
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error)
    throw error
  }
}

async function postAPI(endpoint, body) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return await res.json()
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error)
    throw error
  }
}

export const api = {
  getSummary: () => fetchAPI('/summary'),
  getProjects: (params) => fetchAPI('/projects', params),
  getProjectDetail: (idx) => fetchAPI(`/projects/${idx}`),
  getAlerts: (params) => fetchAPI('/alerts', params),
  getSectors: () => fetchAPI('/analytics/sectors'),
  getRiskDistribution: () => fetchAPI('/analytics/risk-distribution'),
  getCostDrivers: () => fetchAPI('/analytics/cost-drivers'),
  getModelComparison: () => fetchAPI('/analytics/model-comparison'),
  getMinistryOverview: () => fetchAPI('/analytics/ministry-overview'),
  getOverrunTrends: () => fetchAPI('/analytics/overrun-trends'),
  getFilters: () => fetchAPI('/filters'),
  getPredictOptions: () => fetchAPI('/predict/options'),
  predict: (data) => postAPI('/predict', data),
  chat: (message, history = []) => postAPI('/chat', { message, history }),
  getChatSuggestions: () => fetchAPI('/chat/suggestions'),
}

