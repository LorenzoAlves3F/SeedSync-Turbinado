import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: API_URL });

// ─── Types ───────────────────────────────────────────────

export interface SourceConfig {
  id: string;
  client_id: string;
  name: string;
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
  created_at: string;
  updated_at: string;
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

// ─── Logs ────────────────────────────────────────────────

export const fetchLogs = (params?: {
  limit?: number;
  client_id?: string;
  status?: string;
  whatsapp_status?: string;
}) => api.get<IngestionLog[]>('/logs', { params }).then(r => r.data);

// ─── Sheets ──────────────────────────────────────────────

export const fetchWorksheets = (sheetId: string) =>
  api.get<{ id: string; title: string }[]>(`/sheets/${sheetId}/worksheets`).then(r => r.data);

export const fetchColumns = (sheetId: string, wsName: string) =>
  api.get<string[]>(`/sheets/${sheetId}/worksheets/${wsName}/columns`).then(r => r.data);

export default api;
