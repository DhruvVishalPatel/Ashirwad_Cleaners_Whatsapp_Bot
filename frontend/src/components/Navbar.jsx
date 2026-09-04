import React from 'react';
import { RefreshCw, LogOut, Moon, Sun, Radio } from 'lucide-react';

export default function Navbar({ onRefresh, onLogout, theme, toggleTheme, wsConnected }) {
  return (
    <div className="navbar">
      <div className="brand-title">
        <img src="/logo.png" alt="Ashirwad Cleaners" className="brand-logo" />
        <span>Ashirwad Cleaners</span>
      </div>

      <div className="nav-actions">
        {/* Real-time WebSocket connection status badge */}
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.4rem',
          fontSize: '0.8rem',
          fontWeight: 600,
          padding: '0.3rem 0.65rem',
          borderRadius: '20px',
          background: wsConnected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
          color: wsConnected ? '#34d399' : '#f87171',
          border: wsConnected ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
          marginRight: '0.5rem'
        }}>
          <Radio size={14} className={wsConnected ? 'pulse-icon' : ''} />
          {wsConnected ? 'Live Real-Time' : 'Connecting...'}
        </div>

        <button className="btn btn-secondary btn-sm" onClick={onRefresh} title="Refresh Data">
          <RefreshCw size={15} /> Sync Data
        </button>

        <button className="btn btn-secondary btn-sm" onClick={toggleTheme} title="Toggle Theme">
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>

        <button className="btn btn-danger btn-sm" onClick={onLogout} title="Log Out">
          <LogOut size={15} /> Log Out
        </button>
      </div>
    </div>
  );
}
