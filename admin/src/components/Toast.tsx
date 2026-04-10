import React, { useEffect } from 'react';
import { CheckCircle2, XCircle, X } from 'lucide-react';
import { type ToastMessage } from '../hooks/useToast';

interface ToastProps {
  toast: ToastMessage;
  onDismiss: (id: string) => void;
}

const Toast: React.FC<ToastProps> = ({ toast, onDismiss }) => {
  // Auto-dismiss after 5 seconds
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 5000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  const isSuccess = toast.type === 'success';

  return (
    <div
      className={`flex items-start gap-4 p-5 rounded-2xl shadow-2xl border backdrop-blur-md min-w-80 max-w-sm
        animate-in slide-in-from-bottom-4 fade-in duration-300
        ${isSuccess
          ? 'bg-emerald-950/90 border-emerald-500/30 text-white'
          : 'bg-red-950/90 border-red-500/30 text-white'
        }`}
    >
      <div className={`shrink-0 mt-0.5 ${isSuccess ? 'text-emerald-400' : 'text-red-400'}`}>
        {isSuccess
          ? <CheckCircle2 size={20} />
          : <XCircle size={20} />
        }
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-black text-sm leading-tight">{toast.title}</p>
        <p className="text-xs mt-1 opacity-70 leading-relaxed">{toast.message}</p>
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="shrink-0 text-white/40 hover:text-white/80 transition-colors p-0.5"
      >
        <X size={14} />
      </button>
    </div>
  );
};

interface ToastContainerProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onDismiss }) => {
  if (!toasts.length) return null;
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 pointer-events-none">
      {toasts.map(t => (
        <div key={t.id} className="pointer-events-auto">
          <Toast toast={t} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
};

export default Toast;
