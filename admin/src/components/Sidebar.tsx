import React from 'react';
import { 
  LayoutDashboard, 
  ListFilter, 
  PlusCircle, 
  Settings, 
  Zap, 
  ShieldCheck,
  ChevronRight,
  LogOut
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab }) => {
  const items = [
    { id: 'dashboard', name: 'Performance', icon: LayoutDashboard },
    { id: 'clients', name: 'Pipelines', icon: Zap },
    { id: 'logs', name: 'Event History', icon: ListFilter },
  ];

  return (
    <div className="w-80 bg-[#0A0D12] text-slate-300 h-screen flex flex-col border-r border-[#151D2A] p-6 shadow-2xl">
      {/* Brand Logo Section */}
      <div className="mb-12 flex items-center gap-4 group cursor-pointer" onClick={() => setActiveTab('dashboard')}>
        <div className="w-12 h-12 bg-emerald-500 rounded-2xl flex items-center justify-center text-white shadow-xl shadow-emerald-900/40 group-hover:scale-105 transition-transform">
           <Zap size={24} className="fill-white" />
        </div>
        <div>
          <h1 className="text-2xl font-black text-white tracking-tighter leading-none">SeedSync</h1>
          <p className="text-[10px] text-emerald-400 font-bold uppercase tracking-[0.2em] mt-1 ml-0.5">High Performance</p>
        </div>
      </div>
      
      {/* Action Button */}
      <div className="mb-10">
        <button 
          onClick={() => setActiveTab('new-client')}
          className="w-full bg-slate-800/50 hover:bg-emerald-600 text-white font-black py-5 px-6 rounded-3xl flex items-center justify-between group transition-all border border-slate-700/50 hover:border-emerald-500 shadow-lg"
        >
          <div className="flex items-center gap-3">
             <PlusCircle size={22} className="text-emerald-400 group-hover:text-white transition-colors" />
             <span className="text-sm">Deploy New Pipeline</span>
          </div>
          <ChevronRight size={16} className="opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all" />
        </button>
      </div>
      
      {/* Navigation Groups */}
      <div className="flex-1 space-y-10">
        <nav className="space-y-2">
          <span className="px-6 text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] block mb-4">Realtime Feed</span>
          {items.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center justify-between px-6 py-4 rounded-2xl transition-all group ${
                activeTab === item.id 
                  ? 'bg-emerald-600/10 text-white font-black border border-emerald-500/20 shadow-xl shadow-emerald-900/10' 
                  : 'text-slate-500 hover:text-slate-200 hover:bg-slate-800/30'
              }`}
            >
              <div className="flex items-center gap-4">
                 <item.icon size={22} className={activeTab === item.id ? 'text-emerald-400' : 'text-slate-600 group-hover:text-slate-300'} />
                 <span className="text-sm">{item.name}</span>
              </div>
              {activeTab === item.id && (
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.8)]" />
              )}
            </button>
          ))}
        </nav>

        <nav className="space-y-2">
          <span className="px-6 text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] block mb-4">Account</span>
          <button className="w-full flex items-center gap-4 px-6 py-4 rounded-2xl text-slate-500 hover:text-slate-200 hover:bg-slate-800/30 transition-all group">
             <Settings size={22} className="text-slate-600 group-hover:text-slate-300" />
             <span className="text-sm font-bold">Preferences</span>
          </button>
          <button className="w-full flex items-center gap-4 px-6 py-4 rounded-2xl text-slate-500 hover:text-slate-200 hover:bg-slate-800/30 transition-all group">
             <ShieldCheck size={22} className="text-slate-600 group-hover:text-slate-300" />
             <span className="text-sm font-bold">API Access</span>
          </button>
        </nav>
      </div>
      
      {/* User / Footer */}
      <div className="mt-auto pt-8 border-t border-[#151D2A]">
        <div className="flex items-center justify-between group cursor-pointer p-2 rounded-2xl hover:bg-slate-900/50 transition-all">
          <div className="flex items-center gap-3">
             <div className="w-12 h-12 rounded-2xl overflow-hidden border-2 border-slate-700 p-0.5 group-hover:border-emerald-500 transition-colors">
               <div className="w-full h-full bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center font-black text-white text-lg">
                 LF
               </div>
             </div>
             <div>
               <p className="text-sm font-black text-white group-hover:text-emerald-400 transition-colors">Lorenzo F.</p>
               <p className="text-[10px] text-slate-500 uppercase font-black">Sysadmin</p>
             </div>
          </div>
          <button className="p-2 text-slate-600 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all">
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
