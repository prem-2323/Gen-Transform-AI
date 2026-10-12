import React, { useState } from 'react';
import { 
  Linkedin, 
  Copy, 
  Check, 
  Download, 
  Share2, 
  Sparkles, 
  RotateCw, 
  Edit3, 
  CheckCircle2, 
  Send,
  Image as ImageIcon,
  Loader2,
  Trash2,
  Ratio
} from 'lucide-react';
import { LinkedInDeliverable } from '../../../types';
import { StatusBadge } from '../../common/StatusBadge';
import { imageStudioApi, imageFileUrl } from '../../../api/mediaApi';

type ExportRatio = '1.91:1' | '1:1' | '4:5' | '16:9';

interface RatioConfig {
  id: ExportRatio;
  label: string;
  dimensions: string;
  width: number;
  height: number;
  useCase: string;
}

const RATIO_CONFIGS: Record<ExportRatio, RatioConfig> = {
  '1.91:1': {
    id: '1.91:1',
    label: '1.91:1',
    dimensions: '1200 × 627',
    width: 1200,
    height: 627,
    useCase: 'Landscape Feed'
  },
  '1:1': {
    id: '1:1',
    label: '1:1',
    dimensions: '1080 × 1080',
    width: 1080,
    height: 1080,
    useCase: 'Square Feed'
  },
  '4:5': {
    id: '4:5',
    label: '4:5',
    dimensions: '1080 × 1350',
    width: 1080,
    height: 1350,
    useCase: 'Portrait Mobile'
  },
  '16:9': {
    id: '16:9',
    label: '16:9',
    dimensions: '1200 × 675',
    width: 1200,
    height: 675,
    useCase: 'Presentation'
  }
};

interface LinkedInCardProps {
  deliverable: LinkedInDeliverable;
  onUpdate: (updated: LinkedInDeliverable) => void;
  onPublishToMcp?: () => void;
  onShowToast: (title: string, message: string, type?: 'success' | 'info' | 'error') => void;
}

export const LinkedInCard: React.FC<LinkedInCardProps> = ({
  deliverable,
  onUpdate,
  onPublishToMcp,
  onShowToast
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [hook, setHook] = useState(deliverable.hook);
  const [body, setBody] = useState(deliverable.body);
  const [cta, setCta] = useState(deliverable.callToAction);

  // Image Export State — matplotlib PNG rendered on the backend (no Forge needed)
  const [exportRatio, setExportRatio] = useState<ExportRatio>('1.91:1');
  const [visualUrl, setVisualUrl] = useState<string | null>(null);
  const [isGeneratingVisual, setIsGeneratingVisual] = useState(false);

  const currentRatio = RATIO_CONFIGS[exportRatio];

  const fullPostText = `${hook}\n\n${body}\n\n👉 ${cta}\n\n${deliverable.hashtags.join(' ')}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(fullPostText);
    setCopied(true);
    onShowToast('Copied to Clipboard', 'LinkedIn post copied ready for publication.', 'success');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSaveEdit = () => {
    onUpdate({
      ...deliverable,
      hook,
      body,
      callToAction: cta,
      characterCount: fullPostText.length
    });
    setIsEditing(false);
    onShowToast('Updated', 'LinkedIn post edits saved successfully.', 'info');
  };

  const handleDownload = () => {
    const blob = new Blob([fullPostText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `LinkedIn_Post_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    onShowToast('Downloaded', 'LinkedIn post exported as .txt', 'success');
  };

  // Matplotlib visual — maps post text into infographic renderer (1200×627 default)
  const handleGenerateImage = async () => {
    if (isGeneratingVisual) return;
    setIsGeneratingVisual(true);
    try {
      const bodyChunks = body.split(/\n+/).map((s) => s.trim()).filter(Boolean);
      const res = await imageStudioApi.generateInfographic({
        key_message: hook || 'Executive insight',
        key_statistics: [
          { value: `${fullPostText.length}`, label: 'Characters', subtext: 'post length' },
          { value: `${deliverable.hashtags.length}`, label: 'Hashtags', subtext: 'reach tags' },
          { value: `${bodyChunks.length || 1}`, label: 'Key points', subtext: 'in body' },
          { value: currentRatio.label, label: currentRatio.useCase, subtext: currentRatio.dimensions },
        ],
        supporting_points: [
          { title: 'Core thesis', description: (bodyChunks[0] || body).slice(0, 140) },
          { title: 'Implication', description: (bodyChunks[1] || body).slice(0, 140) },
          { title: 'Audience', description: (deliverable.targetAudience || 'Executives').slice(0, 140) },
          { title: 'Next step', description: cta.slice(0, 140) },
        ],
        call_to_action: cta,
        layout: 'Horizontal',
        visual_style: 'Corporate',
        width: currentRatio.width,
        height: currentRatio.height,
      });
      setVisualUrl(imageFileUrl(res.filename));
      onUpdate({ ...deliverable, generatedImage: { id: res.filename, style: 'matplotlib', headline: hook, subheadline: cta, createdAt: new Date().toISOString() } });
      onShowToast('Visual Rendered', `Matplotlib graphic ready (${res.width}×${res.height} in ${res.generation_time}s).`, 'success');
    } catch (err: any) {
      onShowToast('Render Failed', err?.message || 'Backend unreachable on :8000.', 'error');
    } finally {
      setIsGeneratingVisual(false);
    }
  };

  const handleDownloadVisualPng = async () => {
    if (!visualUrl) return;
    try {
      const resp = await fetch(visualUrl);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `LinkedIn_Visual_${currentRatio.width}x${currentRatio.height}_${Date.now()}.png`;
      a.click();
      URL.revokeObjectURL(url);
      onShowToast('Image Exported', `Exported ${currentRatio.dimensions} px matplotlib PNG.`, 'success');
    } catch {
      window.open(visualUrl, '_blank');
    }
  };

  const handleDownloadImage = () => {
    const svgEl = document.getElementById('linkedin-visual-svg');
    if (!svgEl) return;

    const clonedSvg = svgEl.cloneNode(true) as SVGSVGElement;
    clonedSvg.setAttribute('width', String(currentRatio.width));
    clonedSvg.setAttribute('height', String(currentRatio.height));
    clonedSvg.setAttribute('viewBox', `0 0 ${currentRatio.width} ${currentRatio.height}`);

    const svgData = new XMLSerializer().serializeToString(clonedSvg);
    const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `LinkedIn_Post_Graphic_${currentRatio.width}x${currentRatio.height}_${exportRatio.replace(':', 'by')}_${Date.now()}.svg`;
    a.click();
    URL.revokeObjectURL(url);
    onShowToast('Image Exported', `Exported ${currentRatio.dimensions} px (${currentRatio.label}) vector graphic.`, 'success');
  };

  const handleRemoveImage = () => {
    onUpdate({
      ...deliverable,
      generatedImage: undefined
    });
    onShowToast('Image Removed', 'Attached post graphic cleared.', 'info');
  };

  // Color profile
  const themeColors = {
    bgStart: '#080d1a',
    bgEnd: '#10172a',
    accent1: '#a855f7',
    accent2: '#38bdf8',
    badgeBg: '#a855f7',
    badgeText: '#f3e8ff',
    border: '#334155'
  };

  const isVertical = exportRatio === '1:1' || exportRatio === '4:5';

  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0d121f] p-6 space-y-5 shadow-xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400">
            <Linkedin className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-white">LinkedIn Post</h3>
              <StatusBadge status="ready" size="xs" />
              {deliverable.generatedImage && (
                <span className="text-[10px] font-semibold text-purple-300 bg-purple-500/15 px-2 py-0.5 rounded border border-purple-500/30 flex items-center gap-1">
                  <ImageIcon className="w-3 h-3" /> Image Attached
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400">Optimized for executive reach & leadership discussion</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400 bg-slate-900 px-2 py-1 rounded border border-slate-800">
            {fullPostText.length} chars
          </span>
        </div>
      </div>

      {/* Post Content Area */}
      {isEditing ? (
        <div className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Hook / Opening Line</label>
            <textarea
              value={hook}
              onChange={(e) => setHook(e.target.value)}
              rows={2}
              className="w-full rounded-xl bg-slate-900 border border-slate-800 p-3 text-xs text-white focus:outline-none focus:border-purple-500"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Body Text</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={8}
              className="w-full rounded-xl bg-slate-900 border border-slate-800 p-3 text-xs text-white focus:outline-none focus:border-purple-500 font-sans leading-relaxed"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Call to Action</label>
            <input
              type="text"
              value={cta}
              onChange={(e) => setCta(e.target.value)}
              className="w-full rounded-xl bg-slate-900 border border-slate-800 p-3 text-xs text-white focus:outline-none focus:border-purple-500"
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              onClick={() => setIsEditing(false)}
              className="px-3.5 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs font-medium"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveEdit}
              className="px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold"
            >
              Save Changes
            </button>
          </div>
        </div>
      ) : (
        <div className="rounded-xl bg-slate-950/70 border border-slate-800/80 p-5 space-y-4 text-xs sm:text-sm text-slate-200 leading-relaxed font-sans select-text">
          {/* Post Hook */}
          <div className="font-bold text-white text-sm sm:text-base border-l-2 border-purple-500 pl-3">
            {deliverable.hook}
          </div>

          {/* Post Body */}
          <div className="whitespace-pre-line text-slate-300 leading-relaxed">
            {deliverable.body}
          </div>

          {/* Call to Action */}
          <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-purple-300 font-medium">
            👉 {deliverable.callToAction}
          </div>

          {/* Hashtags */}
          <div className="flex flex-wrap gap-1.5 pt-2 text-blue-400 font-mono text-xs">
            {deliverable.hashtags.map((tag, i) => (
              <span key={i} className="hover:underline cursor-pointer">{tag}</span>
            ))}
          </div>
        </div>
      )}

      {/* Rendered Attached Image View (backend-supplied visuals only) */}
      {deliverable.generatedImage && (
        <div className="pt-2 border-t border-slate-800/80 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 text-xs text-slate-400">
            <div className="flex items-center gap-2">
              <span className="font-semibold uppercase tracking-wider text-purple-400 flex items-center gap-1.5">
                <ImageIcon className="w-3.5 h-3.5" />
                <span>Generated Post Visual Graphic</span>
              </span>
              <span className="font-mono text-[10px] text-slate-400 bg-slate-900/90 px-2 py-0.5 rounded border border-slate-800">
                {currentRatio.dimensions} px · {currentRatio.label} ({currentRatio.useCase})
              </span>
            </div>

            {/* Target Element: Image Size & Export Ratio Selector */}
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-lg border border-slate-800 text-[11px]">
                <div className="flex items-center gap-1 text-slate-400 px-1.5 font-medium border-r border-slate-800 mr-0.5">
                  <Ratio className="w-3.5 h-3.5 text-purple-400" />
                  <span className="hidden sm:inline text-[10px] uppercase tracking-wider text-slate-400">Ratio</span>
                </div>
                {(['1.91:1', '1:1', '4:5', '16:9'] as const).map((rKey) => {
                  const r = RATIO_CONFIGS[rKey];
                  const isSelected = exportRatio === rKey;
                  return (
                    <button
                      key={rKey}
                      onClick={() => {
                        setExportRatio(rKey);
                        onShowToast('Export Ratio Changed', `Visual layout scaled to ${r.dimensions} px (${r.label}) for export.`, 'info');
                      }}
                      title={`${r.label} • ${r.dimensions} px (${r.useCase})`}
                      className={`px-2 py-1 rounded transition-all cursor-pointer flex items-center gap-1 font-mono text-[10px] ${
                        isSelected
                          ? 'bg-purple-600 text-white font-bold shadow-sm shadow-purple-600/40'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                      }`}
                    >
                      <span>{r.label}</span>
                      <span className={`text-[9px] hidden md:inline opacity-70 ${isSelected ? 'text-purple-100' : 'text-slate-500'}`}>
                        ({r.dimensions.split(' ')[0]})
                      </span>
                    </button>
                  );
                })}
              </div>

              <button
                onClick={handleDownloadImage}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-purple-600 text-slate-200 hover:text-white transition-colors cursor-pointer"
                title={`Export ${currentRatio.dimensions} (${currentRatio.label}) SVG`}
              >
                <Download className="w-3.5 h-3.5" />
              </button>

              <button
                onClick={handleRemoveImage}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-950/60 text-slate-400 hover:text-rose-400 transition-colors cursor-pointer"
                title="Remove Image"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Rendered SVG graphic dynamically sized by export ratio */}
          <div className="rounded-xl overflow-hidden border border-slate-800 bg-[#070b14] p-2 hover:border-slate-700 transition-colors shadow-2xl flex items-center justify-center">
            <svg
              id="linkedin-visual-svg"
              xmlns="http://www.w3.org/2000/svg"
              viewBox={`0 0 ${currentRatio.width} ${currentRatio.height}`}
              className="w-full h-auto rounded-lg shadow-inner select-none block transition-all"
              style={{
                maxHeight: exportRatio === '4:5' ? '540px' : exportRatio === '1:1' ? '460px' : '400px',
                aspectRatio: `${currentRatio.width} / ${currentRatio.height}`
              }}
            >
              <defs>
                <linearGradient id="liCardBgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor={themeColors.bgStart} />
                  <stop offset="100%" stopColor={themeColors.bgEnd} />
                </linearGradient>
                <linearGradient id="liAccentGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor={themeColors.accent1} />
                  <stop offset="100%" stopColor={themeColors.accent2} />
                </linearGradient>
                <pattern id="liGridPattern" width="32" height="32" patternUnits="userSpaceOnUse">
                  <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#334155" strokeWidth="0.5" opacity="0.25" />
                </pattern>
              </defs>

              {/* Background Canvas */}
              <rect width={currentRatio.width} height={currentRatio.height} fill="url(#liCardBgGrad)" rx="18" />
              <rect width={currentRatio.width} height={currentRatio.height} fill="url(#liGridPattern)" rx="18" />
              <rect width={currentRatio.width} height={currentRatio.height} fill="none" stroke={themeColors.border} strokeWidth="1.5" rx="18" />

              {/* Glowing Accent Top Bar */}
              <rect x="0" y="0" width={currentRatio.width} height="5" fill="url(#liAccentGrad)" rx="2" />

              {/* Decorative Glow Orbs */}
              <circle cx={currentRatio.width - 100} cy="90" r="140" fill={themeColors.accent1} opacity="0.08" />
              <circle cx="100" cy={currentRatio.height - 100} r="160" fill={themeColors.accent2} opacity="0.06" />

              {/* VERTICAL LAYOUT (1:1 Square & 4:5 Portrait) */}
              {isVertical ? (
                <>
                  {/* Header Badges */}
                  <g transform={`translate(50, ${exportRatio === '1:1' ? 44 : 56})`}>
                    <rect width="250" height="32" rx="6" fill={themeColors.badgeBg} fillOpacity="0.2" stroke={themeColors.badgeBg} strokeOpacity="0.4" />
                    <circle cx="18" cy="16" r="4" fill={themeColors.accent1} />
                    <text x="32" y="21" fill={themeColors.badgeText} fontFamily="system-ui, -apple-system, sans-serif" fontSize="11" fontWeight="bold" letterSpacing="0.08em">
                      STRATEGIC BRIEFING · LINKEDIN
                    </text>

                    <rect x="264" y="0" width="180" height="32" rx="6" fill="#1e293b" fillOpacity="0.6" stroke="#334155" strokeWidth="1" />
                    <text x="278" y="21" fill="#94a3b8" fontFamily="system-ui, -apple-system, sans-serif" fontSize="11" fontWeight="600">
                      Target: {deliverable.targetAudience.slice(0, 16)}
                    </text>

                    <rect x="456" y="0" width="160" height="32" rx="6" fill="#1e293b" fillOpacity="0.6" stroke="#334155" strokeWidth="1" />
                    <text x="470" y="21" fill="#a855f7" fontFamily="ui-monospace, monospace" fontSize="11" fontWeight="bold">
                      {currentRatio.dimensions} px
                    </text>
                  </g>

                  {/* Key Message Hook */}
                  <g transform={`translate(50, ${exportRatio === '1:1' ? 116 : 136})`}>
                    <text x="0" y="38" fill="#ffffff" fontFamily="system-ui, -apple-system, sans-serif" fontSize={exportRatio === '4:5' ? '34' : '30'} fontWeight="800" letterSpacing="-0.02em">
                      {deliverable.hook.length > 52 ? deliverable.hook.slice(0, 52) : deliverable.hook}
                    </text>
                    {deliverable.hook.length > 52 && (
                      <text x="0" y="80" fill="#e2e8f0" fontFamily="system-ui, -apple-system, sans-serif" fontSize={exportRatio === '4:5' ? '28' : '26'} fontWeight="700">
                        {deliverable.hook.length > 105 ? deliverable.hook.slice(52, 105) + '...' : deliverable.hook.slice(52)}
                      </text>
                    )}
                    <line x1="0" y1="104" x2="980" y2="104" stroke="#334155" strokeWidth="1.2" opacity="0.6" />
                  </g>

                  {/* 3 Stacked Pillars for Vertical Space */}
                  <g transform="translate(50, 0)">
                    {/* Pillar 1 */}
                    <g transform={`translate(0, ${exportRatio === '1:1' ? 250 : 285})`}>
                      <rect width="980" height={exportRatio === '1:1' ? '150' : '190'} rx="12" fill="#0f172a" fillOpacity="0.75" stroke="#1e293b" strokeWidth="1.2" />
                      <rect x="0" y="0" width="4" height={exportRatio === '1:1' ? '150' : '190'} fill={themeColors.accent1} rx="2" />
                      <circle cx="34" cy="38" r="14" fill={themeColors.accent1} fillOpacity="0.2" />
                      <text x="34" y="43" fill={themeColors.accent1} fontFamily="system-ui, sans-serif" fontSize="13" fontWeight="bold" textAnchor="middle">1</text>
                      <text x="62" y="43" fill="#f8fafc" fontFamily="system-ui, sans-serif" fontSize="16" fontWeight="700">
                        Core Thesis &amp; Context
                      </text>
                      <text x="34" y="82" fill="#cbd5e1" fontFamily="system-ui, sans-serif" fontSize="14">
                        {deliverable.body.slice(0, 78)}
                      </text>
                      <text x="34" y="108" fill="#94a3b8" fontFamily="system-ui, sans-serif" fontSize="13">
                        {deliverable.body.slice(78, 156)}...
                      </text>
                      <text x="34" y={exportRatio === '1:1' ? '134' : '160'} fill={themeColors.accent1} fontFamily="ui-monospace, monospace" fontSize="11" fontWeight="600">
                        HIGH IMPACT SIGNAL · VERIFIED INSIGHT
                      </text>
                    </g>

                    {/* Pillar 2 */}
                    <g transform={`translate(0, ${exportRatio === '1:1' ? 425 : 505})`}>
                      <rect width="980" height={exportRatio === '1:1' ? '150' : '190'} rx="12" fill="#0f172a" fillOpacity="0.75" stroke="#1e293b" strokeWidth="1.2" />
                      <rect x="0" y="0" width="4" height={exportRatio === '1:1' ? '150' : '190'} fill={themeColors.accent2} rx="2" />
                      <circle cx="34" cy="38" r="14" fill={themeColors.accent2} fillOpacity="0.2" />
                      <text x="34" y="43" fill={themeColors.accent2} fontFamily="system-ui, sans-serif" fontSize="13" fontWeight="bold" textAnchor="middle">2</text>
                      <text x="62" y="43" fill="#f8fafc" fontFamily="system-ui, sans-serif" fontSize="16" fontWeight="700">
                        Strategic Implication &amp; Impact
                      </text>
                      <text x="34" y="82" fill="#cbd5e1" fontFamily="system-ui, sans-serif" fontSize="14">
                        {deliverable.body.slice(156, 234)}
                      </text>
                      <text x="34" y="108" fill="#94a3b8" fontFamily="system-ui, sans-serif" fontSize="13">
                        {deliverable.body.slice(234, 312)}...
                      </text>
                      <text x="34" y={exportRatio === '1:1' ? '134' : '160'} fill={themeColors.accent2} fontFamily="ui-monospace, monospace" fontSize="11" fontWeight="600">
                        OPERATIONAL READINESS · EXECUTIVE ALIGNMENT
                      </text>
                    </g>

                    {/* Pillar 3 */}
                    <g transform={`translate(0, ${exportRatio === '1:1' ? 600 : 725})`}>
                      <rect width="980" height={exportRatio === '1:1' ? '150' : '190'} rx="12" fill="#0f172a" fillOpacity="0.75" stroke="#1e293b" strokeWidth="1.2" />
                      <rect x="0" y="0" width="4" height={exportRatio === '1:1' ? '150' : '190'} fill="#ec4899" rx="2" />
                      <circle cx="34" cy="38" r="14" fill="#ec4899" fillOpacity="0.2" />
                      <text x="34" y="43" fill="#ec4899" fontFamily="system-ui, sans-serif" fontSize="13" fontWeight="bold" textAnchor="middle">3</text>
                      <text x="62" y="43" fill="#f8fafc" fontFamily="system-ui, sans-serif" fontSize="16" fontWeight="700">
                        Enterprise Execution Directive
                      </text>
                      <text x="34" y="82" fill="#cbd5e1" fontFamily="system-ui, sans-serif" fontSize="14">
                        👉 {deliverable.callToAction}
                      </text>
                      <text x="34" y="108" fill="#94a3b8" fontFamily="system-ui, sans-serif" fontSize="13">
                        Action framework structured for executive team implementation.
                      </text>
                      <text x="34" y={exportRatio === '1:1' ? '134' : '160'} fill="#ec4899" fontFamily="ui-monospace, monospace" fontSize="11" fontWeight="600">
                        EXECUTIVE DIRECTIVE · NEXT STEPS
                      </text>
                    </g>
                  </g>

                  {/* Bottom Footer Bar */}
                  <g transform={`translate(50, ${exportRatio === '1:1' ? 780 : 965})`}>
                    <rect width="980" height={exportRatio === '1:1' ? '82' : '96'} rx="10" fill="url(#liAccentGrad)" opacity="0.92" />
                    <text x="30" y={exportRatio === '1:1' ? '48' : '56'} fill="#ffffff" fontFamily="system-ui, -apple-system, sans-serif" fontSize="17" fontWeight="bold">
                      👉 {deliverable.callToAction.length > 58 ? deliverable.callToAction.slice(0, 58) + '...' : deliverable.callToAction}
                    </text>
                    <text x="950" y={exportRatio === '1:1' ? '48' : '56'} fill="#ffffff" opacity="0.85" fontFamily="ui-monospace, monospace" fontSize="11" fontWeight="600" textAnchor="end">
                      GEN-TRANSFORM ENGINE
                    </text>
                  </g>

                  {/* Watermarks */}
                  <text x="50" y={exportRatio === '1:1' ? 900 : 1105} fill="#64748b" fontFamily="system-ui, sans-serif" fontSize="11">
                    Generated from verified source intelligence • Formatted for LinkedIn {currentRatio.useCase}
                  </text>
                  <text x="1030" y={exportRatio === '1:1' ? 900 : 1105} fill="#64748b" fontFamily="ui-monospace, monospace" fontSize="11" textAnchor="end">
                    {currentRatio.dimensions} • {currentRatio.label}
                  </text>
                </>
              ) : (
                /* HORIZONTAL LAYOUT (1.91:1 Landscape & 16:9 Widescreen) */
                <>
                  {/* Header Badges */}
                  <g transform="translate(60, 50)">
                    <rect width="250" height="32" rx="6" fill={themeColors.badgeBg} fillOpacity="0.2" stroke={themeColors.badgeBg} strokeOpacity="0.4" />
                    <circle cx="18" cy="16" r="4" fill={themeColors.accent1} />
                    <text x="32" y="21" fill={themeColors.badgeText} fontFamily="system-ui, -apple-system, sans-serif" fontSize="11" fontWeight="bold" letterSpacing="0.08em">
                      STRATEGIC BRIEFING · LINKEDIN
                    </text>

                    <rect x="264" y="0" width="170" height="32" rx="6" fill="#1e293b" fillOpacity="0.6" stroke="#334155" strokeWidth="1" />
                    <text x="278" y="21" fill="#94a3b8" fontFamily="system-ui, -apple-system, sans-serif" fontSize="11" fontWeight="600">
                      Target: {deliverable.targetAudience.slice(0, 15)}
                    </text>

                    <rect x="446" y="0" width="160" height="32" rx="6" fill="#1e293b" fillOpacity="0.6" stroke="#334155" strokeWidth="1" />
                    <text x="460" y="21" fill="#a855f7" fontFamily="ui-monospace, monospace" fontSize="11" fontWeight="bold">
                      {currentRatio.dimensions} px
                    </text>
                  </g>

                  {/* Key Message Hook */}
                  <g transform="translate(60, 130)">
                    <text x="0" y="38" fill="#ffffff" fontFamily="system-ui, -apple-system, sans-serif" fontSize="32" fontWeight="800" letterSpacing="-0.02em">
                      {deliverable.hook.length > 58 ? deliverable.hook.slice(0, 58) : deliverable.hook}
                    </text>
                    {deliverable.hook.length > 58 && (
                      <text x="0" y="80" fill="#e2e8f0" fontFamily="system-ui, -apple-system, sans-serif" fontSize="28" fontWeight="700" letterSpacing="-0.01em">
                        {deliverable.hook.length > 118 ? deliverable.hook.slice(58, 118) + '...' : deliverable.hook.slice(58)}
                      </text>
                    )}
                    <line x1="0" y1="108" x2="1080" y2="108" stroke="#334155" strokeWidth="1.2" opacity="0.6" />
                  </g>

                  {/* 3 Executive Pillars / Takeaways */}
                  <g transform="translate(60, 266)">
                    {/* Pillar 1 */}
                    <g transform="translate(0, 0)">
                      <rect width="340" height={exportRatio === '16:9' ? '200' : '180'} rx="12" fill="#0f172a" fillOpacity="0.7" stroke="#1e293b" strokeWidth="1.2" />
                      <rect x="0" y="0" width="340" height="3" fill={themeColors.accent1} rx="1.5" />
                      <circle cx="28" cy="34" r="12" fill={themeColors.accent1} fillOpacity="0.2" />
                      <text x="28" y="38" fill={themeColors.accent1} fontFamily="system-ui, sans-serif" fontSize="12" fontWeight="bold" textAnchor="middle">1</text>
                      <text x="52" y="38" fill="#f8fafc" fontFamily="system-ui, sans-serif" fontSize="15" fontWeight="700">
                        Core Thesis &amp; Context
                      </text>
                      <text x="24" y="76" fill="#cbd5e1" fontFamily="system-ui, sans-serif" fontSize="13">
                        {deliverable.body.slice(0, 42)}
                      </text>
                      <text x="24" y="100" fill="#94a3b8" fontFamily="system-ui, sans-serif" fontSize="12">
                        {deliverable.body.slice(42, 84)}...
                      </text>
                      <text x="24" y={exportRatio === '16:9' ? '160' : '145'} fill={themeColors.accent1} fontFamily="ui-monospace, monospace" fontSize="11" fontWeight="600">
                        HIGH IMPACT SIGNAL
                      </text>
                    </g>

                    {/* Pillar 2 */}
                    <g transform="translate(370, 0)">
                      <rect width="340" height={exportRatio === '16:9' ? '200' : '180'} rx="12" fill="#0f172a" fillOpacity="0.7" stroke="#1e293b" strokeWidth="1.2" />
                      <rect x="0" y="0" width="340" height="3" fill={themeColors.accent2} rx="1.5" />
                      <circle cx="28" cy="34" r="12" fill={themeColors.accent2} fillOpacity="0.2" />
                      <text x="28" y="38" fill={themeColors.accent2} fontFamily="system-ui, sans-serif" fontSize="12" fontWeight="bold" textAnchor="middle">2</text>
                      <text x="52" y="38" fill="#f8fafc" fontFamily="system-ui, sans-serif" fontSize="15" fontWeight="700">
                        Actionable Implication
                      </text>
                      <text x="24" y="76" fill="#cbd5e1" fontFamily="system-ui, sans-serif" fontSize="13">
                        {deliverable.body.slice(84, 126)}
                      </text>
                      <text x="24" y="100" fill="#94a3b8" fontFamily="system-ui, sans-serif" fontSize="12">
                        {deliverable.body.slice(126, 168)}...
                      </text>
                      <text x="24" y={exportRatio === '16:9' ? '160' : '145'} fill={themeColors.accent2} fontFamily="ui-monospace, monospace" fontSize="11" fontWeight="600">
                        STRATEGIC ALIGNMENT
                      </text>
                    </g>

                    {/* Pillar 3 */}
                    <g transform="translate(740, 0)">
                      <rect width="340" height={exportRatio === '16:9' ? '200' : '180'} rx="12" fill="#0f172a" fillOpacity="0.7" stroke="#1e293b" strokeWidth="1.2" />
                      <rect x="0" y="0" width="340" height="3" fill="#ec4899" rx="1.5" />
                      <circle cx="28" cy="34" r="12" fill="#ec4899" fillOpacity="0.2" />
                      <text x="28" y="38" fill="#ec4899" fontFamily="system-ui, sans-serif" fontSize="12" fontWeight="bold" textAnchor="middle">3</text>
                      <text x="52" y="38" fill="#f8fafc" fontFamily="system-ui, sans-serif" fontSize="15" fontWeight="700">
                        Enterprise Next Step
                      </text>
                      <text x="24" y="76" fill="#cbd5e1" fontFamily="system-ui, sans-serif" fontSize="13">
                        👉 {deliverable.callToAction.slice(0, 36)}
                      </text>
                      <text x="24" y="100" fill="#94a3b8" fontFamily="system-ui, sans-serif" fontSize="12">
                        {deliverable.callToAction.slice(36, 76)}...
                      </text>
                      <text x="24" y={exportRatio === '16:9' ? '160' : '145'} fill="#ec4899" fontFamily="ui-monospace, monospace" fontSize="11" fontWeight="600">
                        EXECUTIVE DIRECTIVE
                      </text>
                    </g>
                  </g>

                  {/* Bottom Footer Bar */}
                  <g transform={`translate(60, ${exportRatio === '16:9' ? 515 : 485})`}>
                    <rect width="1080" height="78" rx="10" fill="url(#liAccentGrad)" opacity="0.92" />
                    <text x="32" y="46" fill="#ffffff" fontFamily="system-ui, -apple-system, sans-serif" fontSize="17" fontWeight="bold">
                      👉 {deliverable.callToAction.length > 70 ? deliverable.callToAction.slice(0, 70) + '...' : deliverable.callToAction}
                    </text>
                    <text x="1048" y="46" fill="#ffffff" opacity="0.85" fontFamily="ui-monospace, monospace" fontSize="11" fontWeight="600" textAnchor="end">
                      GEN-TRANSFORM MULTI-AGENT ENGINE
                    </text>
                  </g>

                  {/* Watermark Tag */}
                  <text x="60" y={exportRatio === '16:9' ? 635 : 596} fill="#64748b" fontFamily="system-ui, sans-serif" fontSize="11">
                    Generated from verified source intelligence • Formatted for LinkedIn Enterprise Feed
                  </text>
                  <text x="1140" y={exportRatio === '16:9' ? 635 : 596} fill="#64748b" fontFamily="ui-monospace, monospace" fontSize="11" textAnchor="end">
                    {currentRatio.dimensions} • {currentRatio.label}
                  </text>
                </>
              )}
            </svg>
          </div>
        </div>
      )}

      {/* Matplotlib visual result */}
      {visualUrl && (
        <div className="pt-2 border-t border-slate-800/80 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 text-xs text-slate-400">
            <span className="font-semibold uppercase tracking-wider text-purple-400 flex items-center gap-1.5">
              <ImageIcon className="w-3.5 h-3.5" />
              <span>Matplotlib Visual Graphic</span>
            </span>
            <span className="font-mono text-[10px] text-slate-400 bg-slate-900/90 px-2 py-0.5 rounded border border-slate-800">
              {currentRatio.dimensions} px · {currentRatio.label} ({currentRatio.useCase})
            </span>
          </div>
          <div className="rounded-xl overflow-hidden border border-purple-500/30 bg-[#070b14] p-2 shadow-2xl">
            <img src={visualUrl} alt="LinkedIn matplotlib visual" className="w-full h-auto rounded-lg block" />
          </div>
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={handleDownloadVisualPng}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download PNG</span>
            </button>
            <button
              onClick={() => { setVisualUrl(null); handleRemoveImage(); }}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-950/60 text-slate-400 hover:text-rose-400 transition-colors cursor-pointer"
              title="Remove Image"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Empty State — generate matplotlib visual on the backend */}
      {!visualUrl && !deliverable.generatedImage && (
        <div className="rounded-xl border border-dashed border-slate-800/90 bg-slate-950/40 p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 shrink-0">
              <ImageIcon className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-200">
                Visual Graphic — Matplotlib Ready
              </p>
              <p className="text-[11px] text-slate-400">
                Executive image ({currentRatio.dimensions} px) renders via matplotlib on the backend — no Forge/GPU needed.
              </p>
            </div>
          </div>

          <button
            onClick={handleGenerateImage}
            disabled={isGeneratingVisual}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-60 text-white text-xs font-semibold transition-all shrink-0 cursor-pointer shadow-sm"
          >
            {isGeneratingVisual ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ImageIcon className="w-3.5 h-3.5" />}
            <span>{isGeneratingVisual ? 'Rendering…' : 'Generate Visual'}</span>
          </button>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* Action Footer */}
      {/* ------------------------------------------------------------- */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setIsEditing(!isEditing)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors cursor-pointer"
          >
            <Edit3 className="w-3.5 h-3.5" />
            <span>{isEditing ? 'Editing' : 'Edit Post'}</span>
          </button>

          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors cursor-pointer"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>

          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download .txt</span>
          </button>

          {/* Matplotlib visual generation (replaces Waiting for Backend) */}
          <button
            onClick={handleGenerateImage}
            disabled={isGeneratingVisual}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer bg-purple-600 hover:bg-purple-500 disabled:opacity-60 text-white"
            title="Render matplotlib PNG on the backend (no Forge needed)"
          >
            {isGeneratingVisual ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ImageIcon className="w-3.5 h-3.5" />}
            <span>{isGeneratingVisual ? 'Rendering…' : visualUrl ? 'Regenerate Visual' : 'Generate Visual'}</span>
          </button>
        </div>

        <button
          onClick={onPublishToMcp}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 transition-all cursor-pointer"
          title="Publish to LinkedIn"
        >
          <Send className="w-3.5 h-3.5" />
          <span>Publish to LinkedIn</span>
        </button>
      </div>
    </div>
  );
};
