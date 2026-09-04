import React, { useState, useEffect } from 'react';
import { Search, Edit3, X, Plus, Trash2, MapPin, Send, AlertTriangle, Lock, CheckCircle2 } from 'lucide-react';
import { api } from '../api';

const STATUS_HUMAN_MAP = {
  PENDING_PICKUP: 'Pending Pickup',
  PICKED_UP: 'Picked Up',
  IN_SHOP: 'Received at Shop',
  PROCESSING: 'In Cleaning',
  READY: 'Ready for Delivery',
  DELIVERED: 'Delivered',
  CANCELLED: 'Cancelled',
  REJECTED: 'Rejected',
};

const PAYMENT_HUMAN_MAP = {
  PENDING: 'Unpaid',
  PAID: 'Paid',
};

export default function OrderManagement({ orders, runners, catalog, onRefresh }) {
  const [showAll, setShowAll] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedOrder, setSelectedOrder] = useState(null);

  // Edit form state
  const [editAddress, setEditAddress] = useState('');
  const [editInstructions, setEditInstructions] = useState('');
  const [editItems, setEditItems] = useState([]);
  const [rawPriceInput, setRawPriceInput] = useState(0);
  const [paymentStatusInput, setPaymentStatusInput] = useState('PENDING');
  const [orderStatusInput, setOrderStatusInput] = useState('PENDING_PICKUP');
  const [selectedRunnerPhone, setSelectedRunnerPhone] = useState('');

  // Delivery confirmation modal state
  const [showDeliveryConfirmModal, setShowDeliveryConfirmModal] = useState(false);

  // UI status messages
  const [modalMessage, setModalMessage] = useState({ type: '', text: '' });
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    onRefresh(showAll);
  }, [showAll]);

  const openManageModal = (order) => {
    setSelectedOrder(order);
    setEditAddress(order.flat_address || '');
    setEditInstructions(order.special_instructions || '');
    setEditItems(
      order.items.length > 0
        ? order.items.map((i) => ({ ...i }))
        : []
    );
    setRawPriceInput(order.total_amount !== null ? order.total_amount : order.estimated_amount || 0);
    setPaymentStatusInput(order.payment_status || 'PENDING');
    setOrderStatusInput(order.status || 'PENDING_PICKUP');
    setSelectedRunnerPhone(runners.length > 0 ? runners[0].phone_number : '');
    setModalMessage({ type: '', text: '' });
    setShowDeliveryConfirmModal(false);
  };

  const closeModal = () => {
    setSelectedOrder(null);
    setShowDeliveryConfirmModal(false);
  };

  // Check state lifecycle status
  const isTerminalState = selectedOrder && ['DELIVERED', 'CANCELLED', 'REJECTED'].includes(selectedOrder.status);

  // Garment breakdown item helpers
  const handleAddItemRow = () => {
    if (isTerminalState) return;
    setEditItems([
      ...editItems,
      { garment_type: 'Shirt', service_type: 'dry_clean', quantity: 1 },
    ]);
  };

  const handleRemoveItemRow = (index) => {
    if (isTerminalState) return;
    const updated = editItems.filter((_, idx) => idx !== index);
    setEditItems(updated);
  };

  const handleItemChange = (index, field, value) => {
    if (isTerminalState) return;
    const updated = [...editItems];
    updated[index][field] = value;
    setEditItems(updated);
  };

  // Save Garment Breakdown & Address
  const handleSaveOrderItems = async () => {
    if (!selectedOrder || isTerminalState) return;
    setIsSaving(true);
    setModalMessage({ type: '', text: '' });
    try {
      const updated = await api.updateOrderItems(selectedOrder.order_id, {
        flat_address: editAddress,
        special_instructions: editInstructions,
        items: editItems.map((item) => ({
          garment_type: item.garment_type,
          service_type: item.service_type,
          quantity: parseInt(item.quantity) || 1,
        })),
      });
      setSelectedOrder(updated);
      setModalMessage({ type: 'success', text: 'Garments and address updated successfully!' });
      onRefresh(showAll);
    } catch (err) {
      setModalMessage({ type: 'error', text: err.message });
    } finally {
      setIsSaving(false);
    }
  };

  // Save Final Raw Price
  const handleSavePrice = async () => {
    if (!selectedOrder || isTerminalState) return;
    setIsSaving(true);
    setModalMessage({ type: '', text: '' });
    try {
      const updated = await api.updateOrderPrice(selectedOrder.order_id, parseFloat(rawPriceInput));
      setSelectedOrder(updated);
      setModalMessage({ type: 'success', text: `Raw Price saved as ₹${rawPriceInput}` });
      onRefresh(showAll);
    } catch (err) {
      setModalMessage({ type: 'error', text: err.message });
    } finally {
      setIsSaving(false);
    }
  };

  // Update Status & Payment Click Handler
  const handleUpdateStatusClick = () => {
    if (!selectedOrder || isTerminalState) return;

    // If admin is transitioning to DELIVERED, trigger confirmation modal to prevent miss clicks
    if (orderStatusInput === 'DELIVERED' && selectedOrder.status !== 'DELIVERED') {
      // Check pre-validations first
      if (!selectedOrder.total_amount && (rawPriceInput <= 0)) {
        setModalMessage({ type: 'error', text: '❌ You MUST enter and save Total Amount before moving to DELIVERED.' });
        return;
      }
      if (paymentStatusInput !== 'PAID') {
        setModalMessage({ type: 'error', text: '❌ Cannot mark order as DELIVERED until payment status is PAID.' });
        return;
      }
      setShowDeliveryConfirmModal(true);
      return;
    }

    // Direct update for non-DELIVERED transitions
    executeStatusUpdate();
  };

  // Execute Actual Status Update
  const executeStatusUpdate = async () => {
    if (!selectedOrder) return;
    setIsSaving(true);
    setModalMessage({ type: '', text: '' });
    setShowDeliveryConfirmModal(false);
    try {
      const updated = await api.updateOrderStatus(selectedOrder.order_id, orderStatusInput, paymentStatusInput);
      setSelectedOrder(updated);
      setModalMessage({ type: 'success', text: 'Order status updated successfully!' });
      onRefresh(showAll);
    } catch (err) {
      setModalMessage({ type: 'error', text: err.message });
    } finally {
      setIsSaving(false);
    }
  };

  // Dispatch Runner
  const handleDispatchRunner = async () => {
    if (!selectedOrder || !selectedRunnerPhone || isTerminalState) return;
    setIsSaving(true);
    setModalMessage({ type: '', text: '' });
    try {
      const res = await api.dispatchRunner(selectedOrder.order_id, selectedRunnerPhone);
      setModalMessage({ type: 'success', text: res.message || 'Runner dispatched!' });
      const updated = await api.getOrderDetails(selectedOrder.order_id);
      setSelectedOrder(updated);
      onRefresh(showAll);
    } catch (err) {
      setModalMessage({ type: 'error', text: err.message });
    } finally {
      setIsSaving(false);
    }
  };

  // Reject Order
  const handleRejectOrder = async () => {
    if (!selectedOrder || isTerminalState) return;
    if (!window.confirm('Reject this order (Outside Paldi)?')) return;
    setIsSaving(true);
    try {
      await api.rejectOrder(selectedOrder.order_id);
      closeModal();
      onRefresh(showAll);
    } catch (err) {
      setModalMessage({ type: 'error', text: err.message });
    } finally {
      setIsSaving(false);
    }
  };

  // Cancel Order
  const handleCancelOrder = async () => {
    if (!selectedOrder || isTerminalState) return;
    if (!window.confirm('Cancel this order?')) return;
    setIsSaving(true);
    try {
      await api.cancelOrder(selectedOrder.order_id);
      closeModal();
      onRefresh(showAll);
    } catch (err) {
      setModalMessage({ type: 'error', text: err.message });
    } finally {
      setIsSaving(false);
    }
  };

  // Filter orders by search
  const filteredOrders = orders.filter((o) => {
    const q = searchTerm.toLowerCase();
    return (
      (o.order_id && o.order_id.toLowerCase().includes(q)) ||
      (o.customer_name && o.customer_name.toLowerCase().includes(q)) ||
      (o.customer_phone && o.customer_phone.includes(q)) ||
      (o.service_category && o.service_category.toLowerCase().includes(q))
    );
  });

  const getBadgeClass = (status) => {
    switch (status) {
      case 'PENDING_PICKUP': return 'badge-pending';
      case 'PICKED_UP': return 'badge-picked';
      case 'IN_SHOP': return 'badge-shop';
      case 'PROCESSING': return 'badge-process';
      case 'READY': return 'badge-ready';
      case 'DELIVERED': return 'badge-delivered';
      case 'CANCELLED':
      case 'REJECTED': return 'badge-danger';
      default: return 'badge-pending';
    }
  };

  return (
    <div>
      {/* Controls Bar */}
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
            <input
              type="checkbox"
              checked={showAll}
              onChange={(e) => setShowAll(e.target.checked)}
              style={{ accentColor: 'var(--accent-primary)', width: '16px', height: '16px' }}
            />
            Show all orders (including delivered/cancelled)
          </label>
        </div>

        <div style={{ position: 'relative', minWidth: '280px' }}>
          <input
            type="text"
            className="form-control"
            placeholder="Search Order ID, Name, Phone..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ width: '100%', paddingLeft: '2.25rem' }}
          />
          <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
        </div>
      </div>

      {/* Orders Table */}
      <div className="table-responsive">
        <table className="custom-table">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Placed At</th>
              <th>Type</th>
              <th>Customer</th>
              <th>Address / GPS</th>
              <th>Items</th>
              <th>Final Total</th>
              <th>Payment</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredOrders.length === 0 ? (
              <tr>
                <td colSpan={10} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  No orders found matching criteria.
                </td>
              </tr>
            ) : (
              filteredOrders.map((o) => (
                <tr key={o.order_id}>
                  <td style={{ fontWeight: 700, color: 'var(--accent-primary)' }}>#{o.order_id}</td>
                  <td style={{ fontSize: '0.82rem', whiteSpace: 'nowrap' }}>{o.created_at_formatted || 'N/A'}</td>
                  <td>{o.order_type === 'PICKUP' ? 'Pickup & Delivery' : 'Store Drop'}</td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{o.customer_name}</div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{o.customer_phone}</div>
                  </td>
                  <td style={{ maxWidth: '200px' }}>
                    <div style={{ fontSize: '0.85rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {o.flat_address || 'N/A'}
                    </div>
                    {o.last_location_gps && (
                      <a
                        href={`https://www.google.com/maps?q=${o.last_location_gps}`}
                        target="_blank"
                        rel="noreferrer"
                        style={{ fontSize: '0.75rem', color: 'var(--accent-info)', display: 'inline-flex', alignItems: 'center', gap: '2px' }}
                      >
                        <MapPin size={12} /> Map Link
                      </a>
                    )}
                  </td>
                  <td>{o.item_count} items</td>
                  <td style={{ fontWeight: 700 }}>₹{o.final_total}</td>
                  <td>
                    <span className={`badge ${o.payment_status === 'PAID' ? 'badge-delivered' : 'badge-pending'}`}>
                      {PAYMENT_HUMAN_MAP[o.payment_status] || o.payment_status}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${getBadgeClass(o.status)}`}>
                      {STATUS_HUMAN_MAP[o.status] || o.status}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => openManageModal(o)}
                    >
                      <Edit3 size={14} /> {['DELIVERED', 'CANCELLED', 'REJECTED'].includes(o.status) ? 'View' : 'Manage'}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* MANAGE ORDER MODAL */}
      {selectedOrder && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                Order #{selectedOrder.order_id} Details
                {isTerminalState && (
                  <span className="badge badge-delivered" style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem' }}>
                    <Lock size={12} /> Locked & Completed
                  </span>
                )}
              </h3>
              <button className="modal-close" onClick={closeModal}>
                <X size={20} />
              </button>
            </div>

            {modalMessage.text && (
              <div className={`alert-banner ${modalMessage.type === 'error' ? 'alert-error' : 'alert-success'}`}>
                {modalMessage.type === 'error' ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />} {modalMessage.text}
              </div>
            )}

            {/* Read-Only Terminal State Banner */}
            {isTerminalState && (
              <div className="alert-banner alert-success" style={{ background: 'rgba(16,185,129,0.1)', borderColor: 'rgba(16,185,129,0.3)', color: '#34d399' }}>
                <Lock size={16} /> <strong>Order Lifecycle Completed ({STATUS_HUMAN_MAP[selectedOrder.status]}):</strong> Garments, prices, and address details are permanently locked to preserve historical record integrity.
              </div>
            )}

            {/* Overview Box */}
            <div className="glass-card" style={{ padding: '1rem', marginBottom: '1.25rem', fontSize: '0.9rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
                <div><strong>📅 Placed:</strong> {selectedOrder.created_at_formatted}</div>
                {selectedOrder.picked_up_at_formatted && <div><strong>🚚 Picked Up:</strong> {selectedOrder.picked_up_at_formatted}</div>}
                {selectedOrder.delivered_at_formatted && <div><strong>✅ Delivered:</strong> {selectedOrder.delivered_at_formatted}</div>}
                <div><strong>Requested Services:</strong> {selectedOrder.service_category}</div>
                <div><strong>Address:</strong> {selectedOrder.flat_address || 'N/A'}</div>
              </div>
            </div>

            {/* Edit Breakdown & Address */}
            <div style={{ marginBottom: '1.5rem', border: '1px solid var(--bg-card-border)', borderRadius: 'var(--radius-md)', padding: '1rem', opacity: isTerminalState ? 0.75 : 1 }}>
              <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                ✏️ Garment Breakdown & Address {isTerminalState && <Lock size={14} color="var(--text-muted)" />}
              </h4>

              <div className="form-group">
                <label className="form-label">Pickup Address</label>
                <input
                  type="text"
                  className="form-control"
                  value={editAddress}
                  disabled={isTerminalState}
                  onChange={(e) => setEditAddress(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Special Instructions</label>
                <textarea
                  className="form-control"
                  rows={2}
                  value={editInstructions}
                  disabled={isTerminalState}
                  onChange={(e) => setEditInstructions(e.target.value)}
                />
              </div>

              <h5 style={{ fontSize: '0.9rem', fontWeight: 600, marginTop: '1rem', marginBottom: '0.5rem' }}>
                Garments Breakdown
              </h5>

              {editItems.map((item, idx) => {
                const serviceGarments = catalog
                  .filter((c) => c.service_type === item.service_type)
                  .map((c) => c.item_name);

                return (
                  <div className="item-row" key={idx}>
                    <select
                      className="form-control"
                      value={item.service_type}
                      disabled={isTerminalState}
                      onChange={(e) => handleItemChange(idx, 'service_type', e.target.value)}
                    >
                      <option value="dry_clean">Dry Clean</option>
                      <option value="washing">Washing</option>
                      <option value="steam_press">Steam Press</option>
                      <option value="petrol_wash">Petrol Wash</option>
                    </select>

                    <select
                      className="form-control"
                      value={item.garment_type}
                      disabled={isTerminalState}
                      onChange={(e) => handleItemChange(idx, 'garment_type', e.target.value)}
                    >
                      {serviceGarments.length > 0 ? (
                        serviceGarments.map((g) => (
                          <option key={g} value={g}>{g}</option>
                        ))
                      ) : (
                        <option value={item.garment_type}>{item.garment_type}</option>
                      )}
                    </select>

                    <input
                      type="number"
                      className="form-control"
                      min={1}
                      value={item.quantity}
                      disabled={isTerminalState}
                      onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                    />

                    {!isTerminalState && (
                      <button
                        className="btn btn-danger btn-sm"
                        type="button"
                        onClick={() => handleRemoveItemRow(idx)}
                        title="Remove Row"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                );
              })}

              {!isTerminalState && (
                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
                  <button className="btn btn-secondary btn-sm" type="button" onClick={handleAddItemRow}>
                    <Plus size={14} /> Add Item Row
                  </button>
                  <button className="btn btn-primary btn-sm" type="button" onClick={handleSaveOrderItems} disabled={isSaving}>
                    💾 Save Garments & Address
                  </button>
                </div>
              )}
            </div>

            {/* 3 Column Control Section */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              {/* Col 1: Raw Price */}
              <div style={{ border: '1px solid var(--bg-card-border)', borderRadius: 'var(--radius-md)', padding: '1rem', opacity: isTerminalState ? 0.75 : 1 }}>
                <h5 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem' }}>💰 Total Amount</h5>
                <div className="form-group">
                  <label className="form-label">Raw Clothes Amount (₹)</label>
                  <input
                    type="number"
                    className="form-control"
                    value={rawPriceInput}
                    disabled={isTerminalState}
                    onChange={(e) => setRawPriceInput(e.target.value)}
                  />
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                  <div>+ Delivery Fee: ₹{selectedOrder.delivery_fee}</div>
                  {selectedOrder.points_redeemed > 0 && <div>- Points Redeemed: ₹{selectedOrder.points_redeemed}</div>}
                  <div style={{ fontWeight: 700, color: 'var(--accent-success)', marginTop: '0.25rem' }}>
                    = Total Collected: ₹{(parseFloat(rawPriceInput) || 0) + selectedOrder.delivery_fee - selectedOrder.points_redeemed}
                  </div>
                </div>
                {!isTerminalState && (
                  <button className="btn btn-secondary btn-sm" style={{ width: '100%' }} onClick={handleSavePrice} disabled={isSaving}>
                    Save Price
                  </button>
                )}
              </div>

              {/* Col 2: Status & Payment */}
              <div style={{ border: '1px solid var(--bg-card-border)', borderRadius: 'var(--radius-md)', padding: '1rem', opacity: isTerminalState ? 0.75 : 1 }}>
                <h5 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem' }}>🔄 Update Status</h5>
                <div className="form-group">
                  <label className="form-label">Payment Status</label>
                  <select
                    className="form-control"
                    value={paymentStatusInput}
                    disabled={isTerminalState}
                    onChange={(e) => setPaymentStatusInput(e.target.value)}
                  >
                    <option value="PENDING">Unpaid</option>
                    <option value="PAID">Paid</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Order Status</label>
                  <select
                    className="form-control"
                    value={orderStatusInput}
                    disabled={isTerminalState}
                    onChange={(e) => setOrderStatusInput(e.target.value)}
                  >
                    <option value="PENDING_PICKUP">Pending Pickup</option>
                    <option value="PICKED_UP">Picked Up</option>
                    <option value="IN_SHOP">Received at Shop</option>
                    <option value="PROCESSING">In Cleaning</option>
                    <option value="READY">Ready for Delivery</option>
                    <option value="DELIVERED">Delivered</option>
                  </select>
                </div>
                {!isTerminalState && (
                  <button className="btn btn-primary btn-sm" style={{ width: '100%' }} onClick={handleUpdateStatusClick} disabled={isSaving}>
                    Update Statuses
                  </button>
                )}
              </div>

              {/* Col 3: Dispatch Runner */}
              {!isTerminalState && (
                <div style={{ border: '1px solid var(--bg-card-border)', borderRadius: 'var(--radius-md)', padding: '1rem' }}>
                  <h5 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem' }}>🛵 Dispatch Runner</h5>
                  <div className="form-group">
                    <label className="form-label">Select Staff</label>
                    <select
                      className="form-control"
                      value={selectedRunnerPhone}
                      onChange={(e) => setSelectedRunnerPhone(e.target.value)}
                    >
                      {runners.length === 0 ? (
                        <option value="">No staff available</option>
                      ) : (
                        runners.map((r) => (
                          <option key={r.runner_id} value={r.phone_number}>
                            {r.name} ({r.phone_number})
                          </option>
                        ))
                      )}
                    </select>
                  </div>
                  <button className="btn btn-secondary btn-sm" style={{ width: '100%', marginTop: '1.25rem' }} onClick={handleDispatchRunner} disabled={isSaving || !selectedRunnerPhone}>
                    <Send size={14} /> Dispatch WhatsApp
                  </button>
                </div>
              )}
            </div>

            {/* Danger Zone: Only shown for non-terminal orders (NOT DELIVERED / CANCELLED / REJECTED) */}
            {!isTerminalState && (
              <div style={{ border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.05)', borderRadius: 'var(--radius-md)', padding: '1rem' }}>
                <h5 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--accent-danger)', marginBottom: '0.75rem' }}>
                  ⚠️ Danger Zone
                </h5>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <button className="btn btn-danger btn-sm" onClick={handleRejectOrder} disabled={isSaving}>
                    Reject (Outside Paldi)
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={handleCancelOrder} disabled={isSaving}>
                    Cancel Order
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* CONFIRM DELIVERY DIALOG MODAL */}
      {showDeliveryConfirmModal && selectedOrder && (
        <div className="modal-overlay" style={{ zIndex: 2000 }}>
          <div className="modal-content" style={{ maxWidth: '500px', border: '1px solid rgba(239, 68, 68, 0.4)' }}>
            <div className="modal-header">
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--accent-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <AlertTriangle size={22} color="var(--accent-primary)" /> Confirm Final Delivery
              </h3>
              <button className="modal-close" onClick={() => setShowDeliveryConfirmModal(false)}>
                <X size={20} />
              </button>
            </div>

            <div style={{ marginBottom: '1.25rem', fontSize: '0.92rem', lineHeight: '1.5' }}>
              <p style={{ marginBottom: '0.75rem', fontWeight: 600 }}>
                Are you sure you want to mark Order #{selectedOrder.order_id} as <span style={{ color: 'var(--accent-success)' }}>DELIVERED</span>?
              </p>
              
              <div className="glass-card" style={{ padding: '0.85rem 1rem', marginBottom: '1rem', background: 'var(--bg-secondary)', fontSize: '0.85rem' }}>
                <div><strong>Customer:</strong> {selectedOrder.customer_name} ({selectedOrder.customer_phone})</div>
                <div><strong>Total Clothes Collected:</strong> {selectedOrder.item_count} items</div>
                <div><strong>Final Amount:</strong> ₹{selectedOrder.final_total}</div>
                <div><strong>Payment:</strong> <span style={{ color: 'var(--accent-success)', fontWeight: 600 }}>PAID</span></div>
              </div>

              <div className="alert-banner alert-error" style={{ fontSize: '0.82rem', marginBottom: 0 }}>
                ⚠️ <strong>Important Notice:</strong> Confirming delivery will lock this order permanently, credit customer loyalty points, and send the final delivery receipt message on WhatsApp.
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setShowDeliveryConfirmModal(false)}
                disabled={isSaving}
              >
                Revert / Go Back
              </button>
              <button
                className="btn btn-primary"
                onClick={executeStatusUpdate}
                disabled={isSaving}
              >
                {isSaving ? 'Processing...' : '✅ Confirm & Deliver Order'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
