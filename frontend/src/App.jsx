import { BrowserRouter as Router, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { LayoutDashboard, Shield, AlertTriangle, BarChart3, Menu, X, Zap, MessageCircle } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import Dashboard from './pages/Dashboard'
import RiskMonitor from './pages/RiskMonitor'
import Alerts from './pages/Alerts'
import Analytics from './pages/Analytics'
import Predictor from './pages/Predictor'
import ChatAssistant from './pages/ChatAssistant'
import './index.css'

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/predict', label: 'AI Predictor', icon: Zap },
  { path: '/chat', label: 'AI Assistant', icon: MessageCircle },
  { path: '/risk', label: 'Risk Monitor', icon: Shield },
  { path: '/alerts', label: 'Early Warnings', icon: AlertTriangle },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
]

function PageWrapper({ children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      style={{ width: '100%' }}
    >
      {children}
    </motion.div>
  )
}

function AnimatedRoutes() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<PageWrapper><Dashboard /></PageWrapper>} />
        <Route path="/predict" element={<PageWrapper><Predictor /></PageWrapper>} />
        <Route path="/chat" element={<PageWrapper><ChatAssistant /></PageWrapper>} />
        <Route path="/risk" element={<PageWrapper><RiskMonitor /></PageWrapper>} />
        <Route path="/alerts" element={<PageWrapper><Alerts /></PageWrapper>} />
        <Route path="/analytics" element={<PageWrapper><Analytics /></PageWrapper>} />
      </Routes>
    </AnimatePresence>
  )
}

function Sidebar({ isOpen, onClose }) {
  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-logo">
        <div className="logo-icon">🏗️</div>
        <div>
          <h1>PAIMANA AI</h1>
          <span>Infrastructure Monitoring</span>
        </div>
      </div>
      <nav className="nav-links">
        {navItems.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            onClick={onClose}
          >
            <item.icon />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '16px', marginTop: 'auto' }}>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', padding: '0 8px', lineHeight: '1.4' }}>
          Ministry of Statistics &<br />Programme Implementation
        </div>
      </div>
    </aside>
  )
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <Router>
      <div className="ambient-background">
        <div className="orb orb-1"></div>
        <div className="orb orb-2"></div>
        <div className="orb orb-3"></div>
      </div>
      <div className="app-layout">
        <button className="mobile-menu-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
          {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <main className="main-content">
          <AnimatedRoutes />
        </main>
      </div>
    </Router>
  )
}
