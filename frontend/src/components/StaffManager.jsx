import React, { useState } from 'react';
import { Save, Trash2, UserPlus, Phone } from 'lucide-react';
import { api } from '../api';

export default function StaffManager({ runners, onRefresh }) {
  const [editedRunners, setEditedRunners] = useState({});
  const [newName, setNewName] = useState('');
  const [newPhone, setNewPhone] = useState('');
  const [message, setMessage] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const handleInputChange = (runnerId, field, value) => {
    setEditedRunners((prev) => ({
      ...prev,
      [runnerId]: {
        ...prev[runnerId],
        [field]: value,
      },
    }));
  };

  const handleSaveStaffChanges = async () => {
    setIsSaving(true);
    setMessage('');
    try {
      const runnerIds = Object.keys(editedRunners);
      for (const id of runnerIds) {
        const runner = runners.find((r) => r.runner_id === parseInt(id));
        const draft = editedRunners[id];
        const name = draft.name !== undefined ? draft.name : runner.name;
        const phone = draft.phone_number !== undefined ? draft.phone_number : runner.phone_number;
        await api.updateRunner(id, name, phone);
      }
      setMessage('✅ Staff details updated successfully!');
      setEditedRunners({});
      onRefresh();
    } catch (err) {
      setMessage(`❌ Error updating staff: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteRunner = async (runnerId, name) => {
    if (!window.confirm(`Are you sure you want to remove staff member '${name}'?`)) return;
    setIsSaving(true);
    try {
      await api.deleteRunner(runnerId);
      setMessage(`✅ Staff member '${name}' deleted.`);
      onRefresh();
    } catch (err) {
      setMessage(`❌ Error deleting staff: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRegisterRunner = async (e) => {
    e.preventDefault();
    if (!newName || !newPhone) return;
    setIsSaving(true);
    setMessage('');
    try {
      await api.createRunner(newName, newPhone);
      setMessage(`✅ Staff member '${newName}' registered successfully!`);
      setNewName('');
      setNewPhone('');
      onRefresh();
    } catch (err) {
      setMessage(`❌ Error registering staff: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const hasChanges = Object.keys(editedRunners).length > 0;

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>🛵 Manage Delivery Staff</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Register new delivery runners or update existing staff WhatsApp contact details.
        </p>
      </div>

      {message && (
        <div className={`alert-banner ${message.startsWith('✅') ? 'alert-success' : 'alert-error'}`}>
          {message}
        </div>
      )}

      {/* Existing Staff Members */}
      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h4 style={{ fontSize: '1rem', fontWeight: 700 }}>Existing Staff Members</h4>
          <button
            className="btn btn-primary btn-sm"
            onClick={handleSaveStaffChanges}
            disabled={!hasChanges || isSaving}
          >
            <Save size={14} /> Save Staff Changes
          </button>
        </div>

        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th>Runner ID</th>
                <th>Runner Name</th>
                <th>WhatsApp Phone (Formatted)</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {runners.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>
                    No runners currently registered.
                  </td>
                </tr>
              ) : (
                runners.map((r) => {
                  const draft = editedRunners[r.runner_id] || {};
                  const nameVal = draft.name !== undefined ? draft.name : r.name;
                  const phoneVal = draft.phone_number !== undefined ? draft.phone_number : r.phone_number;

                  return (
                    <tr key={r.runner_id}>
                      <td>#{r.runner_id}</td>
                      <td>
                        <input
                          type="text"
                          className="form-control"
                          value={nameVal}
                          onChange={(e) => handleInputChange(r.runner_id, 'name', e.target.value)}
                        />
                      </td>
                      <td>
                        <div style={{ position: 'relative' }}>
                          <input
                            type="text"
                            className="form-control"
                            value={phoneVal}
                            onChange={(e) => handleInputChange(r.runner_id, 'phone_number', e.target.value)}
                            style={{ paddingLeft: '2.25rem' }}
                          />
                          <Phone size={14} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                        </div>
                      </td>
                      <td>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDeleteRunner(r.runner_id, r.name)}
                          disabled={isSaving}
                        >
                          <Trash2 size={14} /> Delete
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Register New Staff Member */}
      <div className="glass-card">
        <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <UserPlus size={18} /> Register New Staff Member
        </h4>

        <form onSubmit={handleRegisterRunner} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', alignItems: 'end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Runner Name</label>
            <input
              type="text"
              className="form-control"
              placeholder="e.g. Ramesh Kumar"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              required
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">WhatsApp Phone Number</label>
            <input
              type="text"
              className="form-control"
              placeholder="e.g. 9377718648"
              value={newPhone}
              onChange={(e) => setNewPhone(e.target.value)}
              required
            />
          </div>

          <button className="btn btn-primary" type="submit" disabled={isSaving || !newName || !newPhone}>
            Save Staff Member
          </button>
        </form>
      </div>
    </div>
  );
}
