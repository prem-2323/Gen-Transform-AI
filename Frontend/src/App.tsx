import React, { useState } from 'react';
import {
  ViewState,
  SourceFile,
  TransformationConfig,
  OutputType,
  DeliverablesState,
  ProjectRecord,
  AIAnalysis,
  TransformationProject,
  UckrKnowledgeBase
} from './types';
import { Sidebar } from './components/layout/Sidebar';
import { TopBar } from './components/layout/TopBar';
import { ToastContainer, ToastMessage } from './components/common/Toast';
import { DashboardView } from './components/dashboard/DashboardView';
import { NewTransformationView } from './components/transformation/NewTransformationView';
import { GenerationPipelineView } from './components/transformation/GenerationPipelineView';
import { ResultsWorkspaceView } from './components/results/ResultsWorkspaceView';
import { ProjectsView } from './components/pages/ProjectsView';
import { OutputsView } from './components/pages/OutputsView';
import { AgentsView } from './components/pages/AgentsView';
import { McpView } from './components/pages/McpView';
import { ImageStudioView } from './components/pages/ImageStudioView';
import { SettingsView } from './components/pages/SettingsView';
import { UckrPanel } from './components/uckr/UckrPanel';
import { WorkspaceProvider, useWorkspace } from './context/WorkspaceContext';
import { generateDeliverables } from './services/aiService';

const DEFAULT_CONFIG: TransformationConfig = {
  targetAudience: 'General Public',
  tone: 'Professional',
  language: 'English',
  levelOfDetail: 'Balanced',
  objective: 'Inform',
  contentStyle: 'Professional',
};

export interface PipelineResults {
  deliverables: DeliverablesState;
  analysis: AIAnalysis | null;
  uckr: UckrKnowledgeBase | null;
}

function AppContent() {
  const {
    projects,
    isSyncing,
    saveProject,
    deleteProject
  } = useWorkspace();

  const [currentView, setCurrentView] = useState<ViewState>('dashboard');
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // Active Project & Transformation State — empty by default, no demo content
  const [currentProjectId, setCurrentProjectId] = useState<string>('');
  const [source, setSource] = useState<SourceFile | null>(null);
  const [config, setConfig] = useState<TransformationConfig>(DEFAULT_CONFIG);
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [uckr, setUckr] = useState<UckrKnowledgeBase | null>(null);
  const [selectedOutputs, setSelectedOutputs] = useState<OutputType[]>([]);
  const [deliverables, setDeliverables] = useState<DeliverablesState>({});
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [savedProjectIds, setSavedProjectIds] = useState<string[]>([]);

  const combinedProjects = projects;

  const addToast = (title: string, message: string, type: 'success' | 'info' | 'error' = 'info') => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, title, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Bridge: modals rendered outside AppContent (e.g. TopBar Image Studio)
  // publish toasts through the 'gentransform:toast' custom event.
  React.useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail as { title: string; message: string; type?: 'success' | 'info' | 'error' } | undefined;
      if (detail?.title && detail?.message) {
        addToast(detail.title, detail.message, detail.type || 'info');
      }
    };
    window.addEventListener('gentransform:toast', handler);
    return () => window.removeEventListener('gentransform:toast', handler);
  }, []);

  // Quick Start from Dashboard Drop/Paste — real user content only
  const handleQuickStartUpload = (partial: Partial<SourceFile>) => {
    setCurrentProjectId(`proj-${Date.now()}`);
    setSource({
      id: `src-${Date.now()}`,
      name: partial.name || 'Untitled_Source.txt',
      type: partial.type || 'TEXT',
      size: partial.size || '0 KB',
      status: 'ready',
      uploadedAt: new Date().toISOString(),
      extractedText: partial.extractedText || ''
    });
    // Reset derived state — real analysis runs in the studio
    setAnalysis(null);
    setUckr(null);
    setDeliverables({});
    addToast('Source Ingested', `"${partial.name || 'Untitled_Source.txt'}" ready in transformation studio.`, 'success');
  };

  // Output selection toggling
  const handleToggleOutput = (output: OutputType) => {
    setSelectedOutputs((prev) => {
      if (prev.includes(output)) {
        return prev.filter((o) => o !== output);
      } else {
        return [...prev, output];
      }
    });
  };

  const handleSelectAllOutputs = () => {
    setSelectedOutputs([
      'linkedin',
      'twitter',
      'advisory',
      'executive_summary',
      'infographic',
      'presentation',
      'video'
    ]);
    addToast('All Deliverables Selected', 'All 7 output types enabled.', 'info');
  };

  const handleClearOutputs = () => {
    setSelectedOutputs([]);
  };

  // Start Pipeline — requires a real source with text
  const handleStartGeneration = (sourceOverride?: SourceFile | null) => {
    const activeSource = sourceOverride || source;
    if (!activeSource || !activeSource.extractedText?.trim()) {
      addToast('No Source Content', 'Please upload or paste source text before generating.', 'error');
      return;
    }
    if (sourceOverride) {
      setSource(sourceOverride);
    }
    if (selectedOutputs.length === 0) {
      addToast('No Outputs Selected', 'Please select at least one deliverable to generate.', 'error');
      return;
    }
    setCurrentView('generation_pipeline');
  };

  const handlePipelineError = (message: string) => {
    addToast('Generation Failed', message, 'error');
    setCurrentView('new_transformation');
  };

  // Pipeline Completion — real AI results
  const handlePipelineComplete = async (results: PipelineResults) => {
    setDeliverables(results.deliverables);
    if (results.analysis) setAnalysis(results.analysis);
    if (results.uckr) setUckr(results.uckr);
    setCurrentView('results');
    addToast('Deliverables Ready', `Synthesized ${selectedOutputs.length} deliverables from ${source?.name || 'source'}.`, 'success');

    if (source) {
      const newProjectId = currentProjectId || `proj-${Date.now()}`;
      const projectRecord: TransformationProject = {
        id: newProjectId,
        userId: 'local-workspace',
        title: source.name.replace(/\.[^/.]+$/, '') || 'Untitled Transformation',
        description: `${config.targetAudience} · ${config.tone} · ${selectedOutputs.length} deliverables`,
        source,
        config,
        selectedOutputs,
        analysis: results.analysis || analysis as AIAnalysis,
        uckr: results.uckr || undefined,
        deliverables: results.deliverables,
        status: 'Completed',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
      if (projectRecord.analysis) {
        try {
          const saved = await saveProject(projectRecord);
          if (saved) {
            setSavedProjectIds((prev) => [...new Set([...prev, newProjectId])]);
            addToast('Project Saved', 'Transformation saved to the local workspace.', 'success');
          } else {
            console.warn('Automatic project save failed.');
          }
        } catch (err) {
          console.error('Auto cloud save failed:', err);
        }
      }
    }
  };

  // Save the current project to the local workspace.
  const handleSaveToWorkspace = async () => {
    if (!source || !analysis) {
      addToast('Nothing To Save', 'Upload a source and run generation before saving.', 'error');
      return;
    }

    const projectId = currentProjectId || `proj-${Date.now()}`;
    const projectRecord: TransformationProject = {
      id: projectId,
      userId: 'local-workspace',
      title: source.name.replace(/\.[^/.]+$/, '') || 'Untitled Transformation',
      description: `${config.targetAudience} · ${config.tone} · ${selectedOutputs.length} deliverables`,
      source,
      config,
      selectedOutputs,
      analysis,
      uckr: uckr || undefined,
      deliverables,
      status: 'Completed',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    try {
      const success = await saveProject(projectRecord);
      if (success) {
        setSavedProjectIds((prev) => [...new Set([...prev, projectId])]);
        addToast('Project Saved', 'Project and deliverables saved to the local workspace.', 'success');
      } else {
        addToast('Save Failed', 'Could not save the project. Check that the backend is running.', 'error');
      }
    } catch (err) {
      addToast('Save Failed', 'Could not save the project. Check the backend connection.', 'error');
    }
  };

  // Generate a single missing deliverable via real AI
  const handleAddDeliverable = async (type: OutputType) => {
    if (!source) {
      addToast('No Source', 'Upload source content before generating deliverables.', 'error');
      return;
    }
    if (!selectedOutputs.includes(type)) {
      setSelectedOutputs((prev) => [...prev, type]);
    }
    try {
      const fresh = await generateDeliverables(source, config, [type], analysis, uckr);
      setDeliverables((prev) => ({ ...prev, ...fresh }));
      addToast('Deliverable Synthesized', `Generated ${type.replace('_', ' ')} from your source.`, 'success');
    } catch (err) {
      addToast('Generation Failed', err instanceof Error ? err.message : 'Could not generate deliverable.', 'error');
    }
  };

  // Publish to platform — queued until backend publishing is connected
  const handlePublishMcp = (platformName: string) => {
    addToast(
      `Queued for ${platformName}`,
      `Publish request noted. Dispatch waits for backend integration.`,
      'info'
    );
  };

  // Create a project in the local workspace.
  const handleCreateProject = async (name: string, description?: string) => {
    try {
      const saved = await saveProject({
        id: `proj-${Date.now()}`,
        userId: 'local-workspace',
        title: name,
        description: description || 'Enterprise transformation workspace.',
        source: {
          id: `src-${Date.now()}`,
          name: 'Untitled_Source.txt',
          type: 'TEXT',
          size: '0 KB',
          status: 'ready',
          uploadedAt: new Date().toISOString(),
          extractedText: ''
        },
        config: DEFAULT_CONFIG,
        selectedOutputs: ['linkedin', 'executive_summary', 'advisory'],
        analysis: {
          detectedTopic: name,
          confidenceScore: 0.95,
          keyEntities: [],
          importantFacts: [],
          audienceSignals: [],
          communicationObjective: 'Inform',
          sentiment: 'Neutral',
          readabilityScore: 'Grade 12'
        },
        status: 'Draft',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      });
      addToast('Project Created', `Project "${name}" saved to the local workspace.`, saved ? 'success' : 'error');
    } catch (err: any) {
      addToast('Create Project Failed', `Could not save project "${name}".`, 'error');
    }
  };

  // Project select — FastAPI Workspace Hydration
  const handleSelectProject = async (project: ProjectRecord) => {
    const pid = project.id || (project as any).projectId || '';
    setCurrentProjectId(pid);
    setConfig(project.config || DEFAULT_CONFIG);
    setSelectedOutputs(project.selectedOutputs || ['linkedin', 'executive_summary', 'advisory']);

    // Direct assignment from record
    if (project.source) setSource(project.source);
    if (project.analysis) setAnalysis(project.analysis);
    if (project.uckr) setUckr(project.uckr);
    if (project.deliverables) setDeliverables(project.deliverables);

    setCurrentView('results');
    addToast('Project Loaded', `Opened workspace for "${project.title || project.name || 'Project'}".`, 'info');
  };

  // Delete a project from local workspace storage.
  const handleDeleteProject = async (projectId: string) => {
    const deleted = await deleteProject(projectId);
    addToast(
      deleted ? 'Project Deleted' : 'Delete Failed',
      deleted ? 'Project removed from the local workspace.' : 'Could not delete project.',
      deleted ? 'info' : 'error'
    );
  };

  const isCurrentSaved = savedProjectIds.includes(currentProjectId) || projects.some((p) => p.id === currentProjectId);

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col font-sans antialiased selection:bg-purple-600 selection:text-white">
      {/* Toast Notification Container */}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />

      {/* Persistent Left Sidebar */}
      <Sidebar
        currentView={currentView}
        onNavigate={setCurrentView}
        isOpenMobile={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
        outputsCount={selectedOutputs.length}
      />

      {/* Main Workspace Frame */}
      <div className="lg:pl-72 flex-1 flex flex-col min-w-0">
        {/* Sticky Clean TopBar */}
        <TopBar
          currentView={currentView}
          onNavigate={setCurrentView}
          onOpenMobileSidebar={() => setIsMobileSidebarOpen(true)}
        />

        {/* Dynamic Page Router */}
        <main className="flex-1 px-4 sm:px-6 lg:px-10 py-6 max-w-7xl w-full mx-auto">
          {currentView === 'dashboard' && (
            <DashboardView
              onNavigate={setCurrentView}
              onQuickStartUpload={handleQuickStartUpload}
            />
          )}

          {currentView === 'new_transformation' && (
            <NewTransformationView
              source={source}
              config={config}
              selectedOutputs={selectedOutputs}
              analysis={analysis}
              uckr={uckr}
              onUpdateSource={setSource}
              onUpdateConfig={setConfig}
              onUpdateAnalysis={setAnalysis}
              onUpdateUckr={setUckr}
              onToggleOutput={handleToggleOutput}
              onSelectAllOutputs={handleSelectAllOutputs}
              onClearOutputs={handleClearOutputs}
              onStartGeneration={handleStartGeneration}
              onShowToast={addToast}
            />
          )}

          {currentView === 'generation_pipeline' && (
            <GenerationPipelineView
              selectedOutputs={selectedOutputs}
              sourceName={source?.name || 'Untitled source'}
              source={source}
              config={config}
              analysis={analysis}
              uckr={uckr}
              onComplete={handlePipelineComplete}
              onError={handlePipelineError}
              onBack={() => setCurrentView('new_transformation')}
            />
          )}

          {currentView === 'results' && (
            <ResultsWorkspaceView
              projectId={currentProjectId}
              source={source}
              config={config}
              selectedOutputs={selectedOutputs}
              deliverables={deliverables}
              uckr={uckr}
              onUpdateDeliverables={setDeliverables}
              onNavigateNew={() => setCurrentView('new_transformation')}
              onAddDeliverable={handleAddDeliverable}
              onPublishMcp={handlePublishMcp}
              onShowToast={addToast}
              onSaveToWorkspace={handleSaveToWorkspace}
              isSavedToWorkspace={isCurrentSaved}
              isSavingToWorkspace={isSyncing}
            />
          )}

          {currentView === 'projects' && (
            <ProjectsView
              projects={combinedProjects}
              onSelectProject={handleSelectProject}
              onNewTransformation={() => setCurrentView('new_transformation')}
              onDeleteProject={handleDeleteProject}
              onCreateProject={handleCreateProject}
            />
          )}

          {currentView === 'outputs' && (
            <OutputsView
              deliverables={deliverables}
              onOpenResults={(filter) => {
                if (filter && !selectedOutputs.includes(filter)) {
                  setSelectedOutputs((prev) => [...prev, filter]);
                }
                setCurrentView('results');
              }}
              onShowToast={addToast}
            />
          )}

          {currentView === 'uckr' && (
            <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
              {uckr ? (
                <UckrPanel
                  uckr={uckr}
                  sourceDocTitle={source?.name || 'No source loaded'}
                />
              ) : (
                <div className="p-12 rounded-2xl border border-dashed border-slate-800 text-center space-y-3 bg-slate-900/30">
                  <h2 className="text-lg font-bold text-white">No knowledge base yet</h2>
                  <p className="text-sm text-slate-400 max-w-md mx-auto">
                    Upload a source and run a transformation to build the Unified Content Knowledge Representation.
                  </p>
                  <button
                    onClick={() => setCurrentView('new_transformation')}
                    className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold cursor-pointer"
                  >
                    Start a Transformation
                  </button>
                </div>
              )}
            </div>
          )}

          {currentView === 'agents' && <AgentsView />}

          {currentView === 'mcp' && <McpView onShowToast={addToast} />}

          {currentView === 'image_studio' && (
            <ImageStudioView onShowToast={addToast} />
          )}

          {currentView === 'settings' && (
            <SettingsView
              config={config}
              onUpdateConfig={setConfig}
              onShowToast={addToast}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <WorkspaceProvider>
      <AppContent />
    </WorkspaceProvider>
  );
}
