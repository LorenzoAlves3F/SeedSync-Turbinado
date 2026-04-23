import { useState, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import CreateClient from './components/CreateClient';
import EditConfig from './components/EditConfig';
import ClientList from './components/ClientList';
import LogViewer from './components/LogViewer';
import type { SourceConfig } from './lib/api';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedClientId, setSelectedClientId] = useState<string | undefined>(undefined);
  const [editingConfig, setEditingConfig] = useState<SourceConfig | null>(null);

  const handleViewLogs = useCallback((clientId: string) => {
    setSelectedClientId(clientId);
    setActiveTab('logs');
  }, []);

  const handleEditClient = useCallback((config: SourceConfig) => {
    setEditingConfig(config);
    setActiveTab('edit-client');
  }, []);

  const handleEditSuccess = useCallback(() => {
    setEditingConfig(null);
    setActiveTab('clients');
  }, []);

  return (
    <div className="flex h-screen bg-[#F8FAFC]">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="flex-1 overflow-y-auto">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'new-client' && (
          <CreateClient onSuccess={() => setActiveTab('clients')} />
        )}
        {activeTab === 'edit-client' && editingConfig && (
          <EditConfig
            config={editingConfig}
            onSuccess={handleEditSuccess}
            onCancel={handleEditSuccess}
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
