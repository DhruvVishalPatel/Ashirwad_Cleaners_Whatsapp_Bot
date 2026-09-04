const API_BASE = '/api/v1';

export function getAuthToken() {
  return localStorage.getItem('ashirwad_admin_token') || '';
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem('ashirwad_admin_token', token);
  } else {
    localStorage.removeItem('ashirwad_admin_token');
  }
}

async function request(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errorMsg = data.detail || data.message || 'API Request Failed';
    throw new Error(errorMsg);
  }

  return data;
}

export const api = {
  // Auth
  login: (username, password) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  verifyToken: (token) => request(`/auth/verify?token=${encodeURIComponent(token)}`),

  // Analytics
  getAnalytics: () => request('/orders/analytics'),

  // Orders
  getOrders: (showAll = false) => request(`/orders?show_all=${showAll}`),
  getOrderDetails: (orderId) => request(`/orders/${orderId}`),
  updateOrderItems: (orderId, payload) =>
    request(`/orders/${orderId}/items`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  updateOrderPrice: (orderId, rawPrice) =>
    request(`/orders/${orderId}/price`, {
      method: 'PUT',
      body: JSON.stringify({ raw_price: rawPrice }),
    }),
  updateOrderStatus: (orderId, status, paymentStatus) =>
    request(`/orders/${orderId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status, payment_status: paymentStatus }),
    }),
  dispatchRunner: (orderId, runnerPhone) =>
    request(`/orders/${orderId}/dispatch`, {
      method: 'POST',
      body: JSON.stringify({ runner_phone: runnerPhone }),
    }),
  rejectOrder: (orderId) =>
    request(`/orders/${orderId}/reject`, {
      method: 'POST',
    }),
  cancelOrder: (orderId) =>
    request(`/orders/${orderId}/cancel`, {
      method: 'POST',
    }),

  // Customers
  getCustomers: () => request('/customers'),
  updateCustomer: (customerId, payload) =>
    request(`/customers/${customerId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  // Runners
  getRunners: () => request('/runners'),
  createRunner: (name, phoneNumber) =>
    request('/runners', {
      method: 'POST',
      body: JSON.stringify({ name, phone_number: phoneNumber }),
    }),
  updateRunner: (runnerId, name, phoneNumber) =>
    request(`/runners/${runnerId}`, {
      method: 'PUT',
      body: JSON.stringify({ name, phone_number: phoneNumber }),
    }),
  deleteRunner: (runnerId) =>
    request(`/runners/${runnerId}`, {
      method: 'DELETE',
    }),

  // Catalog
  getCatalog: (serviceType = null) =>
    request(`/catalog${serviceType ? `?service_type=${serviceType}` : ''}`),
  createCatalogItem: (item) =>
    request('/catalog', {
      method: 'POST',
      body: JSON.stringify(item),
    }),
  updateCatalogItem: (itemId, item) =>
    request(`/catalog/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify(item),
    }),
  deleteCatalogItem: (itemId) =>
    request(`/catalog/${itemId}`, {
      method: 'DELETE',
    }),
};
