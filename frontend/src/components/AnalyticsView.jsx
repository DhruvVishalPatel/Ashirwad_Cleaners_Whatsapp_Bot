import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  ShoppingBag,
  Users,
  Truck,
  Calendar,
  CreditCard,
  CheckCircle2,
  Clock,
  Sparkles,
  RefreshCw,
  Tag,
  ArrowUpRight,
  Store,
  MapPin,
  MessageSquare
} from 'lucide-react';
import { api } from '../api';

export default function AnalyticsView({ wsEvent }) {
  const [timeframe, setTimeframe] = useState('weekly');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAnalytics = useCallback(async (tf = timeframe) => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getDetailedAnalytics(tf);
      setData(res);
    } catch (err) {
      console.error('Failed to load analytics:', err);
      setError(err.message || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }, [timeframe]);

  useEffect(() => {
    fetchAnalytics(timeframe);
  }, [timeframe, fetchAnalytics]);

  // Refresh if an order is created or updated over WebSocket
  useEffect(() => {
    if (wsEvent && (wsEvent.type === 'ORDER_CREATED' || wsEvent.type === 'ORDER_UPDATED')) {
      fetchAnalytics(timeframe);
    }
  }, [wsEvent, timeframe, fetchAnalytics]);

  const timeframes = [
    { key: 'daily', label: '📅 Daily (Today)' },
    { key: 'weekly', label: '📊 Weekly (7 Days)' },
    { key: 'monthly', label: '🗓️ Monthly (30 Days)' },
    { key: 'quarterly', label: '📈 Quarterly (90 Days)' },
    { key: 'annual', label: '🌟 Annual (365 Days)' },
    { key: 'all', label: '♾️ All Time' },
  ];

  if (loading && !data) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        <RefreshCw size={28} className="pulse-icon" style={{ animation: 'spin 1.5s linear infinite' }} />
        <p style={{ marginTop: '1rem', fontWeight: 600 }}>Calculating Store Analytics & Reports...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--danger)' }}>
        <p>⚠️ {error}</p>
        <button className="btn btn-secondary btn-sm" onClick={() => fetchAnalytics(timeframe)} style={{ marginTop: '1rem' }}>
          Retry
        </button>
      </div>
    );
  }

  const kpis = data?.kpis || {};
  const channels = data?.channels || {};
  const payments = data?.payments || {};
  const funnel = data?.funnel || {};
  const services = data?.services || {};
  const topGarments = data?.top_garments || [];
  const customers = data?.customers || {};
  const trends = data?.trends || [];

  // Calculate highest revenue in trend for scaling bars
  const maxTrendRevenue = Math.max(...trends.map((t) => t.revenue || 0), 1);
  const totalServiceCount = Object.values(services).reduce((a, b) => a + b, 0) || 1;

  return (
    <div className="analytics-view" style={{ padding: '0.5rem 0' }}>
      {/* Header & Timeframe Selector Bar */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '1rem',
        marginBottom: '1.75rem',
        borderBottom: '1px solid var(--border-color)',
        paddingBottom: '1.25rem'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              Business Analytics & Performance
            </h2>
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              padding: '0.2rem 0.6rem',
              borderRadius: '20px',
              background: 'rgba(99, 102, 241, 0.15)',
              color: '#818cf8',
              border: '1px solid rgba(99, 102, 241, 0.3)'
            }}>
              Period: {data?.period_label}
            </span>
          </div>
          <p style={{ margin: '0.35rem 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Real-time financial, logistical, and garment throughput intelligence for Manager Faizan.
          </p>
        </div>

        {/* Timeframe Buttons */}
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.4rem',
          background: 'var(--bg-secondary)',
          padding: '0.3rem',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-color)'
        }}>
          {timeframes.map((tf) => (
            <button
              key={tf.key}
              onClick={() => setTimeframe(tf.key)}
              style={{
                border: 'none',
                background: timeframe === tf.key ? 'var(--primary)' : 'transparent',
                color: timeframe === tf.key ? '#fff' : 'var(--text-secondary)',
                padding: '0.45rem 0.85rem',
                borderRadius: 'var(--radius-sm)',
                fontWeight: timeframe === tf.key ? 700 : 500,
                fontSize: '0.82rem',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: timeframe === tf.key ? '0 2px 8px rgba(99, 102, 241, 0.3)' : 'none'
              }}
            >
              {tf.label}
            </button>
          ))}
          <button
            onClick={() => fetchAnalytics(timeframe)}
            title="Refresh Analytics"
            style={{
              border: 'none',
              background: 'transparent',
              color: 'var(--text-muted)',
              padding: '0.45rem 0.6rem',
              cursor: 'pointer',
              borderRadius: 'var(--radius-sm)'
            }}
          >
            <RefreshCw size={14} className={loading ? 'pulse-icon' : ''} />
          </button>
        </div>
      </div>

      {/* 1. TOP EXECUTIVE KPI CARDS */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
        gap: '1rem',
        marginBottom: '1.5rem'
      }}>
        {/* Total Billed Revenue */}
        <div className="glass-card" style={{ padding: '1.25rem', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Total Billed Revenue
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.35rem' }}>
                ₹{kpis.total_revenue?.toLocaleString('en-IN')}
              </div>
            </div>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              background: 'rgba(16, 185, 129, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#10b981'
            }}>
              <DollarSign size={22} />
            </div>
          </div>
          <div style={{
            display: 'flex',
            gap: '0.6rem',
            marginTop: '0.85rem',
            paddingTop: '0.75rem',
            borderTop: '1px solid var(--border-color)',
            fontSize: '0.76rem'
          }}>
            <span style={{ color: '#34d399', fontWeight: 600 }}>
              ✓ ₹{kpis.paid_revenue?.toLocaleString('en-IN')} Paid
            </span>
            <span style={{ color: 'var(--text-muted)' }}>•</span>
            <span style={{ color: '#fbbf24', fontWeight: 600 }}>
              ⏳ ₹{kpis.pending_revenue?.toLocaleString('en-IN')} Pending
            </span>
          </div>
        </div>

        {/* Total Orders & Channel Ratio */}
        <div className="glass-card" style={{ padding: '1.25rem', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Orders Placed
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.35rem' }}>
                {kpis.total_orders || 0}
              </div>
            </div>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              background: 'rgba(99, 102, 241, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#6366f1'
            }}>
              <ShoppingBag size={22} />
            </div>
          </div>
          <div style={{
            display: 'flex',
            gap: '0.6rem',
            marginTop: '0.85rem',
            paddingTop: '0.75rem',
            borderTop: '1px solid var(--border-color)',
            fontSize: '0.76rem'
          }}>
            <span style={{ color: '#818cf8', fontWeight: 600 }}>
              🛵 {channels.pickup?.orders || 0} Pickup ({channels.pickup?.share_pct || 0}%)
            </span>
            <span style={{ color: 'var(--text-muted)' }}>•</span>
            <span style={{ color: '#c084fc', fontWeight: 600 }}>
              🏬 {channels.store_drop?.orders || 0} Walk-in ({channels.store_drop?.share_pct || 0}%)
            </span>
          </div>
        </div>

        {/* Garments Cleaned & Average Order Value */}
        <div className="glass-card" style={{ padding: '1.25rem', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Garments Processed
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.35rem' }}>
                {kpis.total_garments || 0} <span style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-muted)' }}>pcs</span>
              </div>
            </div>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              background: 'rgba(236, 72, 153, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ec4899'
            }}>
              <Sparkles size={22} />
            </div>
          </div>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: '0.85rem',
            paddingTop: '0.75rem',
            borderTop: '1px solid var(--border-color)',
            fontSize: '0.76rem',
            color: 'var(--text-secondary)'
          }}>
            <span>Avg Order Value:</span>
            <strong style={{ color: 'var(--text-primary)' }}>₹{kpis.avg_order_value || 0}</strong>
          </div>
        </div>

        {/* Customer Base & Repeat Rate */}
        <div className="glass-card" style={{ padding: '1.25rem', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Customer Retention
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.35rem' }}>
                {customers.repeat_rate_pct || 0}%
              </div>
            </div>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              background: 'rgba(14, 165, 233, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#0ea5e9'
            }}>
              <Users size={22} />
            </div>
          </div>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: '0.85rem',
            paddingTop: '0.75rem',
            borderTop: '1px solid var(--border-color)',
            fontSize: '0.76rem',
            color: 'var(--text-secondary)'
          }}>
            <span>{customers.repeat_customers || 0} repeat of {customers.total_registered || 0} total</span>
            <span style={{ color: '#34d399', fontWeight: 600 }}>Loyal Base</span>
          </div>
        </div>
      </div>

      {/* 2. TIMELINE REVENUE & ORDERS TREND BAR CHART */}
      <div className="glass-card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <TrendingUp size={18} color="#6366f1" /> Revenue & Order Trend ({data?.period_label})
            </h3>
            <p style={{ margin: '0.2rem 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Breakdown of incoming orders and billed amounts across this timeframe.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '1rem', fontSize: '0.8rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ width: '12px', height: '12px', borderRadius: '3px', background: 'linear-gradient(180deg, #6366f1 0%, #4338ca 100%)' }}></span>
              <span style={{ color: 'var(--text-secondary)' }}>Revenue (₹)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ width: '12px', height: '12px', borderRadius: '3px', background: '#34d399' }}></span>
              <span style={{ color: 'var(--text-secondary)' }}>Orders Count</span>
            </div>
          </div>
        </div>

        {trends.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No order activity recorded in this period.
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${trends.length}, 1fr)`,
            gap: '0.75rem',
            alignItems: 'flex-end',
            minHeight: '200px',
            paddingTop: '1.5rem',
            borderBottom: '1px solid var(--border-color)'
          }}>
            {trends.map((t, idx) => {
              const heightPct = Math.max(12, Math.round((t.revenue / maxTrendRevenue) * 100));
              return (
                <div key={idx} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    ₹{t.revenue}
                  </div>
                  <div style={{
                    width: '100%',
                    maxWidth: '48px',
                    height: `${heightPct * 1.5}px`,
                    maxHeight: '150px',
                    borderRadius: '6px 6px 0 0',
                    background: 'linear-gradient(180deg, #6366f1 0%, #4338ca 100%)',
                    boxShadow: '0 4px 12px rgba(99, 102, 241, 0.25)',
                    position: 'relative',
                    transition: 'height 0.4s ease'
                  }}>
                    {t.orders > 0 && (
                      <span style={{
                        position: 'absolute',
                        top: '-10px',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        background: '#10b981',
                        color: '#fff',
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        padding: '1px 5px',
                        borderRadius: '10px'
                      }}>
                        {t.orders}
                      </span>
                    )}
                  </div>
                  <div style={{
                    fontSize: '0.72rem',
                    color: 'var(--text-muted)',
                    textAlign: 'center',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    maxWidth: '85px',
                    paddingTop: '0.35rem'
                  }} title={t.label}>
                    {t.label}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 3. OPERATIONS PIPELINE & STATUS FUNNEL */}
      <div className="glass-card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h3 style={{ margin: '0 0 0.35rem', fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Clock size={18} color="#ec4899" /> Current Operational Stage Pipeline
        </h3>
        <p style={{ margin: '0 0 1.25rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Real-time garments tracking through the Paldi shop lifecycle.
        </p>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: '0.75rem'
        }}>
          {[
            { label: 'Pending Pickup', count: funnel.PENDING_PICKUP || 0, color: '#f59e0b', icon: '🛵' },
            { label: 'In Shop (Received)', count: funnel.IN_SHOP || 0, color: '#3b82f6', icon: '🏬' },
            { label: 'Cleaning / Process', count: funnel.PROCESSING || 0, color: '#8b5cf6', icon: '⚙️' },
            { label: 'Ready for Dispatch', count: funnel.READY || 0, color: '#10b981', icon: '✨' },
            { label: 'Delivered', count: funnel.DELIVERED || 0, color: '#059669', icon: '✅' },
            { label: 'Cancelled', count: funnel.CANCELLED || 0, color: '#ef4444', icon: '❌' },
          ].map((st, i) => (
            <div key={i} style={{
              background: 'var(--bg-secondary)',
              border: `1px solid var(--border-color)`,
              borderRadius: 'var(--radius-md)',
              padding: '0.85rem',
              textAlign: 'center',
              borderTop: `3px solid ${st.color}`
            }}>
              <div style={{ fontSize: '1.3rem', marginBottom: '0.2rem' }}>{st.icon}</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                {st.count}
              </div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: '0.15rem' }}>
                {st.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4. CHANNELS, PAYMENTS & SERVICES 3-COLUMN GRID */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '1.25rem',
        marginBottom: '1.5rem'
      }}>
        {/* Logistics & Channel Breakdown */}
        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <h4 style={{ margin: '0 0 1rem', fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Truck size={16} color="#6366f1" /> Logistics Channels
          </h4>

          {/* Home Pickup */}
          <div style={{ marginBottom: '1rem', background: 'var(--bg-secondary)', padding: '0.85rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                🛵 Home Delivery (Paldi Area)
              </span>
              <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#818cf8' }}>
                {channels.pickup?.orders || 0} orders ({channels.pickup?.share_pct || 0}%)
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Revenue: <strong>₹{channels.pickup?.revenue || 0}</strong> • Delivery Fees Collected: <strong>₹{kpis.delivery_fees_collected || 0}</strong>
            </div>
          </div>

          {/* Walk-in Counter */}
          <div style={{ background: 'var(--bg-secondary)', padding: '0.85rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                🏬 Store Walk-in (Counter POS)
              </span>
              <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#c084fc' }}>
                {channels.store_drop?.orders || 0} orders ({channels.store_drop?.share_pct || 0}%)
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Revenue: <strong>₹{channels.store_drop?.revenue || 0}</strong> • Zero delivery fee (Self-pickup)
            </div>
          </div>
        </div>

        {/* Payment Methods & Collection */}
        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <h4 style={{ margin: '0 0 1rem', fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <CreditCard size={16} color="#10b981" /> Payment Modes & Status
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>📱 UPI Digital Pay</span>
              <strong style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{payments.modes?.UPI || 0} orders</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>💵 Cash at Counter / COD</span>
              <strong style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{payments.modes?.CASH || 0} orders</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>⏳ Unpaid / Pending Pay</span>
              <strong style={{ fontSize: '0.85rem', color: '#fbbf24' }}>{payments.statuses?.PENDING || 0} orders</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0.75rem', background: 'rgba(99, 102, 241, 0.08)', borderRadius: 'var(--radius-sm)', border: '1px dashed var(--border-color)' }}>
              <span style={{ fontSize: '0.8rem', color: '#818cf8' }}>🎁 Loyalty Points Redeemed</span>
              <strong style={{ fontSize: '0.85rem', color: '#818cf8' }}>₹{kpis.points_redeemed || 0} discount</strong>
            </div>
          </div>
        </div>

        {/* Services Demand Breakdown */}
        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <h4 style={{ margin: '0 0 1rem', fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Tag size={16} color="#ec4899" /> Service Demand Breakdown
          </h4>

          {Object.keys(services).length === 0 ? (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', padding: '1.5rem 0' }}>
              No item details recorded yet.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {Object.entries(services).map(([sName, count]) => {
                const pct = Math.round((count / totalServiceCount) * 100);
                return (
                  <div key={sName}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', marginBottom: '0.25rem' }}>
                      <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{sName}</span>
                      <span style={{ color: 'var(--text-muted)' }}>{count} pcs ({pct}%)</span>
                    </div>
                    <div style={{ height: '6px', width: '100%', background: 'var(--bg-secondary)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${pct}%`,
                        background: 'linear-gradient(90deg, #6366f1 0%, #ec4899 100%)',
                        borderRadius: '3px'
                      }}></div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* 5. TOP GARMENTS & CUSTOMER LEADERBOARD */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '1.25rem'
      }}>
        {/* Top Garments Leaderboard */}
        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <h4 style={{ margin: '0 0 1rem', fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            🧺 Most Popular Garments
          </h4>

          {topGarments.length === 0 ? (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', padding: '1.5rem 0' }}>
              No garment data available.
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.6rem' }}>
              {topGarments.map((g, i) => (
                <div key={i} style={{
                  padding: '0.6rem 0.8rem',
                  background: 'var(--bg-secondary)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-color)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {g.name}
                  </span>
                  <span style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    background: 'rgba(99, 102, 241, 0.15)',
                    color: '#818cf8',
                    padding: '2px 7px',
                    borderRadius: '10px'
                  }}>
                    {g.count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Customer Intelligence & Languages */}
        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <h4 style={{ margin: '0 0 1rem', fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <MessageSquare size={16} color="#3b82f6" /> Customer Language Preferences
          </h4>

          <div style={{ display: 'flex', gap: '0.6rem', marginBottom: '1rem' }}>
            {Object.entries(customers.languages || {}).map(([lang, cnt]) => (
              <div key={lang} style={{
                flex: 1,
                padding: '0.6rem',
                background: 'var(--bg-secondary)',
                borderRadius: 'var(--radius-sm)',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                  {cnt}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                  {lang}
                </div>
              </div>
            ))}
          </div>

          <h5 style={{ margin: '0.75rem 0 0.5rem', fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
            Top Customers ({data?.period_label})
          </h5>
          {(customers.top_customers || []).length === 0 ? (
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>No customer orders in this timeframe.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {(customers.top_customers || []).map((c) => (
                <div key={c.id} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '0.78rem',
                  padding: '0.35rem 0',
                  borderBottom: '1px solid var(--border-color)'
                }}>
                  <div>
                    <strong style={{ color: 'var(--text-primary)' }}>{c.name}</strong>
                    <span style={{ color: 'var(--text-muted)', marginLeft: '0.4rem' }}>({c.phone})</span>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)', marginRight: '0.6rem' }}>{c.orders} orders</span>
                    <strong style={{ color: '#34d399' }}>₹{c.spend}</strong>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
