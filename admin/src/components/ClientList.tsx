import React, { useEffect, useState } from 'react';
import {
  Search, Trash2, ExternalLink,
  Loader2, RefreshCw, FileText, Settings2,
  Database, Phone, Hash, RotateCcw, Check, X, Webhook
} from 'lucide-react';

import { fetchConfigs, updateConfig, deleteConfig, resetCursor, type SourceConfig } from '../lib/api';

interface ClientListProps {
  onViewLogs?: (clientId: string) => void;
  onEdit?: (config: SourceConfig) => void;
}

const ClientList: React.FC<ClientListProps> = ({ onViewLogs, onEdit }) => {
  const [configs, setConfigs] = useState<SourceConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [toggling, setToggling] = useState<string | null>(null);
  const [resetting, setResetting] = useState<string | null>(null);
  const [resetInputs, setResetInputs] = useState<Record<string, string>>({});

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchConfigs();
      setConfigs(data);
    } catch (e) {
      console.error('Failed to load configs', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleToggle = async (c: SourceConfig) => {
    if (toggling) return;
    setToggling(c.client_id);
    try {
      await updateConfig(c.client_id, { active: !c.active });
      setConfigs(prev =>
        prev.map(x => x.client_id === c.client_id ? { ...x, active: !x.active } : x)
      );
    } catch (e) {
      console.error('Toggle failed', e);
    } finally {
      setToggling(null);
    }
  };

  const handleDelete = async (clientId: string) => {
    if (!confirm(`Atenção: exclusão permanente de "${clientId}". Continuar?`)) return;
    try {
      await deleteConfig(clientId);
      setConfigs(prev => prev.filter(x => x.client_id !== clientId));
    } catch (e) {
      console.error('Delete failed', e);
    }
  };

  const openResetCursor = (c: SourceConfig) => {
    setResetInputs(prev => ({ ...prev, [c.client_id]: String(c.last_row_index + 1) }));
    setResetting(c.client_id);
  };

  const cancelReset = (clientId: string) => {
    setResetting(null);
    setResetInputs(prev => { const n = { ...prev }; delete n[clientId]; return n; });
  };

  const confirmReset = async (clientId: string) => {
    const lineNumber = parseInt(resetInputs[clientId] ?? '1', 10);
    if (isNaN(lineNumber) || lineNumber < 1) return;
    const rowIndex = lineNumber - 1;
    try {
      await resetCursor(clientId, rowIndex);
      setConfigs(prev =>
        prev.map(x => x.client_id === clientId ? { ...x, last_row_index: rowIndex } : x)
      );
    } catch (e) {
      console.error('Reset cursor failed', e);
    } finally {
      cancelReset(clientId);
    }
  };

  const filtered = configs.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.client_id.toLowerCase().includes(search.toLowerCase())
  );

  const activeCount = configs.filter(c => c.active).length;

  return (
    <div className="mesh-bg min-h-screen p-10 pb-20 space-y-12 animate-in fade-in duration-500">
      {/* Header Area */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-8">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Database className="text-emerald-500" size={14} />
            <span className="text-[10px] font-black text-emerald-600 uppercase tracking-[0.3em]">Registro Geral</span>
          </div>
          <h2 className="text-5xl font-black text-slate-900 tracking-tight leading-none">
            Pipelines <span className="text-emerald-500 italic">Ativos</span>
          </h2>
          <p className="text-slate-500 font-medium mt-2">Gerenciando {configs.length} pipelines · {activeCount} ativos no cluster.</p>
        </div>

        <div className="flex items-center gap-4">
          <div className="relative group">
            <Search size={18} className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-emerald-500 transition-colors" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Buscar pipelines..."
              className="pl-14 pr-6 py-4 rounded-[1.5rem] border border-slate-200 bg-white/80 focus:bg-white outline-none w-80 transition-all font-bold text-sm focus:ring-4 focus:ring-emerald-50"
            />
          </div>
          <button
            onClick={load}
            className="p-4 bg-white border border-slate-200 rounded-[1.2rem] hover:bg-slate-50 transition-all shadow-sm group"
          >
            <RefreshCw size={20} className={loading ? 'animate-spin text-emerald-500' : 'text-slate-400 group-hover:text-emerald-500'} />
          </button>
        </div>
      </header>

      {/* States */}
      {loading && configs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 gap-4">
           <Loader2 className="animate-spin text-emerald-500 opacity-20" size={64} strokeWidth={1} />
           <p className="text-xs font-black text-slate-400 uppercase tracking-[0.4em]">Carregando...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white/60 backdrop-blur-xl rounded-[3rem] p-24 text-center border border-white/40 shadow-2xl">
          <p className="text-2xl font-black text-slate-900 tracking-tighter mb-2">Nenhum pipeline encontrado.</p>
          <p className="text-slate-500 font-medium tracking-tight">Tente outro identificador ou crie um novo pipeline.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filtered.map(c => (
            <div
              key={c.client_id}
              className={`group bg-white rounded-[2.5rem] border border-slate-100 p-8 flex flex-col hover:shadow-2xl hover:shadow-emerald-950/10 transition-all relative overflow-hidden ${
                !c.active && 'opacity-60 grayscale'
              }`}
            >
              {/* Status Header */}
              <div className="flex justify-between items-center mb-10">
                <div className={`px-4 py-1.5 rounded-2xl text-[9px] font-black tracking-widest flex items-center gap-2 ${
                  c.active ? 'bg-emerald-500/10 text-emerald-600' : 'bg-slate-100 text-slate-400'
                }`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${c.active ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'}`} />
                  {c.active ? 'ATIVO' : 'INATIVO'}
                </div>

                <div className="flex gap-1.5 translate-x-2">
                   <button onClick={() => onViewLogs?.(c.client_id)} className="p-2.5 rounded-xl text-slate-400 hover:text-emerald-500 hover:bg-emerald-50 transition-all">
                     <FileText size={18} />
                   </button>
                   <button onClick={() => onEdit?.(c)} className="p-2.5 rounded-xl text-slate-400 hover:text-amber-500 hover:bg-amber-50 transition-all">
                     <Settings2 size={18} />
                   </button>
                   <button onClick={() => handleDelete(c.client_id)} className="p-2.5 rounded-xl text-slate-300 hover:text-red-500 hover:bg-red-50 transition-all opacity-0 group-hover:opacity-100">
                     <Trash2 size={18} />
                   </button>
                </div>
              </div>

              {/* Title Block */}
              <div className="mb-8">
                <h3 className="text-2xl font-black text-slate-900 tracking-tighter leading-tight group-hover:text-emerald-600 transition-colors uppercase truncate">
                  {c.name}
                </h3>
                <p className="text-[10px] text-slate-500 font-bold font-mono tracking-tight mt-1">{c.client_id}</p>
              </div>

              {/* Insight Grid */}
              <div className="grid grid-cols-2 gap-4 pt-6 border-t border-slate-50 mb-8">
                 <div className="space-y-1">
                    <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                      {c.ingestion_mode === 'webhook' ? <Webhook size={10} /> : <Hash size={10} />}
                      {c.ingestion_mode === 'webhook' ? 'Fonte' : 'Linha Atual'}
                    </p>
                    {c.ingestion_mode === 'webhook' ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-violet-500/10 text-violet-600 text-[9px] font-black uppercase tracking-widest">
                        <Webhook size={9} /> WEBHOOK
                      </span>
                    ) : resetting === c.client_id ? (
                      <div className="flex items-center gap-1.5">
                        <input
                          type="number"
                          min={0}
                          value={resetInputs[c.client_id] ?? ''}
                          onChange={e => setResetInputs(prev => ({ ...prev, [c.client_id]: e.target.value }))}
                          onKeyDown={e => { if (e.key === 'Enter') confirmReset(c.client_id); if (e.key === 'Escape') cancelReset(c.client_id); }}
                          autoFocus
                          className="w-16 text-xs font-black text-slate-800 bg-slate-50 border border-slate-200 rounded-xl px-2 py-1 outline-none focus:border-emerald-400"
                        />
                        <button onClick={() => confirmReset(c.client_id)} className="p-1 text-emerald-500 hover:bg-emerald-50 rounded-lg transition-all">
                          <Check size={14} />
                        </button>
                        <button onClick={() => cancelReset(c.client_id)} className="p-1 text-slate-300 hover:text-red-400 hover:bg-red-50 rounded-lg transition-all">
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-black text-slate-800">{c.last_row_index + 1}</p>
                        <button
                          onClick={() => openResetCursor(c)}
                          title="Reenviar a partir da linha…"
                          className="p-1 text-slate-300 hover:text-amber-500 hover:bg-amber-50 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                        >
                          <RotateCcw size={12} />
                        </button>
                      </div>
                    )}
                 </div>
                 <div className="space-y-1">
                    <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                      <Phone size={10} /> Destinatários
                    </p>
                    <p className="text-sm font-black text-slate-800">{c.destination_phones?.length || 0}</p>
                 </div>
              </div>

              {/* Quick Actions */}
              <div className="mt-auto flex items-center justify-between gap-3 pt-6">
                {c.ingestion_mode === 'webhook' ? (
                  <span className="px-5 py-3 rounded-2xl bg-violet-500/10 text-violet-600 text-[10px] font-black uppercase tracking-widest flex items-center gap-2">
                    <Webhook size={12} /> Webhook
                  </span>
                ) : (
                  <a
                    href={`https://docs.google.com/spreadsheets/d/${c.sheet_id}/edit`}
                    target="_blank" rel="noreferrer"
                    className="px-5 py-3 rounded-2xl bg-slate-900 text-white text-[10px] font-black uppercase tracking-widest hover:bg-black transition-all flex items-center gap-2 shadow-lg"
                  >
                    Planilha <ExternalLink size={12} />
                  </a>
                )}

                <button
                  onClick={() => handleToggle(c)}
                  className={`flex-1 py-3 rounded-2xl border-2 font-black text-[10px] uppercase tracking-widest transition-all ${
                    c.active
                      ? 'border-red-500/10 text-red-500 hover:bg-red-50'
                      : 'border-emerald-500/10 text-emerald-500 hover:bg-emerald-50'
                  }`}
                >
                  {toggling === c.client_id ? 'AGUARDE...' : c.active ? 'Desativar' : 'Ativar'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ClientList;
