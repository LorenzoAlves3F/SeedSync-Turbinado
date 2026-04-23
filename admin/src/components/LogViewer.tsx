import React, { useEffect, useState, useCallback } from 'react';
import {
  ListFilter, RefreshCw, Loader2, FileText,
  CheckCircle2, XCircle, AlertTriangle, Copy,
  Search, Calendar, ChevronDown, MessageSquare
} from 'lucide-react';
import { fetchLogs, fetchConfigs, type IngestionLog, type SourceConfig } from '../lib/api';
import { ToastContainer } from './Toast';
import { useToast } from '../hooks/useToast';

const STATUS_VARIANTS: Record<string, { bg: string, text: string, icon: React.ElementType }> = {
  inserted: { bg: 'bg-emerald-500/10', text: 'text-emerald-600', icon: CheckCircle2 },
  duplicate: { bg: 'bg-amber-500/10', text: 'text-amber-600', icon: Copy },
  error: { bg: 'bg-red-500/10', text: 'text-red-600', icon: XCircle },
  invalid: { bg: 'bg-orange-500/10', text: 'text-orange-600', icon: AlertTriangle },
};

const WA_VARIANTS: Record<string, string> = {
  sent: 'text-emerald-600 bg-emerald-50',
  delivered: 'text-blue-600 bg-blue-50',
  failed: 'text-red-600 bg-red-50',
  skipped: 'text-slate-400 bg-slate-50',
  queued: 'text-amber-600 bg-amber-50',
};

interface LogViewerProps {
  initialClientId?: string;
  onClearFilter?: () => void;
}

const LogViewer: React.FC<LogViewerProps> = ({ initialClientId, onClearFilter }) => {
  const [logs, setLogs] = useState<IngestionLog[]>([]);
  const [clients, setClients] = useState<SourceConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const { toasts, addToast, dismissToast } = useToast();

  const [filterClient, setFilterClient] = useState(initialClientId || '');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterWa, setFilterWa] = useState('');
  const [limit, setLimit] = useState(100);

  useEffect(() => {
    if (initialClientId) setFilterClient(initialClientId);
  }, [initialClientId]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { limit };
      if (filterClient) params.client_id = filterClient;
      if (filterStatus) params.status = filterStatus;
      if (filterWa) params.whatsapp_status = filterWa;

      const [logsData, clientsData] = await Promise.all([
        fetchLogs(params),
        clients.length ? Promise.resolve(clients) : fetchConfigs(),
      ]);
      setLogs(logsData);
      if (!clients.length) setClients(clientsData);
    } catch (e: unknown) {
      const err = e instanceof Error ? e : new Error('Erro de rede');
      addToast('error', 'Falha ao carregar logs', err.message);
    } finally {
      setLoading(false);
    }
  }, [filterClient, filterStatus, filterWa, limit, clients, addToast]);

  useEffect(() => { load(); }, [load]);

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return {
      date: d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }),
      time: d.toLocaleTimeString('pt-BR', { hour12: false, hour: '2-digit', minute: '2-digit' })
    };
  };

  return (
    <div className="mesh-bg min-h-screen p-10 pb-20 space-y-10 animate-in fade-in duration-500">
      {/* Cabeçalho */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
           <div className="flex items-center gap-2 mb-2">
            <ListFilter className="text-emerald-500" size={14} />
            <span className="text-[10px] font-black text-emerald-600 uppercase tracking-[0.3em]">Auditoria</span>
          </div>
          <h2 className="text-5xl font-black text-slate-900 tracking-tight leading-none">
            Histórico de <span className="text-emerald-500 italic">Eventos</span>
          </h2>
          <p className="text-slate-500 font-medium mt-2">Analisando {logs.length} eventos em todos os pipelines.</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-3 px-6 py-4 bg-white border border-slate-200 rounded-2xl text-sm font-black text-slate-700 hover:bg-slate-50 hover:shadow-lg transition-all"
        >
          <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          Atualizar
        </button>
      </header>

      {/* Filtros */}
      <div className="bg-white/60 backdrop-blur-xl p-6 rounded-[2.5rem] border border-white/40 shadow-2xl shadow-slate-200/50 flex flex-wrap items-center gap-4">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
          <select
            value={filterClient}
            onChange={e => {
              setFilterClient(e.target.value);
              if (!e.target.value) onClearFilter?.();
            }}
            className="w-full pl-12 pr-10 py-4 rounded-2xl border border-slate-200 bg-white/80 focus:bg-white outline-none appearance-none font-bold text-sm text-slate-700 focus:ring-4 focus:ring-emerald-50 transition-all shadow-sm"
          >
            <option value="">Todos os Pipelines</option>
            {clients.map(c => (
              <option key={c.client_id} value={c.client_id}>{c.name}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={16} />
        </div>

        <div className="relative">
          <select
            value={filterStatus}
            onChange={e => setFilterStatus(e.target.value)}
            className="pl-4 pr-10 py-4 rounded-2xl border border-slate-200 bg-white/80 focus:bg-white outline-none appearance-none font-bold text-sm text-slate-700 shadow-sm"
          >
            <option value="">Todos os Status</option>
            <option value="inserted">Inserido</option>
            <option value="duplicate">Duplicado</option>
            <option value="error">Erro</option>
            <option value="invalid">Inválido</option>
          </select>
          <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={16} />
        </div>

        <div className="relative">
          <select
            value={filterWa}
            onChange={e => setFilterWa(e.target.value)}
            className="pl-4 pr-10 py-4 rounded-2xl border border-slate-200 bg-white/80 focus:bg-white outline-none appearance-none font-bold text-sm text-slate-700 shadow-sm"
          >
            <option value="">Notif.: Todos</option>
            <option value="sent">Enviado</option>
            <option value="delivered">Entregue</option>
            <option value="queued">Na Fila</option>
            <option value="failed">Falhou</option>
            <option value="skipped">Desativado</option>
          </select>
          <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={16} />
        </div>

        <div className="relative">
          <select
            value={limit}
            onChange={e => setLimit(Number(e.target.value))}
            className="pl-4 pr-10 py-4 rounded-2xl border border-slate-200 bg-white shadow-sm font-bold text-sm text-slate-700 appearance-none"
          >
            <option value={100}>100 Registros</option>
            <option value={250}>250 Registros</option>
            <option value={500}>500 Registros</option>
          </select>
          <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={16} />
        </div>
      </div>

      {/* Tabela */}
      {loading && logs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 gap-4">
           <Loader2 className="animate-spin text-emerald-500 opacity-20" size={64} strokeWidth={1} />
           <p className="text-xs font-black text-slate-400 uppercase tracking-[0.4em]">Consultando arquivo...</p>
        </div>
      ) : logs.length === 0 ? (
        <div className="bg-white rounded-[3rem] p-24 text-center border border-slate-100 shadow-2xl">
          <div className="w-20 h-20 bg-slate-50 rounded-[2rem] flex items-center justify-center mx-auto mb-8 border border-slate-100">
            <FileText size={32} className="text-slate-300" />
          </div>
          <h3 className="text-2xl font-black text-slate-900 tracking-tight">Sem Registros</h3>
          <p className="text-slate-500 mt-2 font-medium">Nenhum evento encontrado com os filtros atuais.</p>
          <button
            onClick={() => { setFilterClient(''); setFilterStatus(''); setFilterWa(''); }}
            className="mt-8 text-emerald-600 font-black text-xs uppercase tracking-widest hover:underline"
          >
            Limpar Filtros
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-[3rem] border border-slate-100 shadow-2xl shadow-slate-200/40 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50/50 border-b border-slate-100">
                  <th className="px-10 py-6 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Data/Hora</th>
                  <th className="px-10 py-6 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Pipeline</th>
                  <th className="px-10 py-6 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Status</th>
                  <th className="px-10 py-6 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Notificação</th>
                  <th className="px-10 py-6 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Dados</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {logs.map(log => {
                  const stamp = formatDate(log.processed_at);
                  const status = STATUS_VARIANTS[log.status] || { bg: 'bg-slate-100', text: 'text-slate-600', icon: AlertTriangle };
                  const waClass = WA_VARIANTS[log.whatsapp_status || ''] || 'text-slate-400 bg-slate-50';

                  return (
                    <tr key={log.id} className="group hover:bg-slate-50/50 transition-all cursor-pointer">
                      <td className="px-10 py-7">
                        <div className="flex items-center gap-3">
                          <div className="p-2.5 bg-slate-50 rounded-xl text-slate-400 group-hover:bg-white group-hover:text-emerald-500 transition-all border border-transparent group-hover:border-slate-100">
                             <Calendar size={16} />
                          </div>
                          <div>
                            <p className="text-sm font-black text-slate-900 leading-none mb-1">{stamp.date}</p>
                            <p className="text-xs font-bold text-slate-400 font-mono">{stamp.time}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-10 py-7">
                        <p className="text-sm font-black text-slate-900 group-hover:text-emerald-600 transition-colors">{log.client_id}</p>
                        <p className="text-[10px] font-bold text-slate-400 mt-1 uppercase tracking-tight">Pipeline Ativo</p>
                      </td>
                      <td className="px-10 py-7">
                        <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-2xl font-black text-[10px] uppercase tracking-tighter ${status.bg} ${status.text}`}>
                          <status.icon size={12} />
                          {log.status}
                        </div>
                      </td>
                      <td className="px-10 py-7">
                         <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl font-black text-[9px] uppercase tracking-widest border border-transparent ${waClass}`}>
                           <MessageSquare size={10} />
                           {log.whatsapp_status || 'PENDENTE'}
                         </div>
                      </td>
                      <td className="px-10 py-7">
                        {log.raw_payload ? (
                          <details className="group/payload">
                            <summary className="list-none flex items-center gap-2 text-[11px] font-black text-emerald-600 uppercase tracking-widest hover:underline cursor-pointer">
                              Ver Dados
                              <ChevronDown size={14} className="group-open/payload:rotate-180 transition-transform" />
                            </summary>
                            <div className="mt-4 p-6 bg-[#0A0D12] rounded-[1.5rem] border border-[#151D2A] relative overflow-hidden">
                               <pre className="text-[11px] leading-relaxed text-emerald-400/80 font-mono overflow-x-auto custom-scrollbar">
                                 {JSON.stringify(log.raw_payload, null, 2)}
                               </pre>
                               <div className="absolute top-2 right-2 flex gap-1">
                                 <div className="w-1.5 h-1.5 rounded-full bg-red-500/20" />
                                 <div className="w-1.5 h-1.5 rounded-full bg-amber-500/20" />
                                 <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/20" />
                               </div>
                            </div>
                          </details>
                        ) : (
                          <span className="text-slate-300 text-[10px] font-black uppercase tracking-widest">Sem Dados</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};

export default LogViewer;
