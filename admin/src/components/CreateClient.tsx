import React, { useState } from 'react';
import { 
  LayoutPanelLeft, 
  ArrowRight, Loader2, RefreshCw, 
  X, MessageSquare, AlertCircle, CheckSquare, 
  Globe, Fingerprint, Zap, ShieldCheck
} from 'lucide-react';
import axios from 'axios';
import api, { type SourceConfig } from '../lib/api';
interface CreateClientProps {
  initialConfig?: SourceConfig | null;
  onSuccess?: () => void;
}

const CreateClient: React.FC<CreateClientProps> = ({ initialConfig, onSuccess }) => {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  // Form State
  const [name, setName] = useState(initialConfig?.name || '');
  const [sheetUrl, setSheetUrl] = useState(initialConfig ? `https://docs.google.com/spreadsheets/d/${initialConfig.sheet_id}/edit` : '');
  const [sheetId, setSheetId] = useState(initialConfig?.sheet_id || '');
  const [worksheets, setWorksheets] = useState<{id: string, title: string}[]>([]);
  
  // Multi-tab support
  const [selectedWorksheets, setSelectedWorksheets] = useState<{title: string, phones: string[]}[]>(
    initialConfig 
      ? [{ title: initialConfig.worksheet_name, phones: initialConfig.destination_phones || [''] }] 
      : []
  );

  const [columns, setColumns] = useState<string[]>([]);
  const [nameColumn, setNameColumn] = useState(initialConfig?.name_column || 'NOME');
  const [phoneColumn, setPhoneColumn] = useState(initialConfig?.phone_column || 'WHATSAPP');
  const [clickupEnabled, setClickupEnabled] = useState(initialConfig?.clickup_enabled ?? false);
  const [clickupListId, setClickupListId] = useState(initialConfig?.clickup_list_id || '');

  const extractId = (url: string) => {
    const match = url.match(/\/d\/([a-zA-Z0-9-_]{20,})/);
    return match ? match[1] : '';
  };

  const handleNextStep1 = async () => {
    const id = extractId(sheetUrl);
    if (!id || !name.trim()) {
      setError('Identity check failed. Please provide a valid Name and Spreadsheet URL.');
      return;
    }
    
    setLoading(true);
    setError('');
    try {
      const worksheets = await api.get<{id: string, title: string}[]>(`/sheets/${id}/worksheets`).then(r => r.data);
      setSheetId(id);
      setWorksheets(worksheets);
      if (worksheets.length > 0 && selectedWorksheets.length === 0 && !initialConfig) {
        setSelectedWorksheets([{ title: worksheets[0].title, phones: [''] }]);
      }
      setStep(2);
    } catch {
      setError('Handshake failed. Ensure the service email has ARCHIVE access.');
    } finally {
      setLoading(false);
    }
  };

  const handleRefetchWorksheets = async () => {
    setLoading(true);
    setError('');
    try {
      const worksheetsData = await api.get<{id: string, title: string}[]>(`/sheets/${sheetId}/worksheets`).then(r => r.data);
      setWorksheets(worksheetsData);
    } catch {
      setError('Relay error. Could not fetch tabs.');
    } finally {
      setLoading(false);
    }
  };

  const toggleWorksheet = (title: string) => {
    if (initialConfig) return;

    setSelectedWorksheets(prev => {
      const exists = prev.find(w => w.title === title);
      if (exists) {
        return prev.filter(w => w.title !== title);
      } else {
        return [...prev, { title, phones: [''] }];
      }
    });
  };

  const handleNextStep2 = async () => {
    if (selectedWorksheets.length === 0) {
      setError('Pipeline requires at least one source tab.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const columnsData = await api.get<string[]>(`/sheets/${sheetId}/worksheets/${selectedWorksheets[0].title}/columns`).then(r => r.data);
      setColumns(columnsData);
      setStep(3);
    } catch {
      setError('Mapping failed. Structure unreadable.');
    } finally {
      setLoading(false);
    }
  };

  const handleNextStep3 = () => {
    setStep(4);
  };

  const addPhone = (wsIndex: number) => {
    const newWs = [...selectedWorksheets];
    newWs[wsIndex].phones.push('');
    setSelectedWorksheets(newWs);
  };

  const updatePhone = (wsIndex: number, pIndex: number, val: string) => {
    const newWs = [...selectedWorksheets];
    newWs[wsIndex].phones[pIndex] = val;
    setSelectedWorksheets(newWs);
  };

  const removePhone = (wsIndex: number, pIndex: number) => {
    const newWs = [...selectedWorksheets];
    if (newWs[wsIndex].phones.length > 1) {
      newWs[wsIndex].phones.splice(pIndex, 1);
      setSelectedWorksheets(newWs);
    }
  };

  const applyPhonesToAll = (sourceIndex: number) => {
    const sourcePhones = [...selectedWorksheets[sourceIndex].phones];
    const newWs = selectedWorksheets.map(ws => ({ ...ws, phones: [...sourcePhones] }));
    setSelectedWorksheets(newWs);
  };

  const handleSave = async () => {
    if (selectedWorksheets.some(ws => ws.phones.filter(p => p.trim()).length === 0)) {
      setError('Target identification required for all pipelines.');
      return;
    }

    setLoading(true);
    setError('');
    try {
      if (initialConfig) {
        const payload = {
          name,
          sheet_id: sheetId,
          worksheet_name: selectedWorksheets[0].title,
          name_column: nameColumn,
          phone_column: phoneColumn,
          required_columns: [nameColumn, phoneColumn],
          destination_phones: selectedWorksheets[0].phones.filter(p => p.trim()),
          clickup_enabled: clickupEnabled,
          clickup_list_id: clickupListId || null
        };
        await api.patch(`/configs/${initialConfig.client_id}`, payload);
      } else {
        const promises = selectedWorksheets.map(sws => {
          const tabName = selectedWorksheets.length > 1 ? `${name} - ${sws.title}` : name;
          return api.post('/configs', {
            name: tabName,
            sheet_id: sheetId,
            worksheet_name: sws.title,
            name_column: nameColumn,
            phone_column: phoneColumn,
            required_columns: [nameColumn, phoneColumn],
            destination_phones: sws.phones.filter(p => p.trim()),
            clickup_enabled: clickupEnabled,
            clickup_list_id: clickupListId || null,
            client_id: '',
            active: true
          });
        });
        await Promise.all(promises);
      }

      if (onSuccess) onSuccess();
      else alert(initialConfig ? 'Deployment Updated!' : 'Cluster Deployed Successfully!');
    } catch (e: unknown) {
      let message = 'Unknown error';
      if (axios.isAxiosError(e)) {
        message = e.response?.data?.detail || e.message;
      } else if (e instanceof Error) {
        message = e.message;
      }
      setError('Deployment failed: ' + message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mesh-bg min-h-screen p-10 pb-24 space-y-12 animate-in fade-in zoom-in-95 duration-500">
      {/* Dynamic Header */}
      <header className="max-w-5xl mx-auto flex flex-col md:flex-row items-start md:items-end justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Zap className="text-emerald-500" size={16} />
            <span className="text-[10px] font-black text-emerald-600 uppercase tracking-[0.3em]">Deployment Wizard</span>
          </div>
          <h2 className="text-5xl font-black text-slate-900 tracking-tight leading-none">
            {initialConfig ? 'Refactor' : 'New'} <span className="text-emerald-500 italic">Pipeline</span>
          </h2>
          <p className="text-slate-500 font-medium">{initialConfig ? 'Modify existing cluster parameters' : 'Architect a new lead ingestion node in 4 stages.'}</p>
        </div>
        
        <div className="flex items-center gap-4">
             {step > 1 && (
                <button 
                  onClick={() => setStep(step - 1)}
                  className="px-6 py-4 bg-white border border-slate-200 rounded-2xl text-sm font-black text-slate-400 hover:text-slate-600 transition-all"
                >
                  Back
                </button>
             )}
        </div>
      </header>

      {/* Progress Matrix */}
      <div className="max-w-5xl mx-auto grid grid-cols-4 gap-6">
        {[
          { label: 'Connect', icon: Globe },
          { label: 'Source', icon: LayoutPanelLeft },
          { label: 'Map', icon: Fingerprint },
          { label: 'Relay', icon: MessageSquare }
        ].map((s, i) => {
          const isActive = step === i + 1;
          const isDone = step > i + 1;
          return (
            <div key={i} className={`p-6 rounded-[2rem] border-2 transition-all duration-500 flex flex-col items-center gap-4 ${
              isActive ? 'bg-white border-emerald-500 shadow-xl shadow-emerald-900/5' : 
              isDone ? 'bg-emerald-50/50 border-emerald-200 opacity-60' : 'bg-white/40 border-slate-100 opacity-40'
            }`}>
               <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isActive ? 'bg-emerald-500 text-white shadow-lg' : 'bg-slate-100 text-slate-400'}`}>
                 {isDone ? <CheckSquare size={20} /> : <s.icon size={20} />}
               </div>
               <span className={`text-[10px] font-black uppercase tracking-[0.2em] ${isActive ? 'text-emerald-600' : 'text-slate-400'}`}>{s.label}</span>
            </div>
          );
        })}
      </div>

      {/* Main Wizard Area */}
      <div className="max-w-5xl mx-auto bg-white rounded-[3.5rem] border border-slate-100 shadow-2xl shadow-emerald-950/5 relative overflow-hidden group">
        <div className="h-1.5 w-full bg-slate-50">
          <div className="h-full bg-emerald-500 transition-all duration-700 ease-spring" style={{ width: `${(step/4)*100}%` }} />
        </div>

        <div className="p-16">
          {error && (
            <div className="bg-red-50 p-6 rounded-3xl mb-12 border border-red-100 flex items-start gap-4 animate-in slide-in-from-top-4">
              <div className="bg-red-500 p-2 rounded-xl text-white shadow-lg"><AlertCircle size={20}/></div>
              <div>
                <p className="text-xs font-black text-red-900 uppercase tracking-widest mb-1">Deployment Error</p>
                <p className="text-sm text-red-800/80 font-medium">{error}</p>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-10 animate-in fade-in duration-500">
               <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
                  <div className="space-y-3">
                    <label className="text-xs font-black text-slate-900 uppercase tracking-widest ml-1">Pipeline Identity</label>
                    <input 
                      value={name} 
                      onChange={e => setName(e.target.value)} 
                      placeholder="Ex: GEOTECH MASTER" 
                      className="w-full bg-[#FAFBFC] p-5 rounded-3xl border border-slate-200 outline-none focus:bg-white focus:ring-4 focus:ring-emerald-50 focus:border-emerald-500 transition-all font-bold text-slate-800 placeholder:text-slate-300"
                    />
                  </div>
                  <div className="space-y-3">
                    <label className="text-xs font-black text-slate-900 uppercase tracking-widest ml-1">Source URL</label>
                    <input 
                      value={sheetUrl} 
                      onChange={e => setSheetUrl(e.target.value)} 
                      placeholder="https://docs.google.com/..." 
                      className="w-full bg-[#FAFBFC] p-5 rounded-3xl border border-slate-200 outline-none focus:bg-white focus:ring-4 focus:ring-emerald-50 focus:border-emerald-500 transition-all font-bold text-slate-800"
                    />
                  </div>
               </div>

               <div className="bg-slate-900 p-10 rounded-[2.5rem] relative overflow-hidden group/box">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 blur-[60px]" />
                  <div className="flex gap-6 relative z-10">
                     <div className="w-14 h-14 bg-white/5 rounded-2xl flex items-center justify-center text-emerald-500 shrink-0 border border-white/5 shadow-inner">
                        <ShieldCheck size={28} />
                     </div>
                     <div>
                        <h4 className="text-lg font-black text-white tracking-tight">Security Handshake</h4>
                        <p className="text-slate-400 text-sm font-medium mt-1">Add this robot ID to the archive's Share panel to grant ingestion access:</p>
                        <div className="mt-4 flex items-center gap-4">
                           <code className="bg-white/5 border border-white/10 p-4 rounded-2xl text-emerald-400 font-mono text-xs select-all cursor-pointer hover:bg-white/10 transition-colors w-full md:w-auto">
                             seedsync@seedsync-491513.iam.gserviceaccount.com
                           </code>
                           <button className="hidden md:flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-widest hover:text-white transition-colors">
                             <Fingerprint size={14} /> Verify
                           </button>
                        </div>
                     </div>
                  </div>
               </div>

               <button 
                onClick={handleNextStep1} 
                disabled={loading} 
                className="btn-primary w-full shadow-emerald-900/10"
              >
                {loading ? <Loader2 className="animate-spin" /> : <>Initiate Protocol <ArrowRight size={22} /></>}
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-10 animate-in fade-in slide-in-from-right-10 duration-500">
               <div className="flex items-center justify-between border-b border-slate-50 pb-8">
                  <div>
                    <h3 className="text-3xl font-black text-slate-900 tracking-tight">Source Nodes</h3>
                    <p className="text-slate-500 font-medium">Select all tabs to be architected into this pipeline cluster.</p>
                  </div>
                  <button 
                    onClick={handleRefetchWorksheets} 
                    className="p-4 rounded-2xl border border-slate-100 bg-white hover:bg-slate-50 text-slate-400 hover:text-emerald-500 transition-all flex items-center gap-2"
                  >
                    <RefreshCw className={loading ? 'animate-spin' : ''} size={18} />
                  </button>
               </div>

               <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {worksheets.map(ws => {
                    const isSelected = selectedWorksheets.some(s => s.title === ws.title);
                    return (
                      <button 
                        key={ws.id} 
                        onClick={() => toggleWorksheet(ws.title)}
                        className={`group p-8 rounded-[2rem] border-2 text-left transition-all relative ${
                          isSelected ? 'bg-emerald-50/20 border-emerald-500' : 'bg-slate-50/30 border-transparent hover:border-slate-200'
                        }`}
                      >
                         <div className={`w-6 h-6 rounded-lg mb-4 flex items-center justify-center transition-all ${isSelected ? 'bg-emerald-500 text-white' : 'bg-slate-200 text-transparent group-hover:bg-slate-300'}`}>
                           <CheckSquare size={14} />
                         </div>
                         <p className={`font-black text-lg tracking-tight leading-none mb-1 ${isSelected ? 'text-emerald-700' : 'text-slate-800'}`}>{ws.title}</p>
                         <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{ws.id}</p>
                      </button>
                    );
                  })}
               </div>

               <div className="flex gap-4">
                  <button 
                    onClick={handleNextStep2} 
                    className="btn-primary flex-1 shadow-emerald-900/10"
                  >
                    Initialize Mapping ({selectedWorksheets.length} nodes)
                  </button>
               </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-10 animate-in fade-in slide-in-from-right-10 duration-500">
               <div className="border-b border-slate-50 pb-8">
                 <h3 className="text-3xl font-black text-slate-900 tracking-tight">Data Mapping</h3>
                 <p className="text-slate-500 font-medium">Define metadata extraction rules applied across selected nodes.</p>
               </div>

               <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
                  <div className="space-y-4">
                    <label className="text-[10px] font-black text-slate-900 uppercase tracking-[0.2em] ml-1">Entity Name Pointer</label>
                    <div className="relative">
                       <select 
                        value={nameColumn} 
                        onChange={e => setNameColumn(e.target.value)} 
                        className="w-full bg-[#FAFBFC] p-5 rounded-3xl border border-slate-200 outline-none appearance-none font-bold text-slate-800 focus:bg-white transition-all shadow-sm"
                      >
                         {columns.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                      <ChevronDown size={14} className="absolute right-6 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                    </div>
                  </div>
                  <div className="space-y-4">
                    <label className="text-[10px] font-black text-slate-900 uppercase tracking-[0.2em] ml-1">Identity/Phone Pointer</label>
                    <div className="relative">
                       <select 
                        value={phoneColumn} 
                        onChange={e => setPhoneColumn(e.target.value)} 
                        className="w-full bg-[#FAFBFC] p-5 rounded-3xl border border-slate-200 outline-none appearance-none font-bold text-slate-800 focus:bg-white transition-all shadow-sm"
                      >
                         {columns.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                      <ChevronDown size={14} className="absolute right-6 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                    </div>
                  </div>
               </div>

               <button 
                onClick={handleNextStep3} 
                className="btn-primary w-full"
              >
                Assemble Delivery Mesh
              </button>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-10 animate-in fade-in slide-in-from-right-10 duration-500">
               <div className="border-b border-slate-50 pb-8">
                 <h3 className="text-3xl font-black text-slate-900 tracking-tight">Delivery Hub</h3>
                 <p className="text-slate-500 font-medium">Relay configuration for outbound lead notifications.</p>
               </div>

               <div className="space-y-6 max-h-[500px] overflow-y-auto pr-4 custom-scrollbar">
                  {selectedWorksheets.map((ws, wsIdx) => (
                    <div key={wsIdx} className="bg-[#FAFBFC] p-10 rounded-[3rem] border border-slate-100 relative group/row overflow-hidden">
                       <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 blur-[40px] opacity-0 group-hover/row:opacity-100 transition-opacity" />
                       
                       <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8 relative z-10">
                          <div>
                            <p className="text-[10px] font-black text-emerald-600 uppercase tracking-[0.3em] mb-1">Target Relay</p>
                            <h4 className="text-xl font-black text-slate-900 tracking-tight">{ws.title}</h4>
                          </div>
                          {wsIdx === 0 && selectedWorksheets.length > 1 && (
                            <button onClick={() => applyPhonesToAll(0)} className="px-4 py-2 bg-emerald-500 text-white text-[10px] font-black uppercase tracking-widest rounded-xl hover:bg-emerald-600 transition-all shadow-lg shadow-emerald-900/10">
                              Sync to All Nodes
                            </button>
                          )}
                       </div>

                       <div className="grid gap-3 relative z-10">
                          {ws.phones.map((phone, idx) => (
                            <div key={idx} className="flex gap-3">
                               <input 
                                value={phone} 
                                onChange={e => updatePhone(wsIdx, idx, e.target.value)} 
                                placeholder="5599999999999" 
                                className="flex-1 bg-white p-4 rounded-2xl border border-slate-200 outline-none font-mono text-xs font-bold text-slate-800"
                               />
                               <button onClick={() => removePhone(wsIdx, idx)} className="p-4 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-2xl transition-all">
                                 <X size={18} />
                               </button>
                            </div>
                          ))}
                          <button onClick={() => addPhone(wsIdx)} className="w-full border-2 border-dashed border-slate-200 p-4 rounded-[1.5rem] text-[10px] font-black uppercase tracking-widest text-slate-400 hover:border-emerald-300 hover:text-emerald-500 transition-all">
                            Add Relay Node
                          </button>
                       </div>
                    </div>
                  ))}
               </div>

               <div className="bg-slate-900 p-10 rounded-[3rem] shadow-2xl">
                   <div className="flex items-center justify-between gap-6 mb-4">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-white/5 rounded-2xl flex items-center justify-center text-emerald-500 border border-white/5">
                           <AlertCircle size={24} />
                        </div>
                        <div>
                           <h4 className="text-white font-black tracking-tight">Active Failure Safeguard</h4>
                           <p className="text-slate-500 text-xs font-medium">Automatic ticket creation if delivery relay fails.</p>
                        </div>
                      </div>
                      <button 
                        onClick={() => setClickupEnabled(!clickupEnabled)}
                        className={`w-14 h-8 rounded-full p-1 transition-colors ${clickupEnabled ? 'bg-emerald-500' : 'bg-slate-700'}`}
                      >
                         <div className={`w-6 h-6 bg-white rounded-full transition-transform ${clickupEnabled ? 'translate-x-6 shadow-lg shadow-emerald-900' : 'translate-x-0'}`} />
                      </button>
                   </div>
                   {clickupEnabled && (
                     <input 
                      value={clickupListId} 
                      onChange={e => setClickupListId(e.target.value)} 
                      placeholder="ClickUp Object ID" 
                      className="w-full mt-6 bg-white/5 p-5 rounded-2xl border border-white/10 outline-none font-mono text-xs font-bold text-emerald-400 placeholder:text-slate-700"
                     />
                   )}
               </div>

               <button onClick={handleSave} className="btn-primary w-full py-6 text-xl">
                 Finalize & Deploy Protocol
               </button>
            </div>
          )}
        </div>
      </div>
      
      <p className="text-center font-black text-slate-300 text-[10px] uppercase tracking-[0.5em]">SeedSync Protocol v1.50 // Kernel Live</p>
    </div>
  );
};

const ChevronDown = ({ size, className }: { size: number, className: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="m6 9 6 6 6-6"/>
  </svg>
);

export default CreateClient;
