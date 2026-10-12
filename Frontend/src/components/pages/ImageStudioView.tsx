import React, { useEffect, useState, useRef } from 'react';
import {
  Wand2,
  Sparkles,
  Image as ImageIcon,
  Loader2,
  Download,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Copy,
  Check,
  Maximize2,
  Sliders,
  Layers,
  Film,
  FileText,
  Upload,
  Trash2,
  Info,
  Compass,
  ArrowRight,
  X,
  ExternalLink
} from 'lucide-react';
import {
  ForgeStatusResponse,
  GeneratedImageResponse,
  imageStudioApi,
  imageFileUrl,
  imageFileDownloadUrl,
  SceneImagesResponse,
} from '../../api/mediaApi';

// Explicit generation lifecycle states (task §6).
type ForgeState = 'checking' | 'online' | 'offline';
type GenState = 'idle' | 'preparing' | 'generating' | 'completed' | 'failed';

interface ImageStudioViewProps {
  onShowToast: (title: string, message: string, type?: 'success' | 'info' | 'error') => void;
}

interface ImageHistoryItem extends GeneratedImageResponse {
  id: string;
  prompt: string;
  createdAt: string;
}

const STYLE_PRESETS = [
  { label: 'Photorealistic 8K', suffix: ', highly detailed photograph, 8k resolution, cinematic lighting, photorealistic, shot on 35mm lens' },
  { label: 'Cinematic 35mm', suffix: ', cinematic still, 35mm film photography, anamorphic lens flare, moody color grading, masterpiece' },
  { label: '3D Isometric', suffix: ', 3d isometric render, blender cycles, clean geometric forms, soft studio lighting, high poly count' },
  { label: 'Cyberpunk Neon', suffix: ', cyberpunk aesthetic, volumetric neon fog, glowing holographic UI, moody dark rainy atmosphere' },
  { label: 'Minimalist Vector', suffix: ', clean vector illustration, flat design, modern UI graphic style, bold palettes, Behance trending' },
  { label: 'Editorial Magazine', suffix: ', luxury editorial photography, studio lighting, Hasselblad H6D, award-winning composition' },
  { label: 'Digital Oil', suffix: ', digital oil painting, expressive brushwork, fine art texture, dramatic chiaroscuro' },
  { label: 'Anime Concept', suffix: ', makoto shinkai aesthetic, vivid sky, gorgeous anime keyframe, atmospheric lighting' },
];

const PROMPT_INSPIRATIONS = [
  'A state-of-the-art quantum computing server core floating inside a minimalist glass datacenter, glowing cyan and violet optic cables',
  'Futuristic automated drone greenhouse nurturing bioluminescent flora under atmospheric glass domes on Mars, high detail',
  'Isometric illustration of an AI neural transformation engine with interconnected crystalline data nodes and glowing light beams',
  'Cinematic close-up portrait of an android engineer assembling precision micro-optics in a cleanroom, dramatic rim lighting',
  'Modern executive dashboard interface visualized as a holographic floating glass monolith in a sleek boardroom',
  'Solar-powered high-speed magnetic levitation train gliding over a lush cybernetic smart city with green rooftop parks',
];

const ASPECT_RATIOS = [
  { id: '1:1', label: '1:1 Square', width: 512, height: 512, desc: 'Social & Avatars' },
  { id: '16:9', label: '16:9 Landscape', width: 768, height: 432, desc: 'Headers & Video' },
  { id: '9:16', label: '9:16 Portrait', width: 432, height: 768, desc: 'Stories & Mobile' },
  { id: '4:3', label: '4:3 Standard', width: 640, height: 480, desc: 'Presentations' },
];

const QUALITY_MODES: Array<{ id: 'fast' | 'balanced' | 'quality'; label: string; steps: number; desc: string }> = [
  { id: 'fast', label: 'Fast Preview', steps: 18, desc: '18 steps · Rapid testing' },
  { id: 'balanced', label: 'Balanced', steps: 22, desc: '22 steps · Recommended' },
  { id: 'quality', label: 'High Fidelity', steps: 28, desc: '28 steps · Maximum detail' },
];

const STORAGE_KEY = 'gentransform_image_studio_history_v1';

export const ImageStudioView: React.FC<ImageStudioViewProps> = ({ onShowToast }) => {
  const [activeTab, setActiveTab] = useState<'txt2img' | 'scene_script'>('txt2img');

  // Generation parameters
  const [prompt, setPrompt] = useState('');
  const [negativePrompt, setNegativePrompt] = useState('blurry, low quality, distorted, extra limbs, artifacts, watermark, deformed, noisy, empty room, empty office, vacant boardroom, conference table, empty chairs, blank screen');
  const [showNegative, setShowNegative] = useState(false);
  const [mode, setMode] = useState<'fast' | 'balanced' | 'quality'>('fast');
  const [aspectRatio, setAspectRatio] = useState('1:1');
  const [customSteps, setCustomSteps] = useState(18);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Status & Generation state
  const [isGenerating, setIsGenerating] = useState(false);
  const [genState, setGenState] = useState<GenState>('idle');
  const [currentResult, setCurrentResult] = useState<GeneratedImageResponse | null>(null);
  const [lastPromptUsed, setLastPromptUsed] = useState('');
  const [forgeStatus, setForgeStatus] = useState<ForgeStatusResponse | null>(null);
  const [isCheckingStatus, setIsCheckingStatus] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Prompt-enhancement agent state (task §3)
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [enhancedPrompt, setEnhancedPrompt] = useState<string | null>(null);
  const [enhanceMeta, setEnhanceMeta] = useState<{ subject: string; llm_used: boolean; warning?: string | null } | null>(null);
  const [appliedStyle, setAppliedStyle] = useState<string | null>(null);

  // History & Lightbox
  const [history, setHistory] = useState<ImageHistoryItem[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [lightboxImage, setLightboxImage] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Scene Script generation
  const [sceneScript, setSceneScript] = useState('');
  const [isGeneratingScenes, setIsGeneratingScenes] = useState(false);
  const [sceneResults, setSceneResults] = useState<SceneImagesResponse | null>(null);
  const [sceneFileUploading, setSceneFileUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Sync history to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(0, 30)));
    } catch {
      // Ignore localStorage quotas
    }
  }, [history]);

  // Check Forge health on mount
  const checkForgeHealth = async () => {
    setIsCheckingStatus(true);
    try {
      const status = await imageStudioApi.getStatus();
      setForgeStatus(status);
    } catch {
      setForgeStatus({
        forge_url: 'http://127.0.0.1:7860',
        online: false,
        message: 'Could not contact backend image service (Port 8000).',
      });
    } finally {
      setIsCheckingStatus(false);
    }
  };

  useEffect(() => {
    void checkForgeHealth();
  }, []);

  // Update steps when mode changes
  const handleModeChange = (newMode: 'fast' | 'balanced' | 'quality') => {
    setMode(newMode);
    const modeConfig = QUALITY_MODES.find(m => m.id === newMode);
    if (modeConfig) {
      setCustomSteps(modeConfig.steps);
    }
  };

  // Get current dimensions
  const currentDimensions = ASPECT_RATIOS.find(r => r.id === aspectRatio) || ASPECT_RATIOS[0];

  // Append style preset (tracked so the enhance agent can use it as a constraint)
  const handleApplyPreset = (label: string, suffix: string) => {
    setAppliedStyle(label);
    setPrompt(prev => {
      const trimmed = prev.trim();
      if (!trimmed) return suffix.replace(/^,\s*/, '');
      if (trimmed.endsWith('.')) {
        return trimmed.slice(0, -1) + suffix;
      }
      return trimmed + suffix;
    });
  };

  // Image Prompt Enhancement Agent: long/instructional text -> visual prompt.
  const handleEnhancePrompt = async () => {
    if (!prompt.trim() || isEnhancing || isGenerating) return;
    setIsEnhancing(true);
    setGenState('preparing');
    setError(null);
    try {
      const res = await imageStudioApi.enhancePrompt({
        text: prompt.trim().slice(0, 12000),
        style: appliedStyle || undefined,
        negative_prompt: showNegative && negativePrompt.trim() ? negativePrompt.trim() : undefined,
        aspect_ratio: aspectRatio,
      });
      setEnhancedPrompt(res.enhanced_prompt);
      setEnhanceMeta({ subject: res.subject, llm_used: res.llm_used, warning: res.warning });
      setGenState('idle');
      onShowToast(
        'Prompt Enhanced',
        res.llm_used ? `Visual prompt ready (${res.subject.slice(0, 80)}). Review and generate.` : 'Deterministic enhancement ready (LLM offline). Review and generate.',
        'success',
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Prompt enhancement failed.';
      setError(msg);
      setGenState('failed');
      onShowToast('Enhancement Failed', msg, 'error');
    } finally {
      setIsEnhancing(false);
    }
  };

  // Pick random inspiration
  const handleRandomInspiration = () => {
    const random = PROMPT_INSPIRATIONS[Math.floor(Math.random() * PROMPT_INSPIRATIONS.length)];
    setPrompt(random);
  };

  // Execute Generation (duplicate-safe: early return while in flight; Ctrl+Enter guarded by same flag)
  const handleGenerate = async (promptOverride?: string) => {
    const source = (promptOverride ?? prompt).trim();
    if (!source || isGenerating) return;
    setIsGenerating(true);
    setGenState('generating');
    setError(null);
    // NOTE: currentResult is intentionally preserved until success so a failed
    // retry never wipes the last good image (task §6).

    const activePrompt = source;
    setLastPromptUsed(activePrompt);

    try {
      const response = await imageStudioApi.generate({
        prompt: activePrompt.slice(0, 4000),
        negative_prompt: showNegative && negativePrompt.trim() ? negativePrompt.trim() : undefined,
        mode,
        width: currentDimensions.width,
        height: currentDimensions.height,
        steps: customSteps,
      });

      setCurrentResult(response);
      setGenState('completed');

      // Add to history
      const historyEntry: ImageHistoryItem = {
        ...response,
        id: `img-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
        prompt: activePrompt,
        createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setHistory(prev => [historyEntry, ...prev.filter(item => item.filename !== response.filename)]);

      onShowToast(
        response.synthetic ? 'UI Preview Rendered (Not AI)' : 'Image Rendered Successfully',
        response.synthetic
          ? 'Forge is offline — this is a labeled UI preview, not diffusion output. Start Forge and regenerate for real imagery.'
          : `Rendered on ${response.device.toUpperCase()} in ${response.generation_time}s (${response.width}x${response.height}, ${response.steps} steps).`,
        response.synthetic ? 'info' : 'success'
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Image generation encountered an error.';
      setError(msg);
      setGenState('failed');
      onShowToast('Generation Failed', msg, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  // Handle Scene Script Generation
  const handleGenerateScenes = async () => {
    if (!sceneScript.trim() || isGeneratingScenes) return;
    setIsGeneratingScenes(true);
    try {
      const res = await imageStudioApi.generateSceneImages(sceneScript.trim(), {
        mode,
        width: currentDimensions.width,
        height: currentDimensions.height,
        steps: customSteps,
      });
      setSceneResults(res);
      const previews = res.images.filter(i => i.synthetic).length;
      onShowToast(
        previews ? 'Scene Previews Rendered' : 'Scenes Generated',
        previews
          ? `${res.images.length} boards rendered as labeled UI previews (Forge offline). Start Forge for real diffusion.`
          : `Synthesized ${res.images.length} scene visual boards in order.`,
        previews ? 'info' : 'success',
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to generate scene storyboard.';
      onShowToast('Scene Generation Failed', msg, 'error');
    } finally {
      setIsGeneratingScenes(false);
    }
  };

  // Regenerate a single scene image from its engineered prompt (preserves ordering).
  const handleRegenerateScene = async (sceneIdx: number) => {
    const scenePrompt = sceneResults?.scenes?.[sceneIdx]?.prompt;
    if (!scenePrompt || isGeneratingScenes) return;
    setIsGeneratingScenes(true);
    try {
      const res = await imageStudioApi.generate({
        prompt: scenePrompt.slice(0, 4000),
        mode,
        width: currentDimensions.width,
        height: currentDimensions.height,
        steps: customSteps,
      });
      setSceneResults(prev => {
        if (!prev) return prev;
        const images = prev.images.map((img, i) => (i === sceneIdx ? res : img));
        return { ...prev, images };
      });
      onShowToast(res.synthetic ? 'Scene Preview Regenerated' : 'Scene Regenerated', `Scene ${sceneIdx + 1} updated.`, res.synthetic ? 'info' : 'success');
    } catch (err) {
      onShowToast('Scene Regeneration Failed', err instanceof Error ? err.message : 'Failed.', 'error');
    } finally {
      setIsGeneratingScenes(false);
    }
  };

  // Handle Scene File Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSceneFileUploading(true);
    try {
      const res = await imageStudioApi.generateSceneImagesFromFile(file);
      setSceneResults(res);
      onShowToast('Document Processed', `Generated visuals for ${file.name}.`, 'success');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to process document file.';
      onShowToast('Upload Failed', msg, 'error');
    } finally {
      setSceneFileUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const copyText = (text: string, id: string) => {
    void navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
    onShowToast('Copied', 'Prompt copied to clipboard.', 'info');
  };

  const clearHistory = () => {
    setHistory([]);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Ignore
    }
    onShowToast('History Cleared', 'All session generated images removed.', 'info');
  };

  return (
    <div className="space-y-6 pb-20 max-w-7xl mx-auto">
      {/* ── TOP HEADER ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-cyan-400 uppercase tracking-wider mb-1">
            <Wand2 className="w-4 h-4 text-cyan-400" />
            <span>Generative Visual Studio</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <span>AI Image Studio</span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
              Forge &amp; Qwen
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Direct prompt-to-image synthesis, cinematic asset design, and script-driven scene storyboard generation.
          </p>
        </div>

        {/* Forge Status Badge & Actions */}
        <div className="flex items-center gap-2.5">
          <div className={`px-3 py-1.5 rounded-xl border text-xs flex items-center gap-2 shadow-sm ${
            isCheckingStatus
              ? 'bg-slate-500/10 border-slate-500/30 text-slate-300'
              : forgeStatus?.online
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
          }`}>
            {isCheckingStatus ? (
              <RefreshCw className="w-4 h-4 animate-spin text-cyan-400 shrink-0" />
            ) : forgeStatus?.online ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            )}
            <div className="leading-tight">
              <span className="font-semibold block">
                {isCheckingStatus ? 'Checking Forge…' : forgeStatus?.online ? 'Forge Online' : 'Forge Offline'}
              </span>
              <span className="text-[10px] opacity-80 font-mono">
                {forgeStatus?.forge_url || 'http://127.0.0.1:7860'}
                {forgeStatus?.latency_ms != null && forgeStatus.online ? ` · ${forgeStatus.latency_ms}ms` : ''}
              </span>
            </div>
          </div>

          <button
            onClick={() => void checkForgeHealth()}
            disabled={isCheckingStatus}
            title="Refresh Stable Diffusion Forge connection status"
            className="p-2 rounded-xl bg-slate-850 hover:bg-slate-800 border border-slate-700/60 text-slate-300 hover:text-white transition-colors cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isCheckingStatus ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Forge Guidance Notice if Offline */}
      {forgeStatus && !forgeStatus.online && !isCheckingStatus && (
        <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-500/30 text-xs text-amber-200/90 flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-amber-200">
                Forge Offline — real diffusion unavailable on port 7860.
              </p>
              <p className="text-amber-300/75 mt-0.5 text-[11px] leading-relaxed">
                Direct generation will return an explicitly labeled UI preview (never claimed as AI imagery).
                To enable real Stable Diffusion, run <code className="px-1.5 py-0.5 rounded bg-black/40 text-amber-200 font-mono">start.bat</code> (which launches Forge with <code className="px-1.5 py-0.5 rounded bg-black/40 text-amber-200 font-mono">--api --port 7860</code>).
              </p>
            </div>
          </div>
          <button
            onClick={() => void checkForgeHealth()}
            disabled={isCheckingStatus}
            className="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 text-[11px] font-medium shrink-0 cursor-pointer disabled:opacity-50"
          >
            {isCheckingStatus ? 'Checking…' : 'Recheck Port 7860'}
          </button>
        </div>
      )}

      {/* Navigation Studio Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab('txt2img')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'txt2img'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span>Direct Txt2Img Studio</span>
        </button>

        <button
          onClick={() => setActiveTab('scene_script')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'scene_script'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
          }`}
        >
          <Film className="w-4 h-4" />
          <span>Scene Storyboard &amp; Script</span>
        </button>
      </div>

      {/* ── TAB 1: DIRECT TXT2IMG STUDIO ── */}
      {activeTab === 'txt2img' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Controls Column (7 cols) */}
          <div className="lg:col-span-7 space-y-5">
            {/* Prompt Box */}
            <div className="p-5 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-3.5 shadow-lg">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Creative Prompt</span>
                </label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleRandomInspiration}
                    className="flex items-center gap-1 text-[11px] text-cyan-400 hover:text-cyan-300 transition-colors cursor-pointer px-2 py-0.5 rounded-md hover:bg-cyan-500/10"
                    title="Insert sample creative prompt"
                  >
                    <Compass className="w-3.5 h-3.5" />
                    <span>Inspiration</span>
                  </button>
                  {prompt && (
                    <button
                      onClick={() => setPrompt('')}
                      className="text-[11px] text-slate-400 hover:text-rose-400 transition-colors cursor-pointer px-2 py-0.5 rounded-md hover:bg-rose-500/10"
                    >
                      Clear
                    </button>
                  )}
                </div>
              </div>

              <div className="relative">
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                      void handleGenerate();
                    }
                  }}
                  rows={4}
                  maxLength={4000}
                  placeholder="Describe the image in rich detail: subject, setting, aesthetic, lighting, lens, mood... (Ctrl + Enter to generate)"
                  className="w-full px-4 py-3 rounded-xl bg-slate-950/80 border border-slate-800 text-white text-xs leading-relaxed resize-none focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/30 transition-all font-sans placeholder:text-slate-500"
                  disabled={isGenerating}
                />
                <div className="absolute right-3 bottom-2 text-[10px] text-slate-500 font-mono">
                  {prompt.length}/4000
                </div>
              </div>

              {/* Style Presets */}
              <div className="space-y-1.5">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                  Quick Style Injectors
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {STYLE_PRESETS.map((style) => (
                    <button
                      key={style.label}
                      type="button"
                      onClick={() => handleApplyPreset(style.label, style.suffix)}
                      disabled={isGenerating || isEnhancing}
                      className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-slate-900 border border-slate-800 text-slate-300 hover:text-cyan-300 hover:border-cyan-500/40 hover:bg-cyan-950/20 transition-all cursor-pointer"
                    >
                      + {style.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* AI Prompt Enhancement Agent */}
              <div className="space-y-2 pt-2 border-t border-slate-800/80">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                    Image Prompt Enhancement Agent
                  </span>
                  {appliedStyle && (
                    <span className="text-[10px] font-mono text-cyan-400">style: {appliedStyle}</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void handleEnhancePrompt()}
                    disabled={isEnhancing || isGenerating || !prompt.trim()}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/40 text-violet-200 transition-all cursor-pointer disabled:opacity-50"
                  >
                    {isEnhancing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    <span>{isEnhancing ? 'Enhancing…' : 'Enhance Prompt with AI'}</span>
                  </button>
                  {enhancedPrompt && (
                    <button
                      type="button"
                      onClick={() => void handleGenerate(enhancedPrompt)}
                      disabled={isGenerating || isEnhancing}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-all cursor-pointer disabled:opacity-50"
                    >
                      <ArrowRight className="w-3.5 h-3.5" />
                      <span>Generate from Enhanced</span>
                    </button>
                  )}
                </div>
                {enhancedPrompt && (
                  <div className="p-3 rounded-xl bg-violet-950/20 border border-violet-500/30 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-violet-300 uppercase tracking-wider">
                        Enhanced visual prompt (editable)
                      </span>
                      <button
                        onClick={() => copyText(enhancedPrompt, 'enhanced-prompt')}
                        className="text-slate-400 hover:text-white transition-colors cursor-pointer"
                        title="Copy enhanced prompt"
                      >
                        {copiedId === 'enhanced-prompt' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <textarea
                      value={enhancedPrompt}
                      onChange={(e) => setEnhancedPrompt(e.target.value)}
                      rows={4}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950/80 border border-violet-500/20 text-violet-100/90 text-[11px] leading-relaxed resize-none focus:outline-none focus:border-violet-500/50 font-sans"
                      disabled={isGenerating || isEnhancing}
                    />
                    {enhanceMeta && (
                      <p className="text-[10px] text-slate-400">
                        subject: {enhanceMeta.subject.slice(0, 120)} · {enhanceMeta.llm_used ? 'LLM-enhanced' : 'deterministic fallback'}
                        {enhanceMeta.warning ? ` · ${enhanceMeta.warning}` : ''}
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Negative Prompt Toggle */}
              <div className="pt-2 border-t border-slate-800/80">
                <button
                  type="button"
                  onClick={() => setShowNegative(!showNegative)}
                  className="text-[11px] font-medium text-slate-400 hover:text-slate-200 flex items-center gap-1.5 cursor-pointer"
                >
                  <Sliders className="w-3.5 h-3.5 text-cyan-400" />
                  <span>{showNegative ? 'Hide Negative Prompt' : '+ Add Negative Prompt'}</span>
                </button>

                {showNegative && (
                  <div className="mt-2 space-y-1">
                    <textarea
                      value={negativePrompt}
                      onChange={(e) => setNegativePrompt(e.target.value)}
                      rows={2}
                      placeholder="Undesired elements: blurry, lowres, distorted faces..."
                      className="w-full px-3 py-2 rounded-xl bg-slate-950/80 border border-slate-800 text-rose-200/90 text-xs leading-relaxed resize-none focus:outline-none focus:border-rose-500/40 font-sans"
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Geometry & Resolution Settings */}
            <div className="p-5 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-4 shadow-lg">
              {/* Aspect Ratio */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-white uppercase tracking-wider">
                    Aspect Ratio &amp; Dimensions
                  </label>
                  <span className="text-xs font-mono text-cyan-400">
                    {currentDimensions.width} × {currentDimensions.height} px
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {ASPECT_RATIOS.map((ratio) => {
                    const isSelected = aspectRatio === ratio.id;
                    return (
                      <button
                        key={ratio.id}
                        type="button"
                        onClick={() => setAspectRatio(ratio.id)}
                        disabled={isGenerating}
                        className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-cyan-500/15 border-cyan-500/60 text-white shadow-sm'
                            : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold">{ratio.id}</span>
                          <span className="text-[10px] font-mono opacity-60">
                            {ratio.width}×{ratio.height}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-400 mt-0.5 truncate">{ratio.desc}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Quality & Sampling Mode */}
              <div className="space-y-2 pt-2 border-t border-slate-800/80">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-white uppercase tracking-wider">
                    Quality &amp; Steps
                  </label>
                  <span className="text-xs font-mono text-slate-400">
                    {customSteps} sampling steps
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {QUALITY_MODES.map((m) => {
                    const isSelected = mode === m.id;
                    return (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => handleModeChange(m.id)}
                        disabled={isGenerating}
                        className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-cyan-500/15 border-cyan-500/60 text-white'
                            : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                        }`}
                      >
                        <span className="text-xs font-bold block">{m.label}</span>
                        <span className="text-[10px] text-slate-400 block mt-0.5">{m.desc}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Advanced Step Override */}
              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1.5 cursor-pointer"
                >
                  <Sliders className="w-3.5 h-3.5" />
                  <span>{showAdvanced ? 'Hide Step Slider' : 'Fine-tune steps slider'}</span>
                </button>

                {showAdvanced && (
                  <div className="flex items-center gap-3 w-1/2">
                    <input
                      type="range"
                      min={10}
                      max={40}
                      value={customSteps}
                      onChange={(e) => setCustomSteps(parseInt(e.target.value, 10))}
                      className="w-full accent-cyan-500"
                    />
                    <span className="text-xs font-mono text-cyan-400 font-bold w-6 text-right">
                      {customSteps}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Big Generate Button */}
            <button
              onClick={() => void handleGenerate()}
              disabled={isGenerating || isEnhancing || !prompt.trim()}
              className="w-full group relative flex items-center justify-center gap-3 px-6 py-4 rounded-2xl bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 hover:from-cyan-500 hover:via-blue-500 hover:to-indigo-500 text-white font-bold text-sm shadow-xl shadow-cyan-600/25 hover:shadow-cyan-600/40 transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Generating Image… ({customSteps} steps)</span>
                </>
              ) : genState === 'preparing' || isEnhancing ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Preparing Prompt…</span>
                </>
              ) : (
                <>
                  <Wand2 className="w-5 h-5 text-cyan-200 group-hover:rotate-12 transition-transform" />
                  <span>Generate Image</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-black/30 border border-white/20 text-cyan-200">
                    Ctrl+Enter
                  </span>
                </>
              )}
            </button>

            {/* Error Message */}
            {error && (
              <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/40 text-xs text-rose-200 flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-semibold">Generation Failed</p>
                  <p className="mt-0.5 text-rose-300/80 break-words">{error}</p>
                  <button
                    onClick={() => void handleGenerate()}
                    disabled={isGenerating || !prompt.trim()}
                    className="mt-2 px-3 py-1.5 rounded-lg bg-rose-600/30 hover:bg-rose-600/50 border border-rose-500/40 text-rose-100 text-[11px] font-semibold cursor-pointer disabled:opacity-50"
                  >
                    Retry Generation
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Result & Gallery Column (5 cols) */}
          <div className="lg:col-span-5 space-y-5">
            {/* Active Output Showcase */}
            <div className="p-5 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-4 shadow-lg min-h-[460px] flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2.5">
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                    <ImageIcon className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Active Generation Viewport</span>
                  </h3>
                  {currentResult && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                      {currentResult.synthetic ? 'UI PREVIEW' : currentResult.device.toUpperCase()} · {currentResult.generation_time}s
                    </span>
                  )}
                </div>

                {isGenerating ? (
                  <div className="h-72 rounded-xl bg-slate-950/80 border border-dashed border-slate-800 flex flex-col items-center justify-center gap-3 text-slate-400">
                    <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
                    <div className="text-center">
                      <p className="text-xs font-semibold text-white">Generating Image…</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        {forgeStatus?.online ? 'Forge diffusion inference in progress (steps apply to real backend)' : 'Offline — rendering labeled UI preview'}
                      </p>
                    </div>
                  </div>
                ) : currentResult ? (
                  <div className="space-y-3">
                    {/* Real vs preview badge */}
                    <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                      currentResult.synthetic
                        ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                        : 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                    }`}>
                      {currentResult.synthetic ? 'UI PREVIEW — NOT AI-GENERATED' : 'AI-GENERATED'}
                    </div>
                    {/* Notice if synthetic placeholder */}
                    {currentResult.synthetic && currentResult.warning && (
                      <div className="p-2.5 rounded-xl bg-amber-950/30 border border-amber-500/30 text-[11px] text-amber-200">
                        {currentResult.warning}
                      </div>
                    )}

                    {/* Image Preview */}
                    <div className="relative group rounded-xl overflow-hidden border border-slate-800 bg-black/60">
                      <img
                        src={imageFileUrl(currentResult.filename)}
                        alt={lastPromptUsed}
                        className="w-full h-auto object-contain max-h-[380px] rounded-xl mx-auto cursor-pointer"
                        onClick={() => setLightboxImage(imageFileUrl(currentResult.filename))}
                      />
                      <button
                        onClick={() => setLightboxImage(imageFileUrl(currentResult.filename))}
                        className="absolute top-2 right-2 p-2 rounded-lg bg-black/70 hover:bg-black text-white text-xs opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer shadow-md"
                        title="View Fullscreen"
                      >
                        <Maximize2 className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Metadata & Actions */}
                    <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-2">
                      <p className="text-[11px] text-slate-300 line-clamp-2 italic">
                        &ldquo;{lastPromptUsed}&rdquo;
                      </p>
                      <div className="flex items-center justify-between pt-1 border-t border-slate-800 text-[10px] text-slate-400 font-mono">
                        <span>{currentResult.width}×{currentResult.height} px · {currentResult.steps} steps</span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => copyText(lastPromptUsed, 'active-prompt')}
                            className="p-1 text-slate-400 hover:text-white transition-colors cursor-pointer"
                            title="Copy Prompt"
                          >
                            {copiedId === 'active-prompt' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                          </button>
                          <a
                            href={imageFileDownloadUrl(currentResult.filename)}
                            download={currentResult.filename}
                            className="flex items-center gap-1 px-2.5 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-semibold transition-colors cursor-pointer"
                          >
                            <Download className="w-3 h-3" />
                            <span>Download PNG</span>
                          </a>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="h-72 rounded-xl bg-slate-950/50 border border-dashed border-slate-800/80 flex flex-col items-center justify-center p-6 text-center text-slate-400">
                    <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-3">
                      <ImageIcon className="w-6 h-6" />
                    </div>
                    <p className="text-sm font-semibold text-white">No image generated yet</p>
                    <p className="text-xs text-slate-400 max-w-xs mt-1">
                      Type a prompt on the left or select an inspiration preset to render your first generative output.
                    </p>
                  </div>
                )}
              </div>

              {/* Gallery / Session History */}
              <div className="mt-4 pt-4 border-t border-slate-800">
                <div className="flex items-center justify-between mb-2.5">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-slate-400" />
                    <span>Session History ({history.length})</span>
                  </span>
                  {history.length > 0 && (
                    <button
                      onClick={clearHistory}
                      className="text-[10px] text-slate-500 hover:text-rose-400 transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      <Trash2 className="w-3 h-3" /> Clear
                    </button>
                  )}
                </div>

                {history.length > 0 ? (
                  <div className="grid grid-cols-4 gap-2 max-h-36 overflow-y-auto p-1">
                    {history.map((item) => (
                      <div
                        key={item.id}
                        className="group relative rounded-lg overflow-hidden border border-slate-800 aspect-square bg-slate-950 cursor-pointer hover:border-cyan-500/50 transition-colors"
                        onClick={() => {
                          setCurrentResult(item);
                          setLastPromptUsed(item.prompt);
                        }}
                      >
                        <img
                          src={imageFileUrl(item.filename)}
                          alt={item.prompt.slice(0, 40)}
                          className="w-full h-full object-cover"
                        />
                        <span className={`absolute bottom-1 left-1 px-1 py-px rounded text-[8px] font-bold border ${
                          item.synthetic ? 'bg-amber-500/80 border-amber-600 text-black' : 'bg-emerald-500/80 border-emerald-600 text-black'
                        }`}>
                          {item.synthetic ? 'PREVIEW' : 'AI'}
                        </span>
                        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1.5 p-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setLightboxImage(imageFileUrl(item.filename));
                            }}
                            className="p-1 rounded bg-black/80 text-white hover:text-cyan-300"
                            title="Fullscreen"
                          >
                            <Maximize2 className="w-3 h-3" />
                          </button>
                          <a
                            href={imageFileDownloadUrl(item.filename)}
                            download={item.filename}
                            onClick={(e) => e.stopPropagation()}
                            className="p-1 rounded bg-black/80 text-white hover:text-cyan-300"
                            title="Download"
                          >
                            <Download className="w-3 h-3" />
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-500 italic text-center py-2">
                    Your generated images will be saved here during this session.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 2: SCENE STORYBOARD & SCRIPT GENERATOR ── */}
      {activeTab === 'scene_script' && (
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-[#0e1424] border border-slate-800 space-y-5 shadow-lg">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Film className="w-5 h-5 text-cyan-400" />
                <span>Script-Driven Scene Visualizer</span>
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Paste a script or narration text, or upload a document (.txt, .pdf, .docx). Qwen AI automatically decomposes it into sequenced visual scene prompts and renders corresponding visuals.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Text Input */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300 block">
                  Paste Script / Content Text
                </label>
                <textarea
                  value={sceneScript}
                  onChange={(e) => setSceneScript(e.target.value)}
                  rows={6}
                  placeholder="Scene 1: Introduction to clean energy initiatives across global cities...&#10;Scene 2: High-tech solar installations on commercial skylines...&#10;Scene 3: Community impact and sustainable grid storage systems."
                  className="w-full px-4 py-3 rounded-xl bg-slate-950/80 border border-slate-800 text-white text-xs leading-relaxed resize-none focus:outline-none focus:border-cyan-500/60 font-sans"
                  disabled={isGeneratingScenes}
                />
                <button
                  onClick={handleGenerateScenes}
                  disabled={isGeneratingScenes || !sceneScript.trim()}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold transition-all cursor-pointer disabled:opacity-50"
                >
                  {isGeneratingScenes ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Synthesizing Scene Boards...</span>
                    </>
                  ) : (
                    <>
                      <Wand2 className="w-4 h-4" />
                      <span>Generate Scene Images from Script</span>
                    </>
                  )}
                </button>
              </div>

              {/* File Upload Option */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300 block">
                  Or Upload Source Document (.txt, .pdf, .docx)
                </label>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="h-36 rounded-xl border border-dashed border-slate-700/80 hover:border-cyan-500/60 bg-slate-950/40 hover:bg-slate-950/70 transition-all flex flex-col items-center justify-center p-4 text-center cursor-pointer group"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".txt,.pdf,.docx"
                    className="hidden"
                    onChange={handleFileUpload}
                  />
                  {sceneFileUploading ? (
                    <div className="flex flex-col items-center gap-2">
                      <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
                      <span className="text-xs text-slate-300">Decomposing document into scenes...</span>
                    </div>
                  ) : (
                    <>
                      <Upload className="w-6 h-6 text-slate-400 group-hover:text-cyan-400 transition-colors mb-1.5" />
                      <p className="text-xs font-semibold text-slate-200">
                        Click to select script document
                      </p>
                      <p className="text-[10px] text-slate-500 mt-0.5">
                        PDF, DOCX, or Plain Text files supported
                      </p>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Scene Results Board */}
            {sceneResults && sceneResults.images && sceneResults.images.length > 0 && (
              <div className="space-y-4 pt-5 border-t border-slate-800">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Film className="w-4 h-4 text-cyan-400" />
                  <span>Synthesized Scene Storyboard ({sceneResults.images.length} scenes)</span>
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {sceneResults.images.map((img, idx) => (
                    <div
                      key={img.filename}
                      className="rounded-xl border border-slate-800 bg-slate-950/80 overflow-hidden shadow-md space-y-2.5 p-3"
                    >
                      <div className="relative group rounded-lg overflow-hidden border border-slate-800 bg-black aspect-video">
                        <img
                          src={imageFileUrl(img.filename)}
                          alt={`Scene ${idx + 1}`}
                          className="w-full h-full object-cover cursor-pointer"
                          onClick={() => setLightboxImage(imageFileUrl(img.filename))}
                        />
                        <button
                          onClick={() => setLightboxImage(imageFileUrl(img.filename))}
                          className="absolute top-2 right-2 p-1.5 rounded bg-black/70 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Maximize2 className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-bold text-cyan-300">Scene {idx + 1}</span>
                        <span className={`px-1.5 py-px rounded text-[9px] font-bold border ${img.synthetic ? 'bg-amber-500/20 border-amber-500/40 text-amber-300' : 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'}`}>
                          {img.synthetic ? 'PREVIEW' : 'AI'}
                        </span>
                      </div>
                      {sceneResults.scenes?.[idx]?.prompt && (
                        <p className="text-[10px] text-slate-400 line-clamp-3 italic" title={sceneResults.scenes[idx].prompt}>
                          {sceneResults.scenes[idx].prompt}
                        </p>
                      )}
                      <div className="flex items-center justify-between text-[11px] pt-1 border-t border-slate-800/60">
                        <button
                          onClick={() => void handleRegenerateScene(idx)}
                          disabled={isGeneratingScenes}
                          className="flex items-center gap-1 text-slate-400 hover:text-cyan-300 transition-colors cursor-pointer disabled:opacity-50"
                        >
                          <RefreshCw className="w-3 h-3" />
                          <span>Regenerate</span>
                        </button>
                        <a
                          href={imageFileDownloadUrl(img.filename)}
                          download={img.filename}
                          className="flex items-center gap-1 text-slate-400 hover:text-white transition-colors"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>PNG</span>
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── LIGHTBOX MODAL ── */}
      {lightboxImage && (
        <div
          className="fixed inset-0 z-50 bg-black/95 backdrop-blur-md flex items-center justify-center p-4"
          onClick={() => setLightboxImage(null)}
        >
          <div className="relative max-w-5xl max-h-[92vh] flex flex-col items-center">
            <button
              onClick={() => setLightboxImage(null)}
              className="absolute -top-10 right-0 text-slate-300 hover:text-white p-1 text-xs flex items-center gap-1 cursor-pointer"
            >
              <X className="w-5 h-5" />
              <span>Close</span>
            </button>
            <img
              src={lightboxImage}
              alt="Lightbox Full Preview"
              className="max-w-full max-h-[85vh] rounded-2xl shadow-2xl border border-slate-800 object-contain"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </div>
  );
};
