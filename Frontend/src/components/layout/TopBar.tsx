import React, { useState } from 'react';
import { 
  Menu, 
  Sparkles, 
  FolderKanban,
  Database,
  Wand2
} from 'lucide-react';
import { ViewState } from '../../types';
import { useWorkspace } from '../../context/WorkspaceContext';
import { ImageStudioModal } from '../results/ImageStudioModal';

interface TopBarProps {
  currentView: ViewState;
  onNavigate: (view: ViewState) => void;
  onOpenMobileSidebar: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  currentView,
  onNavigate,
  onOpenMobileSidebar
}) => {
  const { backendOnline } = useWorkspace();
  const [isImageStudioOpen, setIsImageStudioOpen] = useState(false);

  const getBreadcrumbs = () => {
    switch (currentView) {
      case 'dashboard':
        return { section: 'Overview', page: 'Transformation Dashboard' };
      case 'new_transformation':
        return { section: 'Workspace', page: 'New Transformation Studio' };
      case 'generation_pipeline':
        return { section: 'Transformation', page: 'AI Processing Pipeline' };
      case 'results':
        return { section: 'Deliverables', page: 'Generated Deliverables' };
      case 'projects':
        return { section: 'Repository', page: 'Projects & Artifacts' };
      case 'outputs':
        return { section: 'Repository', page: 'Output Library' };
      case 'agents':
        return { section: 'Intelligence', page: 'AI Multi-Agent System' };
      case 'mcp':
        return { section: 'Integrations', page: 'Model Context Protocol (MCP)' };
      case 'image_studio':
        return { section: 'Studio', page: 'AI Image Studio' };
      case 'settings':
        return { section: 'System', page: 'Workspace Preferences' };
      default:
        return { section: 'Platform', page: 'Workspace' };
    }
  };

  const breadcrumbs = getBreadcrumbs();

  return (
    <header className="sticky top-0 z-30 h-16 bg-[#0b0f17]/80 backdrop-blur-md border-b border-slate-800/80 px-4 lg:px-8 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobileSidebar}
          className="lg:hidden p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
          aria-label="Open menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Clean Breadcrumb */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-400 font-medium hidden sm:inline">{breadcrumbs.section}</span>
          <span className="text-slate-600 hidden sm:inline">/</span>
          <span className="text-slate-100 font-semibold">{breadcrumbs.page}</span>
        </div>
      </div>

      <div className="flex items-center gap-2.5">
        <button
          onClick={() => onNavigate('image_studio')}
          title="AI Image Studio — Stable Diffusion Forge generation"
          className={`hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
            currentView === 'image_studio'
              ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
              : 'text-slate-300 hover:text-white hover:bg-slate-800/80'
          }`}
        >
          <Wand2 className="w-3.5 h-3.5 text-cyan-400" />
          <span>Image Studio</span>
        </button>

        {currentView !== 'projects' && (
          <button
            onClick={() => onNavigate('projects')}
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors cursor-pointer"
          >
            <FolderKanban className="w-3.5 h-3.5 text-slate-400" />
            <span>Projects</span>
          </button>
        )}

        {currentView !== 'new_transformation' && (
          <button
            onClick={() => onNavigate('new_transformation')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-md shadow-purple-600/20 transition-all cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>New Transform</span>
          </button>
        )}

        <div className="h-5 w-px bg-slate-800 mx-0.5" />

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300 text-xs">
          <span className={`w-2 h-2 rounded-full ${backendOnline ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : backendOnline === false ? 'bg-indigo-400 animate-pulse' : 'bg-slate-400 animate-pulse'}`} />
          <span className="hidden sm:inline">{backendOnline ? 'Backend Online (Port 8000)' : 'Connecting...'}</span>
        </div>
      </div>

      {/* AI Image Studio Modal */}
      <ImageStudioModal
        isOpen={isImageStudioOpen}
        onClose={() => setIsImageStudioOpen(false)}
        onShowToast={(title, message, type) => {
          // Toasts are owned by App; surface via a lightweight custom event
          window.dispatchEvent(new CustomEvent('gentransform:toast', { detail: { title, message, type } }));
        }}
      />
    </header>
  );
};
