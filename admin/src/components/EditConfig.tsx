import React, { useState } from 'react';
import { Settings2, Loader2, AlertCircle, X, Plus, Save } from 'lucide-react';
import { updateConfig, type SourceConfig } from '../lib/api';

interface EditConfigProps {
  config: SourceConfig;
  onSuccess?: () => void;
  onCancel?: () => void;
}

const EditConfig: React.FC<EditConfigProps> = ({ config, onSuccess, onCancel }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [name, setName] = useState(config.name);
  const [sheetId, setSheetId] = useState(config.sheet_id);
  const [worksheetName, setWorksheetName] = useState(config.worksheet_name);
  const [nameColumn, setNameColumn] = useState(config.name_column);
  const [phoneColumn, setPhoneColumn] = useState(config.phone_column);
  const [phones, setPhones] = useState<string[]>(
    config.destination_phones?.length ? config.destination_phones : ['']
  );
  const [clickupEnabled, setClickupEnabled] = useState(config.clickup_enabled ?? false);
  const [clickupListId, setClickupListId] = useState(config.clickup_list_id ?? '');

  const extractId = (val: string) => {
    const match = val.match(/\/d\/([a-zA-Z0-9-_]{20,})/);
    return match ? match[1] : val;
  };

  const addPhone = () => setPhones(p => [...p, '']);
  const updatePhone = (i: number, val: string) =>
    setPhones(p => p.map((v, idx) => idx === i ? val : v));
  const removePhone = (i: number) =>
    setPhones(p => p.length > 1 ? p.filter((_, idx) => idx !== i) : p);

  const handleSave = async () => {
    if (!name.trim() || !sheetId.trim() || !worksheetName.trim()) {
      setError('Nome, ID da planilha e aba são obrigatórios.');
      return;
    }
    const cleanPhones = phones.filter(p => p.trim());
    if (!cleanPhones.length) {
      setError('Informe pelo menos um telefone destinatário.');
      return;
    }

    setLoading(true);
    setError('');
    try {
      await updateConfig(config.client_id, {
        name,
        sheet_id: extractId(sheetId),
        worksheet_name: worksheetName,
        name_column: nameColumn,
        phone_column: phoneColumn,
        required_columns: [nameColumn, phoneColumn],
        destination_phones: cleanPhones,
        clickup_enabled: clickupEnabled,
        clickup_list_id: clickupListId || null,
      });
      onSuccess?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao salvar');
    } finally {
      setLoading(false);
    }
  };

  const field = (label: string, children: React.ReactNode) => (
    <div className="space-y-2">
      <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">{label}</label>
      {children}
    </div>
  );

  const input = (value: string, onChange: (v: string) => void, placeholder = '') => (
    <input
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full bg-[#FAFBFC] p-4 rounded-2xl border border-slate-200 outline-none focus:bg-white focus:ring-4 focus:ring-emerald-50 focus:border-emerald-400 transition-all font-bold text-sm text-slate-800 placeholder:text-slate-300"
    />
  );

  return (
    <div className="mesh-bg min-h-screen p-10 pb-24 space-y-10 animate-in fade-in zoom-in-95 duration-400">
      {/* Header */}
      <header className="max-w-3xl mx-auto flex items-end justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Settings2 className="text-amber-500" size={16} />
            <span className="text-[10px] font-black text-amber-600 uppercase tracking-[0.3em]">Edição Rápida</span>
          </div>
          <h2 className="text-5xl font-black text-slate-900 tracking-tight leading-none">
            Editar <span className="text-amber-500 italic">{config.client_id}</span>
          </h2>
          <p className="text-slate-500 font-medium">Modificar parâmetros diretamente — sem assistente necessário.</p>
        </div>
        {onCancel && (
          <button onClick={onCancel} className="px-6 py-4 bg-white border border-slate-200 rounded-2xl text-sm font-black text-slate-400 hover:text-slate-600 transition-all">
            Cancelar
          </button>
        )}
      </header>

      {/* Form Card */}
      <div className="max-w-3xl mx-auto bg-white rounded-[3.5rem] border border-slate-100 shadow-2xl shadow-emerald-950/5 p-14 space-y-10">
        {error && (
          <div className="bg-red-50 p-5 rounded-3xl border border-red-100 flex items-start gap-4 animate-in slide-in-from-top-4">
            <div className="bg-red-500 p-2 rounded-xl text-white"><AlertCircle size={18}/></div>
            <p className="text-sm text-red-800/80 font-medium pt-0.5">{error}</p>
          </div>
        )}

        {/* Identity */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {field('Nome do Pipeline', input(name, setName, 'Ex: GEOTECH MASTER'))}
          {field('ID ou URL da Planilha', input(sheetId, setSheetId, 'ID ou URL completa'))}
        </div>

        {field('Nome da Aba', input(worksheetName, setWorksheetName, 'Ex: PRODUTORES - 2026'))}

        {/* Column Mapping */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {field('Coluna de Nome', input(nameColumn, setNameColumn, 'NOME'))}
          {field('Coluna de Telefone', input(phoneColumn, setPhoneColumn, 'WHATSAPP'))}
        </div>

        {/* Destination Phones */}
        <div className="space-y-3">
          <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Telefones Destinatários</label>
          <div className="space-y-2">
            {phones.map((phone, i) => (
              <div key={i} className="flex gap-2">
                <input
                  value={phone}
                  onChange={e => updatePhone(i, e.target.value)}
                  placeholder="5599999999999"
                  className="flex-1 bg-[#FAFBFC] p-4 rounded-2xl border border-slate-200 outline-none focus:bg-white focus:ring-4 focus:ring-emerald-50 focus:border-emerald-400 font-mono text-xs font-bold text-slate-800 placeholder:text-slate-300 transition-all"
                />
                <button onClick={() => removePhone(i)} className="p-4 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-2xl transition-all">
                  <X size={16} />
                </button>
              </div>
            ))}
            <button onClick={addPhone} className="w-full border-2 border-dashed border-slate-200 p-3.5 rounded-[1.5rem] text-[10px] font-black uppercase tracking-widest text-slate-400 hover:border-emerald-300 hover:text-emerald-500 transition-all flex items-center justify-center gap-2">
              <Plus size={14} /> Adicionar Número
            </button>
          </div>
        </div>

        {/* ClickUp */}
        <div className="bg-slate-900 p-8 rounded-[2.5rem]">
          <div className="flex items-center justify-between gap-6">
            <div>
              <p className="text-white font-black tracking-tight text-sm">Proteção contra Falhas (ClickUp)</p>
              <p className="text-slate-500 text-xs font-medium mt-0.5">Cria uma tarefa quando todas as tentativas falharem.</p>
            </div>
            <button
              onClick={() => setClickupEnabled(!clickupEnabled)}
              className={`w-12 h-7 rounded-full p-1 transition-colors shrink-0 ${clickupEnabled ? 'bg-emerald-500' : 'bg-slate-700'}`}
            >
              <div className={`w-5 h-5 bg-white rounded-full transition-transform ${clickupEnabled ? 'translate-x-5 shadow-lg' : 'translate-x-0'}`} />
            </button>
          </div>
          {clickupEnabled && (
            <input
              value={clickupListId}
              onChange={e => setClickupListId(e.target.value)}
              placeholder="ID da Lista ClickUp"
              className="mt-5 w-full bg-white/5 p-4 rounded-2xl border border-white/10 outline-none font-mono text-xs font-bold text-emerald-400 placeholder:text-slate-700"
            />
          )}
        </div>

        <button
          onClick={handleSave}
          disabled={loading}
          className="btn-primary w-full py-5 text-base flex items-center justify-center gap-3"
        >
          {loading ? <Loader2 className="animate-spin" size={20} /> : <><Save size={18} /> Salvar Alterações</>}
        </button>
      </div>

      <p className="text-center font-black text-slate-300 text-[10px] uppercase tracking-[0.5em]">SeedSync Protocol v1.50 // Kernel Live</p>
    </div>
  );
};

export default EditConfig;
