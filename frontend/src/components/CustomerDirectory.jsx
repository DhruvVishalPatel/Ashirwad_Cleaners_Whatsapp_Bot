import React, { useState } from 'react';
import { Search, Save, MapPin } from 'lucide-react';
import { api } from '../api';

export default function CustomerDirectory({ customers, onRefresh }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [editedCustomers, setEditedCustomers] = useState({});
  const [message, setMessage] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const handleInputChange = (customerId, field, value) => {
    setEditedCustomers((prev) => ({
      ...prev,
      [customerId]: {
        ...prev[customerId],
        [field]: value,
      },
    }));
  };

  const handleSaveAll = async () => {
    setIsSaving(true);
    setMessage('');
    try {
      const customerIds = Object.keys(editedCustomers);
      for (const id of customerIds) {
        const payload = editedCustomers[id];
        await api.updateCustomer(id, payload);
      }
      setMessage('✅ Customer data saved successfully!');
      setEditedCustomers({});
      onRefresh();
    } catch (err) {
      setMessage(`❌ Error saving customer: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const filteredCustomers = customers.filter((c) => {
    const q = searchTerm.toLowerCase();
    return (
      (c.name && c.name.toLowerCase().includes(q)) ||
      (c.phone_number && c.phone_number.includes(q)) ||
      (c.saved_address && c.saved_address.toLowerCase().includes(q))
    );
  });

  const hasChanges = Object.keys(editedCustomers).length > 0;

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '1.25rem' }}>
        <div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>👥 Customer Database</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            View registered customers and edit saved pickup addresses or GPS coordinates directly.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <div style={{ position: 'relative', minWidth: '260px' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Search Name, Phone, Address..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ width: '100%', paddingLeft: '2.25rem' }}
            />
            <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          </div>

          <button
            className="btn btn-primary"
            onClick={handleSaveAll}
            disabled={!hasChanges || isSaving}
          >
            <Save size={16} /> Save Changes
          </button>
        </div>
      </div>

      {message && (
        <div className={`alert-banner ${message.startsWith('✅') ? 'alert-success' : 'alert-error'}`}>
          {message}
        </div>
      )}

      <div className="table-responsive">
        <table className="custom-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Phone</th>
              <th>Saved Address (Editable)</th>
              <th>GPS Coordinates (Editable)</th>
              <th>Points</th>
              <th>Orders</th>
            </tr>
          </thead>
          <tbody>
            {filteredCustomers.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  No customers found.
                </td>
              </tr>
            ) : (
              filteredCustomers.map((c) => {
                const draft = editedCustomers[c.customer_id] || {};
                const addressVal = draft.saved_address !== undefined ? draft.saved_address : c.saved_address;
                const gpsVal = draft.last_location_gps !== undefined ? draft.last_location_gps : c.last_location_gps;

                return (
                  <tr key={c.customer_id}>
                    <td>#{c.customer_id}</td>
                    <td style={{ fontWeight: 600 }}>{c.name}</td>
                    <td>{c.phone_number}</td>
                    <td style={{ minWidth: '220px' }}>
                      <input
                        type="text"
                        className="form-control"
                        value={addressVal}
                        onChange={(e) => handleInputChange(c.customer_id, 'saved_address', e.target.value)}
                      />
                    </td>
                    <td style={{ minWidth: '200px' }}>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        <input
                          type="text"
                          className="form-control"
                          value={gpsVal}
                          onChange={(e) => handleInputChange(c.customer_id, 'last_location_gps', e.target.value)}
                        />
                        {gpsVal && (
                          <a
                            href={`https://www.google.com/maps?q=${gpsVal}`}
                            target="_blank"
                            rel="noreferrer"
                            title="Open in Maps"
                            style={{ color: 'var(--accent-info)' }}
                          >
                            <MapPin size={16} />
                          </a>
                        )}
                      </div>
                    </td>
                    <td style={{ fontWeight: 700, color: 'var(--accent-warning)' }}>
                      ⭐ {c.available_points} pts
                    </td>
                    <td>{c.order_count}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
