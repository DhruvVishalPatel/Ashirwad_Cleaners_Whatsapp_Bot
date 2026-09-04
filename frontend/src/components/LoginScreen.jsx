import React, { useState } from 'react';
import { Lock, User } from 'lucide-react';
import { api, setAuthToken } from '../api';

export default function LoginScreen({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await api.login(username, password);
      setAuthToken(res.token);
      onLoginSuccess();
    } catch (err) {
      setError(err.message || 'Incorrect username or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1.5rem',
      background: 'radial-gradient(circle at top right, rgba(220, 38, 38, 0.15), transparent 40%), radial-gradient(circle at bottom left, rgba(239, 68, 68, 0.15), transparent 40%)'
    }}>
      <div className="glass-card" style={{ width: '100%', maxWidth: '420px', padding: '2.5rem 2rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <img
            src="/logo.png"
            alt="Ashirwad Cleaners Logo"
            style={{
              height: '76px',
              width: 'auto',
              marginBottom: '1rem',
              filter: 'drop-shadow(0 4px 16px rgba(220, 38, 38, 0.4))'
            }}
          />
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700, marginBottom: '0.25rem', color: 'var(--text-primary)' }}>
            Ashirwad Cleaners
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Administrator Portal Sign In
          </p>
        </div>

        {error && (
          <div className="alert-banner alert-error">
            <span>❌</span> {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Username</label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                className="form-control"
                style={{ width: '100%', paddingLeft: '2.5rem' }}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter admin username"
                required
              />
              <User size={18} style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: '1.5rem' }}>
            <label className="form-label">Password</label>
            <div style={{ position: 'relative' }}>
              <input
                type="password"
                className="form-control"
                style={{ width: '100%', paddingLeft: '2.5rem' }}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                required
              />
              <Lock size={18} style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{ width: '100%', padding: '0.75rem', fontSize: '1rem' }}
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
