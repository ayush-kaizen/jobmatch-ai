const BASE_URL = import.meta.env.VITE_API_URL || '';

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };
  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }
  const res = await fetch(url, config);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  // Profile
  getProfile: () => request('/api/profile'),
  updateProfile: (data) => request('/api/profile', { method: 'PUT', body: data }),

  // Companies
  getCompanies: () => request('/api/companies'),
  addCompany: (data) => request('/api/companies', { method: 'POST', body: data }),
  deleteCompany: (id) => request(`/api/companies/${id}`, { method: 'DELETE' }),
  getCompanyIntel: (id) => request(`/api/companies/${id}/intel`),

  // Jobs
  getJobs: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/jobs${qs ? '?' + qs : ''}`);
  },

  // Scan
  runScan: (companyIds = null) =>
    request('/api/scan', { method: 'POST', body: { company_ids: companyIds } }),

  // Cover letter
  generateCoverLetter: (jobId) =>
    request(`/api/jobs/${jobId}/cover-letter`, { method: 'POST' }),

  // Stats
  getStats: () => request('/api/stats'),

  // Health
  health: () => request('/api/health'),
};
