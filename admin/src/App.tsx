import { useState } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import CreateClient from './components/CreateClient';
import ClientList from './components/ClientList';
import LogViewer from './components/LogViewer';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedClientId, setSelectedClientId] = useState<string | undefined>(undefined);
  const [editingConfig, setEditingConfig] = useState<any>(null);

  const handleViewLogs = (clientId: string) => {
    setSelectedClientId(clientId);
    setActiveTab('logs');
  };

  const handleEditClient = (config: any) => {
    setEditingConfig(config);
    setActiveTab('edit-client');
  };

  return (
    <div className="flex h-screen bg-[#F8FAFC]">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      
      <main className="flex-1 overflow-y-auto">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'new-client' && <CreateClient onSuccess={() => setActiveTab('clients')} />}
        {activeTab === 'edit-client' && (
          <CreateClient 
            initialConfig={editingConfig} 
            onSuccess={() => {
              setEditingConfig(null);
              setActiveTab('clients');
            }} 
          />
        )}
        {activeTab === 'clients' && (
          <ClientList 
            onViewLogs={handleViewLogs} 
            onEdit={handleEditClient} 
          />
        )}
        {activeTab === 'logs' && (
          <LogViewer 
            initialClientId={selectedClientId} 
            onClearFilter={() => setSelectedClientId(undefined)} 
          />
        )}
      </main>
    </div>
  );
}

export default App;
