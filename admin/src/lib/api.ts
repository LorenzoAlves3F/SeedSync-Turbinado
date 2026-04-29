import axios, { AxiosError } from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: API_URL });

// Global error interceptor — converts network/HTTP errors to readable messages
api.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ detail?: string }>) => {
    const detail = err.response?.data?.detail;
    const message = detail
      ? String(detail)
      : err.message || 'Unknown network error';
    return Promise.reject(new Error(message));
  }
);

// ─── Types ───────────────────────────────────────────────

export interface SourceConfig {
  id: string;
  client_id: string;
  name: string;
  ingestion_mode: 'sheet' | 'webhook';
  conta_id: number | null;
  sheet_id: string;
  worksheet_name: string;
  target_table: string;
  phone_column: string;
  name_column: string;
  required_columns: string[];
  destination_phones: string[];
  clickup_enabled: boolean;
  clickup_list_id: string | null;
  active: boolean;
  last_row_index: number;
  google_sa_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Conta {
  id: number;
  conta: string;
  mql: boolean | null;
}

export interface ConfigStats {
  total: number;
  active: number;
  inactive: number;
}

export interface IngestionLog {
  id: number;
  client_id: string;
  row_fingerprint: string;
  status: string;
  whatsapp_status: string | null;
  raw_payload: Record<string, unknown> | null;
  processed_at: string;
}

// ─── Configs ─────────────────────────────────────────────

export const fetchConfigs = () => api.get<SourceConfig[]>('/configs').then(r => r.data);

export const fetchConfigStats = () => api.get<ConfigStats>('/configs/stats').then(r => r.data);

export const fetchConfig = (clientId: string) =>
  api.get<SourceConfig>(`/configs/${clientId}`).then(r => r.data);

export const createConfig = (data: Partial<SourceConfig>) =>
  api.post<SourceConfig[]>('/configs', data).then(r => r.data);

export const updateConfig = (clientId: string, data: Partial<SourceConfig>) =>
  api.patch<SourceConfig[]>(`/configs/${clientId}`, data).then(r => r.data);

export const deleteConfig = (clientId: string) =>
  api.delete(`/configs/${clientId}`).then(r => r.data);

export const resetCursor = (clientId: string, rowIndex: number) =>
  api.post<SourceConfig>(`/configs/${clientId}/reset-cursor`, { row_index: rowIndex }).then(r => r.data);

// ─── Bulk Operations ─────────────────────────────────────

export const syncReset = () =>
  api.post<{ status: string; cluster_size: number; buffer_size: number }>('/configs/sync-reset')
    .then(r => r.data);

// ─── Logs ────────────────────────────────────────────────

export const fetchLogs = (params?: {
  limit?: number;
  client_id?: string;
  status?: string;
  whatsapp_status?: string;
}) => api.get<IngestionLog[]>('/logs', { params }).then(r => r.data);

// ─── Queue ───────────────────────────────────────────────

export interface QueueEntry {
  id: number;
  client_id: string;
  destination_phone: string;
  message: string;
  lead_fingerprint: string;
  retry_count: number;
  next_retry_at: string;
  status: 'pending' | 'sent' | 'dead';
  last_error: string | null;
  created_at: string;
}

export interface QueueStats {
  pending: number;
  dead: number;
  dead_entries: QueueEntry[];
  recent: QueueEntry[];
}

export const fetchQueueStats = () => api.get<QueueStats>('/queue').then(r => r.data);

export const resetDeadQueue = () =>
  api.post<{ reset: number; entries: QueueEntry[] }>('/queue/reset-dead').then(r => r.data);

export const retrySelectedQueue = (ids: number[]) =>
  api.post<{ reset: number; entries: QueueEntry[] }>('/queue/retry-selected', { ids }).then(r => r.data);

// ─── Contas ──────────────────────────────────────────────

export const fetchContas = () => api.get<Conta[]>('/contas').then(r => r.data);

// ─── Sheets ──────────────────────────────────────────────

export const fetchWorksheets = (sheetId: string) =>
  api.get<{ id: string; title: string }[]>(`/sheets/${sheetId}/worksheets`).then(r => r.data);

export const fetchColumns = (sheetId: string, wsName: string) =>
  api.get<string[]>(`/sheets/${sheetId}/worksheets/${wsName}/columns`).then(r => r.data);

export default api;
