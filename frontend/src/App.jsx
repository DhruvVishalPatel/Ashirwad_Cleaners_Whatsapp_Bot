import React, { useState, useEffect, useCallback, useRef } from 'react';
import Navbar from './components/Navbar';
import Scoreboard from './components/Scoreboard';
import OrderManagement from './components/OrderManagement';
import CustomerDirectory from './components/CustomerDirectory';
import StaffManager from './components/StaffManager';
import CatalogManager from './components/CatalogManager';
import LoginScreen from './components/LoginScreen';
import { api, getAuthToken, setAuthToken } from './api';
import { ShoppingBag, Users, Truck, Tag, Bell } from 'lucide-react';

function playNewOrderChime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.2);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.6);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.6);
  } catch (e) {
    // Audio context requires user interaction first
  }
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
  const [activeTab, setActiveTab] = useState('orders');

  // Real-time WebSocket State
  const [wsConnected, setWsConnected] = useState(false);
  const [toastNotification, setToastNotification] = useState(null);
  const wsRef = useRef(null);

  // Data states
  const [analytics, setAnalytics] = useState(null);
  const [orders, setOrders] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [runners, setRunners] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [loading, setLoading] = useState(true);

  // Apply theme to body
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  // Verify Auth on mount
  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      setIsAuthenticated(true);
    }
    setLoading(false);
  }, []);

  // Fetch data function
  const fetchAllData = useCallback(async (showAllOrders = false) => {
    try {
      const [analyticsRes, ordersRes, customersRes, runnersRes, catalogRes] = await Promise.all([
        api.getAnalytics().catch(() => null),
        api.getOrders(showAllOrders).catch(() => []),
        api.getCustomers().catch(() => []),
        api.getRunners().catch(() => []),
        api.getCatalog().catch(() => []),
      ]);

      if (analyticsRes) setAnalytics(analyticsRes);
      setOrders(ordersRes);
      setCustomers(customersRes);
      setRunners(runnersRes);
      setCatalog(catalogRes);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchAllData();
    }
  }, [isAuthenticated, fetchAllData]);

  // WebSocket Real-time Connection
  useEffect(() => {
    if (!isAuthenticated) return;

    let wsHost = window.location.host;
    if (window.location.port === '5173') {
      wsHost = `${window.location.hostname}:8000`;
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${wsHost}/api/v1/ws`;

    let socket;
    let pingInterval;

    const connectWebSocket = () => {
      socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        setWsConnected(true);
        pingInterval = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send('ping');
          }
        }, 20000);
      };

      socket.onmessage = (event) => {
        try {
          if (event.data === 'pong') return;
          const msg = JSON.parse(event.data);
          
          if (msg.type === 'ORDER_CREATED') {
            playNewOrderChime();
            setToastNotification({
              title: '🎉 NEW ORDER RECEIVED!',
              body: `Order #${msg.data.order_id} (${msg.data.item_count} items - ${msg.data.service_category || 'Dry Clean'})`,
            });
            fetchAllData();
          } else if (msg.type === 'ORDER_UPDATED') {
            setToastNotification({
              title: '🔄 ORDER UPDATED',
              body: `Order #${msg.data.order_id} state updated.`,
            });
            fetchAllData();
          }
        } catch (e) {
          // Non-JSON message
        }
      };

      socket.onclose = () => {
        setWsConnected(false);
        clearInterval(pingInterval);
        // Auto-reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };

      socket.onerror = () => {
        socket.close();
      };
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      clearInterval(pingInterval);
    };
  }, [isAuthenticated, fetchAllData]);

  // Toast notification timer
  useEffect(() => {
    if (toastNotification) {
      const timer = setTimeout(() => {
        setToastNotification(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [toastNotification]);

  const handleLogout = () => {
    setAuthToken('');
    setIsAuthenticated(false);
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ fontSize: '1.2rem', color: 'var(--text-secondary)' }}>Loading Ashirwad Portal...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginScreen onLoginSuccess={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="app-container" style={{ position: 'relative' }}>
      {/* Toast Notification Banner */}
      {toastNotification && (
        <div style={{
          position: 'fixed',
          top: '20px',
          right: '20px',
          zIndex: 9999,
          background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
          color: '#fff',
          padding: '1rem 1.25rem',
          borderRadius: 'var(--radius-lg)',
          boxShadow: '0 10px 30px rgba(99, 102, 241, 0.4)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          animation: 'slideIn 0.3s ease-out'
        }}>
          <Bell size={24} />
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{toastNotification.title}</div>
            <div style={{ fontSize: '0.82rem', opacity: 0.9 }}>{toastNotification.body}</div>
          </div>
        </div>
      )}

      <Navbar
        onRefresh={() => fetchAllData()}
        onLogout={handleLogout}
        theme={theme}
        toggleTheme={toggleTheme}
        wsConnected={wsConnected}
      />

      <Scoreboard analytics={analytics} />

      {/* Main Tabs Header */}
      <div className="tabs-header">
        <button
          className={`tab-btn ${activeTab === 'orders' ? 'active' : ''}`}
          onClick={() => setActiveTab('orders')}
        >
          <ShoppingBag size={18} /> 📋 Active Orders
        </button>

        <button
          className={`tab-btn ${activeTab === 'customers' ? 'active' : ''}`}
          onClick={() => setActiveTab('customers')}
        >
          <Users size={18} /> 👥 Customer Database
        </button>

        <button
          className={`tab-btn ${activeTab === 'runners' ? 'active' : ''}`}
          onClick={() => setActiveTab('runners')}
        >
          <Truck size={18} /> 🛵 Staff Settings
        </button>

        <button
          className={`tab-btn ${activeTab === 'catalog' ? 'active' : ''}`}
          onClick={() => setActiveTab('catalog')}
        >
          <Tag size={18} /> 🏷️ Price Catalog Manager
        </button>
      </div>

      {/* Tab Content */}
      <div className="glass-card" style={{ minHeight: '500px' }}>
        {activeTab === 'orders' && (
          <OrderManagement
            orders={orders}
            runners={runners}
            catalog={catalog}
            onRefresh={(showAll) => fetchAllData(showAll)}
          />
        )}

        {activeTab === 'customers' && (
          <CustomerDirectory
            customers={customers}
            onRefresh={() => fetchAllData()}
          />
        )}

        {activeTab === 'runners' && (
          <StaffManager
            runners={runners}
            onRefresh={() => fetchAllData()}
          />
        )}

        {activeTab === 'catalog' && (
          <CatalogManager
            catalog={catalog}
            onRefresh={() => fetchAllData()}
          />
        )}
      </div>
    </div>
  );
}
