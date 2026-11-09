/** Typed API Client for Meridian Knowledge Engine */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/v1';

interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, ...fetchOptions } = options;
  
  const url = new URL(`${API_BASE}${endpoint}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.append(key, value);
    });
  }

  const response = await fetch(url.toString(), {
    ...fetchOptions,
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-Slug': 'meridian',
      ...headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }));
    throw new Error(error.detail || error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

export const api = {
  // Query
  ask: (data: {
    query_text: string;
    client_desk?: string;
    vendor_id?: string;
    invoice_date?: string;
    as_of_date?: string;
    invoice_context?: any;
  }) => request<any>('/query/ask', { method: 'POST', body: JSON.stringify(data) }),

  // Tacit
  captureTacit: (data: any) => request<any>('/tacit/capture', { method: 'POST', body: JSON.stringify(data) }),
  listTacit: (params?: any) => request<any>('/tacit/list', { params }),

  // Episodes
  uploadDocument: (file: File, metadata: any) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('metadata', JSON.stringify(metadata));
    return request<any>('/episodes/upload', { method: 'POST', body: formData });
  },
  getEpisodeStatus: (episodeId: string) => request<any>(`/episodes/${episodeId}/status`),

  // Facts
  getFacts: (params: any) => request<any>('/facts', { params }),
  getFactHistory: (factId: string) => request<any>(`/facts/${factId}/history`),

  // Conflicts
  getConflicts: (params?: any) => request<any>('/conflicts', { params }),
  resolveConflict: (conflictId: string, data: any) => request<any>(`/conflicts/${conflictId}/resolve`, { method: 'POST', body: JSON.stringify(data) }),

  // SOP Sync
  getPendingSync: () => request<any>('/sop/sync/pending'),
  generateRedline: (data: any) => request<Blob>('/sop/sync/generate-redline', { method: 'POST', body: JSON.stringify(data) }),
  pushSync: (data: any) => request<any>('/sop/sync/push', { method: 'POST', body: JSON.stringify(data) }),
  getAcknowledgements: (syncId: string) => request<any>(`/sop/sync/acknowledgements?sync_id=${syncId}`),

  // Delivery
  erpEmbed: (data: any) => request<any>('/delivery/erp/embed', { method: 'POST', body: JSON.stringify(data) }),
  sendTeamsMessage: (data: any) => request<any>('/delivery/teams/message', { method: 'POST', body: JSON.stringify(data) }),
  registerWebhook: (data: any) => request<any>('/delivery/webhook/change', { method: 'POST', body: JSON.stringify(data) }),

  // Admin
  runEval: (suite: string) => request<any>(`/admin/eval/run?suite=${suite}`, { method: 'POST' }),
  getEvalResults: (runId: string) => request<any>(`/admin/eval/${runId}/results`),
  setSchemaMode: (mode: 'learned' | 'baseline') => request<any>('/admin/schema/mode', { method: 'POST', body: JSON.stringify({ mode }) }),

  // Health
  health: () => request<any>('/health'),
  healthReady: () => request<any>('/health/ready'),
};

export default api;