import React, { useEffect, useState } from 'react';
import {
  Image as ImageIcon,
  Loader2,
  Download,
  X,
  Wand2,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import {
  ForgeStatusResponse,
  GeneratedImageResponse,
  imageStudioApi,
  imageFileUrl,
  imageFileDownloadUrl,
} from '../../api/mediaApi';

interface ImageStudioModalProps {
  isOpen: boolean;
  onClose: () => void;
  onShowToast: (title: string, message: string, type?: 'success' | 'info' | 'error') => void;
}

const MODES: Array<{ id: 'fast' | 'balanced' | 'quality'; label: string }> = [
  { id: 'fast', label: 'Fast (768px · 10 steps)' },
  { id: 'balanced', label: 'Balanced (768px · 18 steps)' },
  { id: 'quality', label: 'Quality (1024px · 28 steps)' },
];

/**
 * Direct Stable Diffusion Forge image generation from a prompt.
 * Falls back to a labeled placeholder when Forge (port 7860) is offline.
 */
export const ImageStudioModal: React.FC<ImageStudioModalProps> = ({
  isOpen,
  onClose,
  onShowToast,
}) => {
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState<'fast' | 'balanced' | 'quality'>('fast');
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState<GeneratedImageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forgeStatus, setForgeStatus] = useState<ForgeStatusResponse | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  // Probe Forge once on open so the user knows which mode they're in (real check, never assumed)
  useEffect(() => {
    if (!isOpen) return;
    setForgeStatus(null);
    setIsChecking(true);
    imageStudioApi
      .getStatus()
      .then(setForgeStatus)
      .catch(() =>
        setForgeStatus({
          forge_url: 'http://127.0.0.1:7860',
          online: false,
          message: 'Could not reach the backend to check Forge status.',
        }),
      )
      .finally(() => setIsChecking(false));
  }, [isOpen]);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    if (!prompt.trim() || isGenerating) return;
    setIsGenerating(true);
    setError(null);
    // Preserve last good result until success (failed retry never wipes viewport).
    try {
      const response = await imageStudioApi.generate({
        prompt: prompt.trim().slice(0, 4000),
        mode,
      });
      setResult(response);
      onShowToast(
        response.synthetic ? 'UI Preview Rendered (Not AI)' : 'Image Generated',
        response.synthetic
          ? 'Forge is offline — labeled UI preview returned. Start Forge and regenerate for real imagery.'
          : `Rendered on ${response.device.toUpperCase()} in ${response.generation_time}s.`,
        response.synthetic ? 'info' : 'success',
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Image generation failed.';
      setError(message);
      onShowToast('Generation Failed', message, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-[#0e1422] border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl max-h-[92vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Wand2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-white text-sm">AI Image Studio</h3>
              <p className="text-[11px] text-slate-400">
                Stable Diffusion Forge · txt2img on the FastAPI backend
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isGenerating}
            className="text-slate-400 hover:text-white text-xs p-1 disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
          >
            ✕ Close
          </button>
        </div>

        {/* Forge status */}
        {(forgeStatus || isChecking) && (
          <div
            className={`p-2.5 rounded-xl text-[11px] flex items-center gap-2 border ${
              forgeStatus?.online
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
            }`}
          >
            {isChecking ? (
              <Loader2 className="w-4 h-4 shrink-0 animate-spin" />
            ) : forgeStatus?.online ? (
              <CheckCircle2 className="w-4 h-4 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 shrink-0" />
            )}
            <span>{isChecking ? 'Checking Forge on :7860…' : forgeStatus?.message}</span>
          </div>
        )}

        {/* Prompt */}
        <div className="space-y-1.5">
          <label className="font-semibold text-slate-400 uppercase tracking-wider text-[10px] block">
            Prompt
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            maxLength={4000}
            placeholder="Describe the image: subject, setting, lighting, mood, camera…"
            className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white text-xs leading-relaxed resize-none focus:outline-none focus:border-purple-500/60"
            disabled={isGenerating}
          />
        </div>

        {/* Mode */}
        <div className="space-y-1.5">
          <label className="font-semibold text-slate-400 uppercase tracking-wider text-[10px] block">
            Quality Mode
          </label>
          <div className="grid grid-cols-3 gap-1.5">
            {MODES.map((m) => (
              <button
                key={m.id}
                onClick={() => setMode(m.id)}
                disabled={isGenerating}
                className={`px-2 py-2 rounded-lg text-[11px] font-semibold transition-colors cursor-pointer disabled:cursor-not-allowed ${
                  mode === m.id
                    ? 'bg-cyan-600 text-white'
                    : 'bg-slate-950 border border-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        {/* Generate */}
        <button
          onClick={handleGenerate}
          disabled={isGenerating || !prompt.trim()}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 hover:from-cyan-500 hover:via-blue-500 hover:to-indigo-500 text-white text-sm font-bold shadow-lg shadow-cyan-600/25 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Generating…</span>
            </>
          ) : (
            <>
              <ImageIcon className="w-4 h-4" />
              <span>Generate Image</span>
            </>
          )}
        </button>

        {/* Error */}
        {error && (
          <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/40 text-[11px] text-rose-200 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Generation failed</p>
              <p className="mt-0.5 text-rose-300/80 break-words">{error}</p>
            </div>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="space-y-3">
            {result.synthetic && result.warning && (
              <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-500/40 text-[11px] text-amber-200">
                {result.warning}
              </div>
            )}
            <img
              src={imageFileUrl(result.filename)}
              alt={prompt.slice(0, 80)}
              className="w-full rounded-xl border border-slate-800"
            />
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-mono text-slate-400">
                {result.width}×{result.height} · {result.steps} steps · {result.generation_time}s ·{' '}
                {result.device.toUpperCase()}
              </span>
              <a
                href={imageFileDownloadUrl(result.filename)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" /> Download PNG
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
