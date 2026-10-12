import React from 'react';
import { 
  Home, 
  Sparkles, 
  FolderKanban, 
  Layers, 
  Bot, 
  Share2, 
  Settings, 
  ShieldCheck, 
  Activity,
  X,
  Database,
  RefreshCw,
  Server,
  HardDrive,
  Wand2
} from 'lucide-react';
import { ViewState } from '../../types';
import { useWorkspace } from '../../context/WorkspaceContext';

interface SidebarProps {
  currentView: ViewState;
  onNavigate: (view: ViewState) => void;
  isOpenMobile: boolean;
  onCloseMobile: () => void;
  outputsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onNavigate,
  isOpenMobile,
  onCloseMobile,
  outputsCount
}) => {
  const { backendOnline, checkBackend } = useWorkspace();
  const navItems = [
    { id: 'dashboard' as ViewState, label: 'Dashboard', icon: Home },
    { id: 'new_transformation' as ViewState, label: 'New Transformation', icon: Sparkles, badge: 'Core' },
    { id: 'uckr' as ViewState, label: 'UCKR Knowledge', icon: Database, badge: 'Brain' },
    { id: 'projects' as ViewState, label: 'Projects', icon: FolderKanban },
    { id: 'outputs' as ViewState, label: 'Outputs', icon: Layers, count: outputsCount },
    { id: 'agents' as ViewState, label: 'AI Agents', icon: Bot },
    { id: 'mcp' as ViewState, label: 'MCP Integrations', icon: Share2 },
    { id: 'image_studio' as ViewState, label: 'Image Studio', icon: Wand2, badge: 'AI' },
    { id: 'settings' as ViewState, label: 'Settings', icon: Settings },
  ];

  const handleSelect = (view: ViewState) => {
    onNavigate(view);
    onCloseMobile();
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpenMobile && (
        <div 
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      <aside className={`
        fixed top-0 bottom-0 left-0 z-50 w-72 bg-[#0d121f]/95 lg:bg-[#0d121f] border-r border-slate-800/80
        flex flex-col transition-transform duration-300 ease-in-out backdrop-blur-xl
        ${isOpenMobile ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Brand Header */}
        <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Geometric Connected Transform Logo */}
            <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-600 to-cyan-500 p-0.5 shadow-lg shadow-purple-500/20 flex items-center justify-center">
              <div className="w-full h-full bg-[#0b0f17] rounded-[10px] flex items-center justify-center relative overflow-hidden">
                {/* Abstract geometric transform icon */}
                <svg className="w-5 h-5 text-purple-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" />
                  <path d="M2 17l10 5 10-5" />
                  <path d="M2 12l10 5 10-5" />
                </svg>
                <div className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
              </div>
            </div>

            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-bold tracking-tight text-white text-base">GEN TRANSFORM</span>
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">AI</span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium truncate max-w-[170px]">
                One Source. Multiple Outputs.
              </p>
            </div>
          </div>

          <button 
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Quick Launch Action */}
        <div className="p-3 mx-2 mt-2">
          <button
            onClick={() => handleSelect('new_transformation')}
            className="w-full group relative flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-blue-600 hover:from-purple-500 hover:via-indigo-500 hover:to-blue-500 text-white font-medium text-sm shadow-lg shadow-purple-600/25 hover:shadow-purple-600/40 transition-all duration-200 cursor-pointer"
          >
            <Sparkles className="w-4 h-4 text-purple-200 group-hover:rotate-12 transition-transform" />
            <span>+ New Transformation</span>
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleSelect(item.id)}
                className={`
                  w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer
                  ${isActive 
                    ? 'bg-purple-600/15 text-purple-300 border border-purple-500/30 shadow-sm' 
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                  }
                `}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 transition-colors ${isActive ? 'text-purple-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>

                {item.badge && (
                  <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    {item.badge}
                  </span>
                )}

                {item.count !== undefined && item.count > 0 && (
                  <span className="text-xs font-mono text-slate-400 px-2 py-0.5 rounded-md bg-slate-800">
                    {item.count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Local workspace status */}
        <div className="p-4 border-t border-slate-800/80 bg-[#090d16]/70">
          <div className="flex items-center justify-between mb-2.5">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-700 flex items-center justify-center font-bold text-white text-xs border border-purple-400/30 shadow-inner">
                <Server className={`w-4 h-4 ${backendOnline ? 'text-emerald-300' : 'text-purple-300'}`} />
              </div>
              <div className="leading-tight overflow-hidden">
                <div className="text-sm font-semibold text-slate-200 truncate max-w-[130px]">
                  Workspace Server
                </div>
                <div className="text-[11px] text-slate-400 truncate max-w-[130px]">
                  {backendOnline ? 'FastAPI API + Storage' : 'FastAPI Local Core'}
                </div>
              </div>
            </div>
            <button
              onClick={() => void checkBackend()}
              title="Refresh connection status"
              className="p-1 rounded-md text-slate-400 hover:text-purple-300 hover:bg-slate-800/80 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          {backendOnline === true ? (
            <div className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="font-medium text-[11px]">
                  Backend Online (Port 8000)
                </span>
              </div>
              <Activity className="w-3.5 h-3.5 opacity-70" />
            </div>
          ) : backendOnline === false ? (
            <div className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 text-xs">
              <div className="flex items-center gap-2">
                <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-400 animate-pulse"></span>
                <span className="font-medium text-[11px]">
                  Connecting to Port 8000...
                </span>
              </div>
              <button
                onClick={() => void checkBackend()}
                className="text-[10px] font-semibold underline text-indigo-300 hover:text-indigo-100"
              >
                Retry
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/50 text-slate-400 text-xs">
              <div className="flex items-center gap-2">
                <span className="relative inline-flex rounded-full h-2 w-2 bg-slate-400 animate-pulse"></span>
                <span className="font-medium text-[11px]">
                  Verifying Backend (8000)...
                </span>
              </div>
            </div>
          )}

        </div>
      </aside>
    </>
  );
};
