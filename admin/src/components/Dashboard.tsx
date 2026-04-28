import React, { useEffect, useState } from 'react';
import {
  Activity, Users, Loader2,
  RefreshCw, Zap, ArrowUpRight, ShieldCheck,
  Clock, TrendingUp, AlertCircle, Webhook
} from 'lucide-react';
import { fetchConfigs, fetchLogs, syncReset, type SourceConfig, type IngestionLog } from '../lib/api';
import { ToastContainer } from './Toast';
import { useToast } from '../hooks/useToast';

const Dashboard: React.FC = () => {
  const [configs, setConfigs] = useState<SourceConfig[]>([]);
  const [recentLogs, setRecentLogs] = useState<IngestionLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const { toasts, addToast, dismissToast } = useToast();

  const load = async () => {
    setLoading(true);
    try {
      const [cfgs, logs] = await Promise.all([
        fetchConfigs(),
        fetchLogs({ limit: 20 }),
      ]);
      setConfigs(cfgs);
      setRecentLogs(logs);
    } catch (e: unknown) {
      console.error('Falha ao carregar dashboard', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncReset = async () => {
    if (syncing) return;
    setSyncing(true);
    try {
      const res = await syncReset();
      addToast(
        'success',
        'Sincronização Iniciada',
        `O sistema resetou ${res.cluster_size} pipelines com buffer de ${res.buffer_size} linhas.`
      );
      await load();
    } catch (e: unknown) {
      const error = e instanceof Error ? e : new Error('Erro desconhecido');
      addToast('error', 'Falha na Sincronização', error.message);
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const totalClients = configs.length;
  const activeClients = configs.filter(c => c.active).length;
  const healthScore = totalClients > 0 ? Math.round((activeClients / totalClients) * 100) : 0;
  const errorsCount = recentLogs.filter(l => l.status === 'error').length;

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('pt-BR', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  if (loading && configs.length === 0) {
    return (
      <div className="flex items-center justify-center h-full bg-[#FAFBFC]">
        <div className="flex flex-col items-center gap-4">
           <Loader2 className="animate-spin text-emerald-500" size={48} strokeWidth={1} />
           <p className="text-xs font-black text-slate-400 uppercase tracking-[0.3em]">Carregando...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mesh-bg min-h-screen p-10 space-y-12 animate-in fade-in duration-700 pb-24">
      {/* Cabeçalho */}
      <header className="flex flex-col md:flex-row items-start md:items-end justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <ShieldCheck className="text-emerald-500" size={16} />
            <span className="text-[10px] font-black text-emerald-600 uppercase tracking-[0.3em]">Sistema Operacional</span>
          </div>
          <h2 className="text-5xl font-black text-slate-900 tracking-tight leading-none mb-1">
            Visão <span className="text-emerald-500 italic">Geral</span>
          </h2>
          <p className="text-slate-500 font-medium">Monitoramento em tempo real de todos os pipelines.</p>
        </div>
        <div className="flex gap-4">
          <button
            onClick={handleSyncReset}
            disabled={syncing}
            className={`flex items-center gap-3 px-8 py-4 ${
              syncing ? 'bg-slate-100 text-slate-400' : 'bg-[#10B981] hover:bg-emerald-600 text-white shadow-xl shadow-emerald-200'
            } rounded-2xl text-sm font-black transition-all group overflow-hidden relative`}
          >
            {syncing ? (
              <Loader2 className="animate-spin" size={18} />
            ) : (
              <RefreshCw size={18} className="group-hover:rotate-180 transition-transform duration-700" />
            )}
            <span className="relative z-10">{syncing ? 'Sincronizando...' : 'Sincronizar'}</span>
            {!syncing && <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />}
          </button>

          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-3 px-6 py-4 bg-white border border-slate-200 rounded-2xl text-sm font-black text-slate-700 hover:bg-slate-50 hover:shadow-lg transition-all"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
            Atualizar
          </button>
        </div>
      </header>

      {/* Cards de Estatísticas */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <StatCard
          icon={<Users className="text-slate-900" size={24} />}
          label="Pipelines"
          value={totalClients}
          subtext={`${activeClients} ativos`}
          color="bg-white"
        />
        <StatCard
          icon={<TrendingUp className="text-emerald-600" size={24} />}
          label="Saúde"
          value={`${healthScore}%`}
          subtext="Uptime operacional"
          color="bg-emerald-50/50"
        />
        <StatCard
          icon={<Zap className="text-amber-500" size={24} />}
          label="Throughput"
          value={recentLogs.length}
          subtext="Atividade recente"
          color="bg-white"
        />
        <StatCard
          icon={<AlertCircle className={errorsCount > 0 ? "text-red-500" : "text-slate-300"} size={24} />}
          label="Incidentes"
          value={errorsCount}
          subtext="Falhas críticas"
          color="bg-white"
          caution={errorsCount > 0}
        />
      </div>

      {/* Conteúdo Principal */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">

        {/* Terminal ao Vivo */}
        <section className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between px-2">
             <h3 className="text-sm font-black text-slate-900 uppercase tracking-widest flex items-center gap-3">
               <Activity className="text-emerald-500" size={16} />
               Stream ao Vivo <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping ml-1" />
             </h3>
             <span className="text-[10px] font-bold text-slate-400">Atualiza a cada 30s</span>
          </div>

          <div className="bg-[#0A0D12] rounded-[2.5rem] border border-[#151D2A] p-8 shadow-2xl shadow-emerald-950/10 relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 blur-[100px] -translate-y-1/2 translate-x-1/2" />

            <div className="relative font-mono text-[13px] leading-relaxed space-y-2 overflow-y-auto max-h-[500px] pr-4 custom-scrollbar">
              {recentLogs.length === 0 ? (
                <div className="py-20 text-center space-y-4">
                   <div className="w-12 h-12 bg-slate-900 rounded-2xl mx-auto flex items-center justify-center border border-slate-800">
                     <Loader2 className="animate-spin text-slate-700" size={20} />
                   </div>
                   <p className="text-slate-600 font-bold uppercase tracking-widest text-[10px]">Aguardando novos leads...</p>
                </div>
              ) : (
                recentLogs.map((log, idx) => (
                  <div key={log.id} className="flex gap-6 py-2 group/row border-b border-white/5 last:border-0 hover:bg-white/5 rounded-lg px-2 transition-colors">
                    <span className="text-slate-600 shrink-0 select-none">{(recentLogs.length - idx).toString().padStart(2, '0')}</span>
                    <span className="text-emerald-500/60 shrink-0 font-bold">{formatTime(log.processed_at)}</span>
                    <div className="flex-1 flex gap-3 truncate items-baseline overflow-hidden">
                       <span className={`px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-tighter shrink-0 ${
                         log.status === 'inserted' ? 'bg-emerald-500/10 text-emerald-400' :
                         log.status === 'error' ? 'bg-red-500/20 text-red-400' :
                         'bg-slate-500/10 text-slate-400'
                       }`}>
                         {log.status}
                       </span>
                       <span className="text-slate-300 font-bold truncate shrink-0">{log.client_id}</span>
                       <span className="text-slate-600 hidden md:inline truncate">{log.row_fingerprint}</span>
                    </div>
                    {log.status === 'inserted' && (
                      <ArrowUpRight size={14} className="text-emerald-500/40 mt-1" />
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        {/* Lista de Pipelines */}
        <section className="space-y-6">
          <h3 className="text-sm font-black text-slate-900 uppercase tracking-widest flex items-center gap-3 px-2">
            <Clock className="text-slate-400" size={16} />
            Pipelines Ativos
          </h3>
          <div className="grid gap-3">
            {configs.map(c => (
              <div
                key={c.client_id}
                className="group bg-white p-5 rounded-3xl border border-slate-100 hover:border-emerald-200 hover:shadow-xl hover:shadow-emerald-900/5 transition-all flex items-center justify-between"
              >
                <div className="flex items-center gap-4 overflow-hidden">
                  <div className={`w-3 h-3 rounded-full shrink-0 ${c.active ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-slate-200'}`} />
                  <div className="truncate">
                    <p className="text-sm font-black text-slate-900 truncate leading-none mb-1">{c.name}</p>
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-tight">{c.client_id}</p>
                  </div>
                </div>
                <div className="text-right shrink-0 ml-4">
                  {c.ingestion_mode === 'webhook' ? (
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-violet-500/10 text-violet-600 text-[9px] font-black uppercase tracking-widest">
                      <Webhook size={8} /> WEBHOOK
                    </span>
                  ) : (
                    <>
                      <p className="text-xs font-black text-slate-900">#{c.last_row_index + 1}</p>
                      <p className="text-[9px] text-slate-400 uppercase font-black tracking-widest">Linha</p>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
          <button className="w-full py-4 text-xs font-black text-slate-400 uppercase tracking-[0.2em] border-2 border-dashed border-slate-200 rounded-3xl hover:border-emerald-300 hover:text-emerald-500 transition-all">
            Ver Todos os Pipelines
          </button>
        </section>
      </div>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};

const StatCard: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string | number;
  subtext: string;
  color: string;
  caution?: boolean;
}> = ({ icon, label, value, subtext, color, caution }) => (
  <div className={`${color} ${caution ? 'ring-2 ring-red-500/20' : ''} rounded-[2.5rem] p-8 border border-slate-100 shadow-xl shadow-slate-200/40 relative overflow-hidden group hover:-translate-y-1 transition-all`}>
    <div className="flex flex-col justify-between h-full relative z-10">
      <div className="mb-8 p-4 bg-white rounded-2xl w-fit shadow-md group-hover:scale-110 transition-transform">
        {icon}
      </div>
      <div>
        <p className="text-4xl font-black text-slate-900 tracking-tighter leading-none mb-2">{value}</p>
        <p className="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
           {label}
           <div className="w-1 h-1 rounded-full bg-slate-300" />
           <span className="font-bold text-slate-500 lowercase !tracking-normal">{subtext}</span>
        </p>
      </div>
    </div>
    <div className="absolute -bottom-10 -right-10 opacity-[0.03] rotate-12 group-hover:rotate-6 transition-transform">
      {icon}
    </div>
  </div>
);

export default Dashboard;
