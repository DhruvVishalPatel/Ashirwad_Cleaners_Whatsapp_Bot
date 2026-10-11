import React, { useState, useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import {
  X,
  Plus,
  Trash2,
  Store,
  Truck,
  User,
  Phone,
  MapPin,
  Bot,
  AlertCircle,
  CheckCircle2,
  Receipt,
  Sparkles,
  Search,
  DollarSign,
  Send,
  ChevronDown
} from 'lucide-react';
import { api } from '../api';

const SERVICE_TYPES = [
  { id: 'Dry Clean', label: 'Dry Clean 👔', catKey: 'dry_clean' },
  { id: 'Washing', label: 'Washing & Ironing 🧺', catKey: 'washing' },
  { id: 'Steam Press', label: 'Steam Press 💨', catKey: 'steam_press' },
  { id: 'Petrol Wash', label: 'Petrol Wash ⛽', catKey: 'petrol_wash' }
];

function GarmentCombobox({
  value,
  onChange,
  onSelectGarment,
  garmentList = [],
  placeholder = 'Type or select garment...'
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState(value || '');
  const containerRef = useRef(null);

  useEffect(() => {
    setQuery(value || '');
  }, [value]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredList = useMemo(() => {
    if (!query.trim()) return garmentList;
    const q = query.toLowerCase().trim();
    return garmentList.filter((g) => g.item_name.toLowerCase().includes(q));
  }, [garmentList, query]);

  const handleSelect = (garmentName, price) => {
    setQuery(garmentName);
    onChange(garmentName);
    if (onSelectGarment) {
      onSelectGarment(garmentName, price);
    }
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', position: 'relative' }}>
        <input
          type="text"
          className="form-control form-control-sm"
          style={{ width: '100%', paddingRight: '2.2rem', fontSize: '0.82rem' }}
          placeholder={placeholder}
          value={query}
          onFocus={() => setIsOpen(true)}
          onChange={(e) => {
            const val = e.target.value;
            setQuery(val);
            onChange(val);
            setIsOpen(true);
          }}
          required
        />
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setIsOpen((prev) => !prev)}
          style={{
            position: 'absolute',
            right: '4px',
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
          title="Browse all garments"
        >
          <ChevronDown
            size={15}
            style={{
              transform: isOpen ? 'rotate(180deg)' : 'none',
              transition: 'transform 0.2s ease',
              color: isOpen ? 'var(--primary)' : 'var(--text-muted)'
            }}
          />
        </button>
      </div>

      {isOpen && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 4px)',
          left: 0,
          right: 0,
          zIndex: 99999,
          background: 'var(--bg-card, #1e1e2d)',
          border: '1px solid var(--border-color, rgba(255,255,255,0.15))',
          borderRadius: 'var(--radius-md, 8px)',
          boxShadow: '0 12px 30px rgba(0, 0, 0, 0.55)',
          maxHeight: '240px',
          overflowY: 'auto',
          padding: '0.25rem 0'
        }}>
          <div style={{
            padding: '0.35rem 0.75rem',
            fontSize: '0.7rem',
            fontWeight: 700,
            color: 'var(--text-muted)',
            textTransform: 'uppercase',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'var(--bg-secondary)'
          }}>
            <span>Available Garments ({filteredList.length})</span>
            <span>Est. Rate</span>
          </div>

          {filteredList.length === 0 ? (
            <div style={{ padding: '0.75rem', textAlign: 'center', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              <div>No match in this service.</div>
              {query.trim() && (
                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleSelect(query.trim(), null);
                  }}
                  style={{
                    marginTop: '0.4rem',
                    border: '1px dashed var(--primary)',
                    background: 'rgba(99, 102, 241, 0.1)',
                    color: 'var(--primary)',
                    padding: '0.35rem 0.65rem',
                    borderRadius: '4px',
                    fontSize: '0.76rem',
                    cursor: 'pointer',
                    fontWeight: 600
                  }}
                >
                  Use custom garment: "{query.trim()}"
                </button>
              )}
            </div>
          ) : (
            filteredList.map((g, i) => (
              <div
                key={i}
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSelect(g.item_name, g.price);
                }}
                style={{
                  padding: '0.45rem 0.75rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '0.82rem',
                  cursor: 'pointer',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                  transition: 'background 0.12s ease',
                  background: query && query.toLowerCase() === g.item_name.toLowerCase() ? 'rgba(99, 102, 241, 0.18)' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(99, 102, 241, 0.2)'}
                onMouseLeave={(e) => e.currentTarget.style.background = query && query.toLowerCase() === g.item_name.toLowerCase() ? 'rgba(99, 102, 241, 0.18)' : 'transparent'}
              >
                <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  {g.item_name}
                </div>
                {g.price != null && (
                  <span style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: '#34d399',
                    background: 'rgba(16, 185, 129, 0.12)',
                    padding: '2px 7px',
                    borderRadius: '10px'
                  }}>
                    ₹{g.price}
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default function CreateOrderModal({
  isOpen,
  onClose,
  customers = [],
  catalog = [],
  runners = [],
  preSelectedCustomerId = null,
  onOrderCreated
}) {
  if (!isOpen) return null;

  // Customer Selection State
  const [isNewCustomer, setIsNewCustomer] = useState(false);
  const [customerSearch, setCustomerSearch] = useState('');
  const [selectedCustomerId, setSelectedCustomerId] = useState(preSelectedCustomerId || '');
  
  // New Customer Form
  const [newCustName, setNewCustName] = useState('');
  const [newCustPhone, setNewCustPhone] = useState('');
  const [newCustAddress, setNewCustAddress] = useState('');

  // Order Logistics (Strictly 2 Types: STORE_DROP vs PICKUP)
  const [orderType, setOrderType] = useState('STORE_DROP'); // 'STORE_DROP' (Store Walk-in) | 'PICKUP' (Home Pickup & Delivery)
  const [serviceCategory, setServiceCategory] = useState('Dry Clean');
  const [flatAddress, setFlatAddress] = useState('');
  const [specialInstructions, setSpecialInstructions] = useState('');
  
  // Initial 1 item
  const [items, setItems] = useState([
    { garment_type: 'Shirt', service_type: 'Dry Clean', quantity: 1, price: 50, special_notes: '' }
  ]);

  // Payment & Bot Takeover State
  const [paymentStatus, setPaymentStatus] = useState('PENDING'); // PENDING | PAID
  const [paymentMode, setPaymentMode] = useState('CASH'); // CASH | UPI
  const [selectedRunnerId, setSelectedRunnerId] = useState('');
  const [pointsToRedeem, setPointsToRedeem] = useState(0);
  const [resumeBot, setResumeBot] = useState(true);
  const [sendWhatsAppReceipt, setSendWhatsAppReceipt] = useState(true);

  // Submission State
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Find currently selected customer object
  const currentCustomer = useMemo(() => {
    if (isNewCustomer) return null;
    return customers.find((c) => String(c.customer_id || c.id) === String(selectedCustomerId)) || null;
  }, [customers, selectedCustomerId, isNewCustomer]);

  // Auto-fill address and check pre-selected on open
  useEffect(() => {
    if (preSelectedCustomerId) {
      setSelectedCustomerId(preSelectedCustomerId);
      setIsNewCustomer(false);
    }
  }, [preSelectedCustomerId]);

  useEffect(() => {
    if (currentCustomer && (currentCustomer.saved_address || currentCustomer.flat_address)) {
      setFlatAddress(currentCustomer.saved_address || currentCustomer.flat_address);
    }
  }, [currentCustomer]);

  // Filter existing customers by search input
  const filteredCustomers = useMemo(() => {
    if (!customerSearch.trim()) return customers.slice(0, 50);
    const q = customerSearch.toLowerCase();
    return customers.filter(
      (c) =>
        ((c.name || c.customer_name) && (c.name || c.customer_name).toLowerCase().includes(q)) ||
        ((c.phone_number || c.customer_phone) && (c.phone_number || c.customer_phone).includes(q))
    ).slice(0, 50);
  }, [customers, customerSearch]);

  // Resilient catalog state (uses prop if available, fetches on mount if empty)
  const [internalCatalog, setInternalCatalog] = useState(catalog || []);

  useEffect(() => {
    if (catalog && catalog.length > 0) {
      setInternalCatalog(catalog);
    } else {
      api.getCatalog().then((data) => {
        if (data && data.length > 0) setInternalCatalog(data);
      }).catch(() => {});
    }
  }, [catalog]);

  const normalizeServiceKey = (st) => {
    if (!st) return 'dry_clean';
    const lower = st.toLowerCase().trim();
    if (lower.includes('dry')) return 'dry_clean';
    if (lower.includes('wash') && !lower.includes('petrol')) return 'washing';
    if (lower.includes('press') || lower.includes('steam')) return 'steam_press';
    if (lower.includes('petrol') || lower.includes('stain')) return 'petrol_wash';
    return lower.replace(/ & /g, '_').replace(/ /g, '_');
  };

  // Strictly returns ONLY the garments served under the specific service type
  const getGarmentsWithPricesForService = (serviceTypeLabel) => {
    const sKey = normalizeServiceKey(serviceTypeLabel);
    const filtered = (internalCatalog || []).filter(
      (ci) => normalizeServiceKey(ci.service_type) === sKey
    );

    if (filtered.length > 0) {
      return filtered
        .map((ci) => ({
          item_name: ci.item_name,
          price: ci.price,
          is_variable: ci.is_variable,
          note: ci.note
        }))
        .sort((a, b) => a.item_name.localeCompare(b.item_name));
    }

    // Safe fallbacks per service type if catalog is still loading
    if (sKey === 'washing') {
      return [
        { item_name: 'Kurta', price: 35 },
        { item_name: 'Pant', price: 35 },
        { item_name: 'Payjama', price: 35 },
        { item_name: 'Shirt', price: 35 },
        { item_name: 'T-Shirt', price: 35 },
        { item_name: 'Top', price: 80 }
      ];
    }
    if (sKey === 'steam_press') {
      return [
        { item_name: 'Blouse', price: 20 },
        { item_name: 'Coat / Blazer', price: 80 },
        { item_name: 'Kurta', price: 20 },
        { item_name: 'Pant', price: 20 },
        { item_name: 'Payjama', price: 20 },
        { item_name: 'Saree', price: 80 },
        { item_name: 'Shirt', price: 20 },
        { item_name: 'T-Shirt', price: 20 },
        { item_name: 'Woolen Coat', price: 80 }
      ];
    }
    return [
      { item_name: 'Kurta', price: 50 },
      { item_name: 'Pant', price: 50 },
      { item_name: 'Payjama', price: 50 },
      { item_name: 'Saree', price: 200 },
      { item_name: 'Shirt', price: 50 },
      { item_name: 'T-Shirt', price: 50 }
    ];
  };

  // Garment rows helpers
  const handleItemChange = (index, field, value) => {
    setItems((prev) => {
      const updated = [...prev];
      const row = { ...updated[index], [field]: value };

      // Auto-price and garment realignment if service_type changes
      if (field === 'service_type') {
        const availableGarments = getGarmentsWithPricesForService(value);
        const match = availableGarments.find(
          (ci) => ci.item_name.toLowerCase() === (row.garment_type || '').toLowerCase()
        );

        if (match) {
          row.price = match.price;
        } else if (availableGarments.length > 0) {
          // Garment is not served under this new service: auto-switch to first available garment
          row.garment_type = availableGarments[0].item_name;
          row.price = availableGarments[0].price;
        }
      } else if (field === 'garment_type') {
        const availableGarments = getGarmentsWithPricesForService(row.service_type);
        const match = availableGarments.find(
          (ci) => ci.item_name.toLowerCase() === (value || '').toLowerCase()
        );
        if (match) {
          row.price = match.price;
        }
      }

      updated[index] = row;
      return updated;
    });
  };

  const handleDefaultServiceChange = (newService) => {
    setServiceCategory(newService);
    // If only 1 initial item exists, align its service and garment with the chosen default service
    if (items.length === 1) {
      const availableGarments = getGarmentsWithPricesForService(newService);
      const match = availableGarments.find(
        (ci) => ci.item_name.toLowerCase() === (items[0].garment_type || '').toLowerCase()
      );
      const chosenItem = match || (availableGarments.length > 0 ? availableGarments[0] : { item_name: 'Shirt', price: 50 });
      setItems([
        {
          garment_type: chosenItem.item_name,
          service_type: newService,
          quantity: items[0].quantity || 1,
          price: chosenItem.price,
          special_notes: items[0].special_notes || ''
        }
      ]);
    }
  };

  const handleAddItem = () => {
    const garments = getGarmentsWithPricesForService(serviceCategory);
    const defaultItem = garments.length > 0 ? garments[0] : { item_name: 'Shirt', price: 50 };

    setItems((prev) => [
      ...prev,
      {
        garment_type: defaultItem.item_name,
        service_type: serviceCategory,
        quantity: 1,
        price: defaultItem.price,
        special_notes: ''
      }
    ]);
  };

  const handleRemoveItem = (index) => {
    if (items.length <= 1) return;
    setItems((prev) => prev.filter((_, i) => i !== index));
  };

  // Price calculations
  const subtotal = useMemo(() => {
    return items.reduce((sum, item) => sum + (Number(item.price) || 0) * (Number(item.quantity) || 1), 0);
  }, [items]);

  // Delivery fee: ₹0 for store drop; ₹30 for pickup (waived if customer has 4+ monthly orders)
  const deliveryFee = useMemo(() => {
    if (orderType === 'STORE_DROP') return 0;
    // Check loyalty waiver
    if (currentCustomer && currentCustomer.order_count >= 4) return 0;
    return 30;
  }, [orderType, currentCustomer]);

  const totalPayable = Math.max(0, subtotal + deliveryFee - Number(pointsToRedeem || 0));

  // Handle Form Submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');

    // Validation
    if (!isNewCustomer && !selectedCustomerId) {
      setErrorMsg('Please select an existing customer or switch to "Add New Customer".');
      return;
    }
    if (isNewCustomer) {
      if (!newCustPhone.trim() || newCustPhone.replace(/\D/g, '').length < 10) {
        setErrorMsg('Please enter a valid 10-digit mobile number for the new customer.');
        return;
      }
    }
    if (orderType === 'PICKUP' && !flatAddress.trim()) {
      setErrorMsg('Pickup & Delivery orders require a home address for runner dispatch.');
      return;
    }
    if (items.length === 0) {
      setErrorMsg('Please add at least one garment to the order.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        customer_id: isNewCustomer ? null : Number(selectedCustomerId),
        new_customer_name: isNewCustomer ? newCustName.trim() : null,
        new_customer_phone: isNewCustomer ? newCustPhone.trim() : null,
        new_customer_address: isNewCustomer ? newCustAddress.trim() : null,
        order_type: orderType, // 'STORE_DROP' or 'PICKUP'
        service_category: serviceCategory,
        flat_address: flatAddress.trim(),
        items: items.map((i) => ({
          garment_type: i.garment_type,
          service_type: i.service_type,
          quantity: Number(i.quantity) || 1,
          price: Number(i.price) || 0,
          special_notes: i.special_notes ? i.special_notes.trim() : null
        })),
        total_amount: subtotal,
        delivery_fee: deliveryFee,
        points_redeemed: Number(pointsToRedeem) || 0,
        payment_status: paymentStatus,
        payment_mode: paymentStatus === 'PAID' ? paymentMode : null,
        runner_id: selectedRunnerId ? Number(selectedRunnerId) : null,
        special_instructions: specialInstructions.trim(),
        resume_bot: resumeBot,
        send_whatsapp_receipt: sendWhatsAppReceipt
      };

      const createdOrder = await api.createCounterOrder(payload);
      if (onOrderCreated) {
        onOrderCreated(createdOrder);
      }
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to create order. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 9999 }}>
      <div
        className="modal-content create-order-modal"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-secondary)',
          backgroundColor: 'var(--bg-secondary)',
          maxWidth: '850px',
          width: '95%',
          maxHeight: '92vh',
          overflowY: 'auto'
        }}
      >
        {/* Header */}
        <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Receipt size={22} className="text-primary" /> Create New Order (Digital POS)
            </h2>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
              Book counter walk-ins or home pickup/delivery orders directly into the system.
            </div>
          </div>
          <button className="modal-close" onClick={onClose} title="Close Modal">
            <X size={20} />
          </button>
        </div>

        {errorMsg && (
          <div className="alert-banner alert-error" style={{ marginBottom: '1rem' }}>
            <AlertCircle size={18} />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          
          {/* SECTION 1: CUSTOMER SELECTION */}
          <div className="pos-card" style={{ background: 'var(--bg-primary)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--bg-card-border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <label style={{ fontSize: '0.88rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.4rem', margin: 0 }}>
                <User size={16} className="text-primary" /> Customer Information
              </label>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setIsNewCustomer(!isNewCustomer);
                  setErrorMsg('');
                }}
              >
                {isNewCustomer ? 'Select Existing Customer' : '+ New Walk-in Customer'}
              </button>
            </div>

            {!isNewCustomer ? (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                      Search by Name or Phone:
                    </label>
                    <div style={{ position: 'relative' }}>
                      <Search size={14} style={{ position: 'absolute', left: '10px', top: '11px', color: 'var(--text-muted)' }} />
                      <input
                        type="text"
                        placeholder="Search Dhruv, Faizan, 91987..."
                        value={customerSearch}
                        onChange={(e) => setCustomerSearch(e.target.value)}
                        className="form-control"
                        style={{ paddingLeft: '2rem' }}
                      />
                    </div>
                  </div>

                  <div>
                    <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                      Select Customer ({filteredCustomers.length} matches):
                    </label>
                    <select
                      className="form-control"
                      value={selectedCustomerId}
                      onChange={(e) => setSelectedCustomerId(e.target.value)}
                      required={!isNewCustomer}
                    >
                      <option value="">-- Choose Customer --</option>
                      {filteredCustomers.map((c) => {
                        const cid = c.customer_id || c.id;
                        const cname = c.name || c.customer_name || 'Unknown';
                        const cphone = c.phone_number || c.customer_phone || '';
                        return (
                          <option key={cid} value={cid}>
                            {cname} ({cphone})
                          </option>
                        );
                      })}
                    </select>
                  </div>
                </div>

                {/* Selected Customer Preview Card */}
                {currentCustomer && (
                  <div style={{ marginTop: '0.75rem', padding: '0.65rem 0.85rem', background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--bg-card-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div style={{ fontSize: '0.82rem' }}>
                      <strong>{currentCustomer.name || currentCustomer.customer_name}</strong> • <span>{currentCustomer.phone_number || currentCustomer.customer_phone}</span>
                      {(currentCustomer.saved_address || currentCustomer.flat_address) && (
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.76rem', marginTop: '0.15rem' }}>
                          <MapPin size={11} style={{ display: 'inline', marginRight: '3px' }} />
                          {currentCustomer.saved_address || currentCustomer.flat_address}
                        </div>
                      )}
                    </div>

                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      {currentCustomer.bot_paused && (
                        <span className="badge badge-paused" style={{ fontSize: '0.72rem' }}>
                          ⏸️ Bot Paused
                        </span>
                      )}
                      <span className="badge badge-order" style={{ fontSize: '0.72rem' }}>
                        📦 {currentCustomer.order_count || 0} Orders
                      </span>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* Inline New Customer Form */
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                    Customer Full Name:
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Ramesh Shah"
                    value={newCustName}
                    onChange={(e) => setNewCustName(e.target.value)}
                    className="form-control"
                    required={isNewCustomer}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                    Mobile Number (10 Digits):
                  </label>
                  <input
                    type="tel"
                    placeholder="e.g. 9876543210"
                    value={newCustPhone}
                    onChange={(e) => setNewCustPhone(e.target.value)}
                    className="form-control"
                    required={isNewCustomer}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                    Address (Optional for counter):
                  </label>
                  <input
                    type="text"
                    placeholder="Society, Flat, Paldi..."
                    value={newCustAddress}
                    onChange={(e) => setNewCustAddress(e.target.value)}
                    className="form-control"
                  />
                </div>
              </div>
            )}
          </div>

          {/* SECTION 2: ORDER TYPE (STRICTLY 2 CHOICES: STORE_DROP vs PICKUP) */}
          <div>
            <label style={{ fontSize: '0.88rem', fontWeight: 700, display: 'block', marginBottom: '0.5rem' }}>
              Order Logistics Type:
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <button
                type="button"
                className={`order-type-btn ${orderType === 'STORE_DROP' ? 'active' : ''}`}
                onClick={() => setOrderType('STORE_DROP')}
                style={{
                  padding: '0.85rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  border: orderType === 'STORE_DROP' ? '2px solid #2563eb' : '1px solid var(--bg-card-border)',
                  background: orderType === 'STORE_DROP' ? 'rgba(37, 99, 246, 0.12)' : 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  textAlign: 'left',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem'
                }}
              >
                <div style={{ background: '#2563eb', color: '#fff', padding: '0.6rem', borderRadius: '8px' }}>
                  <Store size={22} />
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>🏬 Store Walk-in</div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>Customer drops & collects at shop counter (₹0 fee)</div>
                </div>
              </button>

              <button
                type="button"
                className={`order-type-btn ${orderType === 'PICKUP' ? 'active' : ''}`}
                onClick={() => setOrderType('PICKUP')}
                style={{
                  padding: '0.85rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  border: orderType === 'PICKUP' ? '2px solid #a855f7' : '1px solid var(--bg-card-border)',
                  background: orderType === 'PICKUP' ? 'rgba(168, 85, 247, 0.12)' : 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  textAlign: 'left',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem'
                }}
              >
                <div style={{ background: '#a855f7', color: '#fff', padding: '0.6rem', borderRadius: '8px' }}>
                  <Truck size={22} />
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>🚚 Pickup & Delivery</div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>Runner collects from home & delivers back (₹30 fee)</div>
                </div>
              </button>
            </div>
          </div>

          {/* Address field for Pickup orders */}
          {orderType === 'PICKUP' && (
            <div>
              <label style={{ fontSize: '0.82rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.3rem' }}>
                <MapPin size={14} className="text-primary" /> Pickup & Delivery Home Address: <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                type="text"
                className="form-control"
                placeholder="Enter complete flat / house address in Paldi area..."
                value={flatAddress}
                onChange={(e) => setFlatAddress(e.target.value)}
                required={orderType === 'PICKUP'}
              />
            </div>
          )}

          {/* SECTION 3: SERVICE CATEGORY & GARMENTS BREAKDOWN */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <label style={{ fontSize: '0.88rem', fontWeight: 700, margin: 0 }}>
                Garments Breakdown (Auto-Pricing Catalog):
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Default Service:</span>
                <select
                  className="form-control form-control-sm"
                  style={{ width: '160px', padding: '0.3rem 0.5rem', fontSize: '0.8rem' }}
                  value={serviceCategory}
                  onChange={(e) => handleDefaultServiceChange(e.target.value)}
                >
                  {SERVICE_TYPES.map((st) => (
                    <option key={st.id} value={st.id}>{st.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Line items table */}
            <div style={{ border: '1px solid var(--bg-card-border)', borderRadius: 'var(--radius-md)', overflow: 'visible', background: 'var(--bg-card)' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--bg-card-border)', textAlign: 'left' }}>
                    <th style={{ padding: '0.6rem 0.75rem', width: '20%' }}>Service Type</th>
                    <th style={{ padding: '0.6rem 0.75rem', width: '45%' }}>Garment Name</th>
                    <th style={{ padding: '0.6rem 0.4rem', width: '8%', textAlign: 'center' }}>Qty</th>
                    <th style={{ padding: '0.6rem 0.75rem', width: '13%' }}>Price (₹)</th>
                    <th style={{ padding: '0.6rem 0.75rem', width: '10%' }}>Total</th>
                    <th style={{ padding: '0.6rem 0.5rem', width: '4%', textAlign: 'center' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row, idx) => {
                    const lineTotal = (Number(row.price) || 0) * (Number(row.quantity) || 1);

                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid var(--bg-card-border)' }}>
                        <td style={{ padding: '0.5rem 0.75rem' }}>
                          <select
                            className="form-control form-control-sm"
                            value={row.service_type}
                            onChange={(e) => handleItemChange(idx, 'service_type', e.target.value)}
                          >
                            {SERVICE_TYPES.map((st) => (
                              <option key={st.id} value={st.id}>{st.id}</option>
                            ))}
                          </select>
                        </td>

                        <td style={{ padding: '0.5rem 0.75rem', position: 'relative' }}>
                          <GarmentCombobox
                            value={row.garment_type}
                            onChange={(name) => handleItemChange(idx, 'garment_type', name)}
                            onSelectGarment={(name, price) => {
                              handleItemChange(idx, 'garment_type', name);
                              if (price != null) {
                                handleItemChange(idx, 'price', price);
                              }
                            }}
                            garmentList={getGarmentsWithPricesForService(row.service_type)}
                            placeholder="Type or select garment..."
                          />
                        </td>

                        <td style={{ padding: '0.5rem 0.4rem', textAlign: 'center' }}>
                          <input
                            type="number"
                            min="1"
                            className="form-control form-control-sm"
                            style={{ textAlign: 'center', padding: '0.3rem 0.2rem' }}
                            value={row.quantity}
                            onChange={(e) => handleItemChange(idx, 'quantity', Math.max(1, parseInt(e.target.value) || 1))}
                            required
                          />
                        </td>

                        <td style={{ padding: '0.5rem 0.75rem' }}>
                          <input
                            type="number"
                            min="0"
                            step="5"
                            className="form-control form-control-sm"
                            value={row.price}
                            onChange={(e) => handleItemChange(idx, 'price', parseFloat(e.target.value) || 0)}
                            required
                          />
                        </td>

                        <td style={{ padding: '0.5rem 0.75rem', fontWeight: 700 }}>
                          ₹{lineTotal}
                        </td>

                        <td style={{ padding: '0.5rem 0.5rem', textAlign: 'center' }}>
                          <button
                            type="button"
                            className="btn-icon text-danger"
                            onClick={() => handleRemoveItem(idx)}
                            disabled={items.length <= 1}
                            title="Remove Garment"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              <div style={{ padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleAddItem}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                >
                  <Plus size={14} /> + Add Another Garment
                </button>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  Total Pieces: <strong>{items.reduce((s, i) => s + (Number(i.quantity) || 1), 0)} pcs</strong>
                </div>
              </div>
            </div>
          </div>

          {/* SECTION 4: BILLING & PAYMENT SUMMARY */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            {/* Left: Notes & Runner */}
            <div>
              <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                Special Instructions / Stain Notes:
              </label>
              <textarea
                rows="2"
                className="form-control"
                placeholder="e.g. Coffee stain on white shirt collar, deliver before Friday evening..."
                value={specialInstructions}
                onChange={(e) => setSpecialInstructions(e.target.value)}
              />

              <div style={{ marginTop: '0.5rem' }}>
                <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                  Assign Staff Runner (Optional):
                </label>
                <select
                  className="form-control"
                  value={selectedRunnerId}
                  onChange={(e) => setSelectedRunnerId(e.target.value)}
                >
                  <option value="">-- No Runner Assigned --</option>
                  {runners.map((r) => (
                    <option key={r.runner_id} value={r.runner_id}>{r.name} ({r.phone_number})</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Right: Payment Status & Bill Box */}
            <div style={{ background: 'var(--bg-primary)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--bg-card-border)' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <div>
                  <label style={{ fontSize: '0.76rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.2rem' }}>
                    Payment Status:
                  </label>
                  <select
                    className="form-control form-control-sm"
                    value={paymentStatus}
                    onChange={(e) => setPaymentStatus(e.target.value)}
                  >
                    <option value="PENDING">Unpaid (Pending)</option>
                    <option value="PAID">Paid (Completed)</option>
                  </select>
                </div>

                {paymentStatus === 'PAID' && (
                  <div>
                    <label style={{ fontSize: '0.76rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.2rem' }}>
                      Payment Mode:
                    </label>
                    <select
                      className="form-control form-control-sm"
                      value={paymentMode}
                      onChange={(e) => setPaymentMode(e.target.value)}
                    >
                      <option value="CASH">Cash 💵</option>
                      <option value="UPI">UPI / GPay 📱</option>
                    </select>
                  </div>
                )}
              </div>

              {/* Bill Details */}
              <div style={{ fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '0.35rem', borderTop: '1px solid var(--bg-card-border)', paddingTop: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Garments Subtotal:</span>
                  <strong>₹{subtotal}</strong>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>
                    Delivery Fee ({orderType === 'STORE_DROP' ? 'Store Walk-in' : 'Runner Delivery'}):
                  </span>
                  <span>{deliveryFee === 0 ? <strong className="text-success">FREE (₹0)</strong> : `₹${deliveryFee}`}</span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '1.05rem', borderTop: '1px solid var(--bg-card-border)', paddingTop: '0.4rem', color: '#2563eb' }}>
                  <strong>Final Amount:</strong>
                  <strong>₹{totalPayable}</strong>
                </div>
              </div>
            </div>
          </div>

          {/* SECTION 5: AI BOT RESUME & WHATSAPP RECEIPT CHECKBOXES */}
          <div style={{ background: 'rgba(59, 130, 246, 0.08)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid rgba(59, 130, 246, 0.25)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.84rem', cursor: 'pointer', margin: 0 }}>
              <input
                type="checkbox"
                checked={sendWhatsAppReceipt}
                onChange={(e) => setSendWhatsAppReceipt(e.target.checked)}
                style={{ width: '16px', height: '16px' }}
              />
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                <Send size={14} className="text-primary" /> Send instant WhatsApp Order Confirmation receipt to customer
              </span>
            </label>

            {currentCustomer && currentCustomer.bot_paused && (
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.84rem', cursor: 'pointer', margin: 0, color: '#f59e0b' }}>
                <input
                  type="checkbox"
                  checked={resumeBot}
                  onChange={(e) => setResumeBot(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                  <Bot size={14} /> Resume AI Bot for this customer & reset state machine to IDLE
                </span>
              </label>
            )}
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.65rem 1.5rem', fontWeight: 700 }}>
              {submitting ? 'Creating Order...' : `Confirm & Bill Order (₹${totalPayable})`}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
