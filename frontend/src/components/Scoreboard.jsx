import React from 'react';
import { ShoppingBag, Truck, Users } from 'lucide-react';

export default function Scoreboard({ analytics }) {
  const { active_orders = 0, pending_pickups = 0, total_customers = 0 } = analytics || {};

  return (
    <div className="scoreboard">
      <div className="glass-card stat-card">
        <div className="stat-icon primary">
          <ShoppingBag size={24} />
        </div>
        <div>
          <div className="stat-val">{active_orders}</div>
          <div className="stat-label">Active Orders</div>
        </div>
      </div>

      <div className="glass-card stat-card">
        <div className="stat-icon warning">
          <Truck size={24} />
        </div>
        <div>
          <div className="stat-val">{pending_pickups}</div>
          <div className="stat-label">Pending Pickups</div>
        </div>
      </div>

      <div className="glass-card stat-card">
        <div className="stat-icon info">
          <Users size={24} />
        </div>
        <div>
          <div className="stat-val">{total_customers}</div>
          <div className="stat-label">Total Customers</div>
        </div>
      </div>
    </div>
  );
}
