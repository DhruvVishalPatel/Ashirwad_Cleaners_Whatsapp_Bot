import React, { useState } from 'react';
import { Save, Plus, Trash2, Tag } from 'lucide-react';
import { api } from '../api';

const CATEGORIES = [
  { label: 'Dry Clean', key: 'dry_clean' },
  { label: 'Washing', key: 'washing' },
  { label: 'Steam Press', key: 'steam_press' },
  { label: 'Petrol Wash', key: 'petrol_wash' },
];

export default function CatalogManager({ catalog, onRefresh }) {
  const [activeCategory, setActiveCategory] = useState('dry_clean');
  const [editedItems, setEditedItems] = useState({});
  const [message, setMessage] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // New Item form state
  const [newName, setNewName] = useState('');
  const [newPrice, setNewPrice] = useState(50.0);
  const [newIsVariable, setNewIsVariable] = useState(false);
  const [newNote, setNewNote] = useState('');

  const currentCategoryItems = catalog.filter((c) => c.service_type === activeCategory);

  const handleInputChange = (itemId, field, value) => {
    setEditedItems((prev) => ({
      ...prev,
      [itemId]: {
        ...prev[itemId],
        [field]: value,
      },
    }));
  };

  const handleSaveGridChanges = async () => {
    setIsSaving(true);
    setMessage('');
    try {
      const itemIds = Object.keys(editedItems);
      for (const id of itemIds) {
        const item = catalog.find((c) => c.id === parseInt(id));
        const draft = editedItems[id];
        const payload = {
          item_name: draft.item_name !== undefined ? draft.item_name : item.item_name,
          price: draft.price !== undefined ? parseFloat(draft.price) : item.price,
          is_variable: draft.is_variable !== undefined ? draft.is_variable : item.is_variable,
          note: draft.note !== undefined ? draft.note : item.note,
        };
        await api.updateCatalogItem(id, payload);
      }
      setMessage('✅ Catalog grid changes saved successfully!');
      setEditedItems({});
      onRefresh();
    } catch (err) {
      setMessage(`❌ Error saving catalog grid: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateCatalogItem = async (e) => {
    e.preventDefault();
    if (!newName) return;
    setIsSaving(true);
    setMessage('');
    try {
      await api.createCatalogItem({
        service_type: activeCategory,
        item_name: newName,
        price: parseFloat(newPrice),
        is_variable: newIsVariable,
        note: newNote,
      });
      setMessage(`✅ Added '${newName}' to catalog!`);
      setNewName('');
      setNewPrice(50.0);
      setNewIsVariable(false);
      setNewNote('');
      onRefresh();
    } catch (err) {
      setMessage(`❌ Error adding catalog item: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteItem = async (itemId, itemName) => {
    if (!window.confirm(`Are you sure you want to delete '${itemName}' from catalog?`)) return;
    setIsSaving(true);
    try {
      await api.deleteCatalogItem(itemId);
      setMessage(`✅ Deleted '${itemName}' from catalog.`);
      onRefresh();
    } catch (err) {
      setMessage(`❌ Error deleting catalog item: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const hasChanges = Object.keys(editedItems).length > 0;

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>🏷️ Price Catalog Manager</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Manage global services and garment base prices dynamically across all 4 categories.
        </p>
      </div>

      {/* Category Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', overflowX: 'auto', paddingBottom: '0.25rem' }}>
        {CATEGORIES.map((cat) => (
          <button
            key={cat.key}
            className={`btn ${activeCategory === cat.key ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => {
              setActiveCategory(cat.key);
              setEditedItems({});
            }}
          >
            <Tag size={14} /> {cat.label}
          </button>
        ))}
      </div>

      {message && (
        <div className={`alert-banner ${message.startsWith('✅') ? 'alert-success' : 'alert-error'}`}>
          {message}
        </div>
      )}

      {/* Catalog Items Table */}
      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h4 style={{ fontSize: '1rem', fontWeight: 700 }}>
            {CATEGORIES.find((c) => c.key === activeCategory)?.label} Pricing Grid
          </h4>
          <button
            className="btn btn-primary btn-sm"
            onClick={handleSaveGridChanges}
            disabled={!hasChanges || isSaving}
          >
            <Save size={14} /> Save Grid Changes
          </button>
        </div>

        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Garment Name</th>
                <th>Price (₹)</th>
                <th>Variable Price</th>
                <th>Special Notes / Range</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {currentCategoryItems.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>
                    No catalog items currently in this category.
                  </td>
                </tr>
              ) : (
                currentCategoryItems.map((item) => {
                  const draft = editedItems[item.id] || {};
                  const nameVal = draft.item_name !== undefined ? draft.item_name : item.item_name;
                  const priceVal = draft.price !== undefined ? draft.price : item.price;
                  const isVarVal = draft.is_variable !== undefined ? draft.is_variable : item.is_variable;
                  const noteVal = draft.note !== undefined ? draft.note : item.note;

                  return (
                    <tr key={item.id}>
                      <td>#{item.id}</td>
                      <td>
                        <input
                          type="text"
                          className="form-control"
                          value={nameVal}
                          onChange={(e) => handleInputChange(item.id, 'item_name', e.target.value)}
                        />
                      </td>
                      <td style={{ width: '120px' }}>
                        <input
                          type="number"
                          className="form-control"
                          step={5}
                          value={priceVal}
                          onChange={(e) => handleInputChange(item.id, 'price', e.target.value)}
                        />
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={isVarVal}
                          onChange={(e) => handleInputChange(item.id, 'is_variable', e.target.checked)}
                          style={{ accentColor: 'var(--accent-primary)', width: '16px', height: '16px' }}
                        />
                      </td>
                      <td>
                        <input
                          type="text"
                          className="form-control"
                          placeholder="e.g. Range 80-200"
                          value={noteVal}
                          onChange={(e) => handleInputChange(item.id, 'note', e.target.value)}
                        />
                      </td>
                      <td>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDeleteItem(item.id, item.item_name)}
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

      {/* Add New Garment Form */}
      <div className="glass-card">
        <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Plus size={18} /> Add New Garment to {CATEGORIES.find((c) => c.key === activeCategory)?.label}
        </h4>

        <form onSubmit={handleCreateCatalogItem} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', alignItems: 'end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Garment Name</label>
            <input
              type="text"
              className="form-control"
              placeholder="e.g. Saree, Suit, Blanket"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              required
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Base Price (₹)</label>
            <input
              type="number"
              className="form-control"
              min={0}
              step={5}
              value={newPrice}
              onChange={(e) => setNewPrice(e.target.value)}
              required
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', marginTop: '1.5rem' }}>
              <input
                type="checkbox"
                checked={newIsVariable}
                onChange={(e) => setNewIsVariable(e.target.checked)}
                style={{ accentColor: 'var(--accent-primary)', width: '16px', height: '16px' }}
              />
              Variable Price
            </label>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Special Notes / Price Range</label>
            <input
              type="text"
              className="form-control"
              placeholder="e.g. Range 100-300 based on fabric"
              value={newNote}
              onChange={(e) => setNewNote(e.target.value)}
            />
          </div>

          <button className="btn btn-primary" type="submit" disabled={isSaving || !newName}>
            Add Garment to Catalog
          </button>
        </form>
      </div>
    </div>
  );
}
