import React, { useState } from 'react';
import {
  BarChart3,
  Download,
  Edit3,
  Sparkles,
  CheckCircle2,
  Layers,
  Cpu,
  ShieldAlert,
  Network,
  KeyRound,
  Zap,
  Compass,
  ShieldCheck,
  RefreshCw,
  Palette,
  Loader2,
  Image as ImageIcon
} from 'lucide-react';
import { InfographicDeliverable } from '../../../types';
import { StatusBadge } from '../../common/StatusBadge';
import { imageStudioApi, imageFileUrl } from '../../../api/mediaApi';

interface InfographicCardProps {
  deliverable: InfographicDeliverable;
  onUpdate: (updated: InfographicDeliverable) => void;
  onShowToast: (title: string, message: string, type?: 'success' | 'info' | 'error') => void;
}

export const InfographicCard: React.FC<InfographicCardProps> = ({
  deliverable,
  onUpdate,
  onShowToast
}) => {
  const [layout, setLayout] = useState(deliverable.layoutRecommendation);
  const [style, setStyle] = useState(deliverable.visualStyle);
  const [isGenerating, setIsGenerating] = useState(false);
  const [pngUrl, setPngUrl] = useState<string | null>(null);
  const [pngMeta, setPngMeta] = useState<string | null>(null);

  const layouts: ('Vertical' | 'Horizontal' | 'Timeline' | 'Process' | 'Comparison')[] = [
    'Vertical',
    'Horizontal',
    'Timeline',
    'Process',
    'Comparison'
  ];

  const styles: ('Corporate' | 'Minimal' | 'Editorial' | 'Technology')[] = [
    'Corporate',
    'Minimal',
    'Editorial',
    'Technology'
  ];

  const handleGenerateVisual = async () => {
    if (isGenerating) return;
    setIsGenerating(true);
    try {
      const res = await imageStudioApi.generateInfographic({
        key_message: deliverable.keyMessage,
        key_statistics: (deliverable.keyStatistics || []).map((s) => ({
          value: s.value,
          label: s.label,
          subtext: s.subtext,
        })),
        supporting_points: (deliverable.supportingPoints || []).map((p) => ({
          title: p.title,
          description: p.description,
        })),
        call_to_action: deliverable.callToAction,
        layout,
        visual_style: style,
        width: 1200,
        height: 800,
      });
      const url = imageFileUrl(res.filename);
      setPngUrl(url);
      setPngMeta(`${res.width} × ${res.height} • matplotlib PNG • ${res.generation_time}s`);
      onShowToast('Infographic Rendered', `Matplotlib PNG ready (${res.width}×${res.height} in ${res.generation_time}s). No Forge/GPU needed.`, 'success');
    } catch (err: any) {
      const msg = err?.message || 'Backend unreachable. Start backend on :8000 (python -m uvicorn app.main:app --port 8000).';
      onShowToast('Render Failed', msg, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownloadPng = async () => {
    if (!pngUrl) return;
    try {
      const resp = await fetch(pngUrl);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Infographic_${layout}_${style}_${Date.now()}.png`;
      a.click();
      URL.revokeObjectURL(url);
      onShowToast('Downloaded', 'Matplotlib infographic exported as PNG.', 'success');
    } catch {
      window.open(pngUrl, '_blank');
    }
  };

  const handleDownloadSvg = () => {
    // Generate clean SVG download
    const svgData = `
      <svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
        <rect width="800" height="600" fill="#0b0f17" rx="16"/>
        <text x="40" y="60" fill="#ffffff" font-family="system-ui" font-size="22" font-weight="bold">${deliverable.keyMessage}</text>
        <line x1="40" y1="85" x2="760" y2="85" stroke="#334155" stroke-width="1"/>
        <g transform="translate(40, 110)">
          ${deliverable.keyStatistics.map((s, idx) => `
            <g transform="translate(${idx * 180}, 0)">
              <rect width="165" height="100" fill="#131b2e" rx="10" stroke="#334155"/>
              <text x="16" y="45" fill="#a855f7" font-family="monospace" font-size="26" font-weight="bold">${s.value}</text>
              <text x="16" y="70" fill="#e2e8f0" font-family="system-ui" font-size="12" font-weight="600">${s.label}</text>
              <text x="16" y="86" fill="#94a3b8" font-family="system-ui" font-size="10">${s.subtext}</text>
            </g>
          `).join('')}
        </g>
        <g transform="translate(40, 240)">
          ${deliverable.supportingPoints.map((p, idx) => `
            <g transform="translate(${(idx % 2) * 370}, ${Math.floor(idx / 2) * 110})">
              <rect width="350" height="90" fill="#131b2e" rx="10" stroke="#1e293b"/>
              <text x="16" y="32" fill="#38bdf8" font-family="system-ui" font-size="14" font-weight="bold">${p.title}</text>
              <text x="16" y="55" fill="#cbd5e1" font-family="system-ui" font-size="11">${p.description}</text>
            </g>
          `).join('')}
        </g>
        <rect x="40" y="500" width="720" height="50" fill="#7e22ce" rx="8"/>
        <text x="400" y="532" fill="#ffffff" font-family="system-ui" font-size="13" font-weight="bold" text-anchor="middle">${deliverable.callToAction}</text>
      </svg>
    `;
    const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Infographic_${Date.now()}.svg`;
    a.click();
    URL.revokeObjectURL(url);
    onShowToast('Downloaded', 'Infographic exported as scalable vector graphics (.svg)', 'success');
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0d121f] p-6 space-y-6 shadow-xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-white">Infographic Workspace</h3>
              <StatusBadge status="ready" size="xs" />
            </div>
            <p className="text-xs text-slate-400">Key visual layout, prominent statistics, and structured hierarchy</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleGenerateVisual}
            disabled={isGenerating}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-60 text-white text-xs font-semibold transition-all cursor-pointer shadow-md shadow-purple-600/20"
            title="Render matplotlib PNG on the backend (no Forge/GPU needed)"
          >
            {isGenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            <span>{isGenerating ? 'Rendering…' : pngUrl ? 'Regenerate PNG' : 'Generate PNG'}</span>
          </button>
        </div>
      </div>

      {/* Matplotlib PNG result — replaces the old "Waiting for Backend" placeholder */}
      {pngUrl && (
        <div className="rounded-xl overflow-hidden border border-purple-500/30 bg-[#070b14] shadow-2xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-4 py-2.5 border-b border-slate-800 bg-slate-900/60">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-purple-300 flex items-center gap-1.5">
              <ImageIcon className="w-3.5 h-3.5" />
              <span>Matplotlib Rendered Infographic</span>
            </span>
            <span className="font-mono text-[10px] text-slate-400">{pngMeta}</span>
          </div>
          <img src={pngUrl} alt="Matplotlib infographic" className="w-full h-auto block" />
          <div className="flex items-center justify-end gap-2 px-4 py-2.5 border-t border-slate-800">
            <button
              onClick={handleDownloadPng}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download PNG</span>
            </button>
          </div>
        </div>
      )}

      {/* Two Column Layout: Left side Visual Preview, Right side Content & Settings */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Side: Generated Infographic Canvas Preview */}
        <div className="lg:col-span-7 rounded-xl bg-[#090d16] border border-slate-800 p-6 space-y-6 relative overflow-hidden shadow-2xl">
          {/* Subtle grid background */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b15_1px,transparent_1px),linear-gradient(to_bottom,#1e293b15_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none" />

          {/* Infographic Title Bar */}
          <div className="relative z-10 border-b border-slate-800/80 pb-4">
            <span className="text-[10px] uppercase font-bold text-amber-400 tracking-wider">
              {style} INFOGRAPHIC BRIEF · {layout.toUpperCase()}
            </span>
            <h2 className="text-base sm:text-lg font-bold text-white mt-1 leading-snug">
              {deliverable.keyMessage}
            </h2>
          </div>

          {/* Key Statistics Grid */}
          <div className="relative z-10 grid grid-cols-2 gap-3">
            {deliverable.keyStatistics.map((stat, i) => (
              <div
                key={i}
                className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800/90 flex flex-col justify-between"
              >
                <div className="text-2xl sm:text-3xl font-bold font-mono text-purple-400 tracking-tight">
                  {stat.value}
                </div>
                <div className="mt-1.5">
                  <div className="text-xs font-semibold text-slate-200">{stat.label}</div>
                  <div className="text-[11px] text-slate-400">{stat.subtext}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Supporting Visual Points */}
          <div className="relative z-10 space-y-2.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
              Core Observations
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {deliverable.supportingPoints.map((pt, i) => (
                <div
                  key={i}
                  className="p-3 rounded-lg bg-slate-900/60 border border-slate-800/80 text-xs space-y-1"
                >
                  <div className="font-semibold text-white flex items-center gap-1.5 text-xs">
                    <span className="w-2 h-2 rounded-full bg-cyan-400" />
                    <span>{pt.title}</span>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed">
                    {pt.description}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Infographic Call to Action Banner */}
          <div className="relative z-10 p-3.5 rounded-xl bg-gradient-to-r from-purple-900/60 to-indigo-900/60 border border-purple-500/30 text-center">
            <span className="text-xs font-bold text-purple-200 tracking-wide">
              {deliverable.callToAction}
            </span>
          </div>
        </div>

        {/* Right Side: Infographic Controls & Content Structure */}
        <div className="lg:col-span-5 space-y-5 text-xs">
          {/* Layout Recommendation */}
          <div className="space-y-2">
            <label className="font-semibold text-slate-300 block">Layout Recommendation</label>
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-1.5">
              {layouts.map((l) => (
                <button
                  key={l}
                  onClick={() => {
                    setLayout(l);
                    onUpdate({ ...deliverable, layoutRecommendation: l });
                  }}
                  className={`py-1.5 px-2 rounded-lg font-medium border text-center transition-colors cursor-pointer ${
                    layout === l
                      ? 'bg-amber-500/20 border-amber-500 text-amber-300'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>

          {/* Visual Style */}
          <div className="space-y-2">
            <label className="font-semibold text-slate-300 block">Visual Style</label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              {styles.map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    setStyle(s);
                    onUpdate({ ...deliverable, visualStyle: s });
                  }}
                  className={`py-1.5 px-2 rounded-lg font-medium border text-center transition-colors cursor-pointer ${
                    style === s
                      ? 'bg-purple-600/20 border-purple-500 text-purple-300'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Infographic Content Breakdown */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
            <span className="font-semibold text-white uppercase tracking-wider text-[11px] block">
              Infographic Blueprint Data
            </span>

            <div>
              <span className="text-slate-400 font-medium">Key Headline:</span>
              <p className="text-slate-200 mt-0.5">{deliverable.keyMessage}</p>
            </div>

            <div>
              <span className="text-slate-400 font-medium">Primary Metrics Extracted:</span>
              <ul className="mt-1 space-y-1 text-slate-300 list-disc pl-4">
                {deliverable.keyStatistics.map((stat, i) => (
                  <li key={i}>
                    <strong>{stat.value}</strong> — {stat.label} ({stat.subtext})
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Action Export Buttons */}
          <div className="pt-2 flex items-center gap-2">
            <button
              onClick={handleDownloadSvg}
              className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download SVG / Vector</span>
            </button>
          </div>

          {/* Rendered SVG Vector Image directly below the button */}
          <div className="pt-3 border-t border-slate-800/80 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span className="font-semibold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
                <Palette className="w-3.5 h-3.5" />
                <span>Rendered SVG Vector Image</span>
              </span>
              <span className="font-mono text-[10px] text-slate-500">800 × 540 • Scalable Vector</span>
            </div>

            <div className="rounded-xl overflow-hidden border border-slate-800 bg-[#070b14] p-2 hover:border-slate-700 transition-colors shadow-2xl">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 800 540"
                className="w-full h-auto rounded-lg shadow-inner select-none block"
              >
                <defs>
                  <linearGradient id="infographicHeaderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#f59e0b" />
                    <stop offset="100%" stopColor="#d97706" />
                  </linearGradient>
                  <linearGradient id="infographicCardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#111827" />
                    <stop offset="100%" stopColor="#0b1120" />
                  </linearGradient>
                  <linearGradient id="infographicAccentGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#7e22ce" />
                    <stop offset="50%" stopColor="#6366f1" />
                    <stop offset="100%" stopColor="#2563eb" />
                  </linearGradient>
                  <pattern id="infographicGrid" width="24" height="24" patternUnits="userSpaceOnUse">
                    <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#334155" strokeWidth="0.5" opacity="0.25" />
                  </pattern>
                </defs>

                {/* Base Surface */}
                <rect width="800" height="540" fill="#080d1a" rx="16" />
                <rect width="800" height="540" fill="url(#infographicGrid)" rx="16" />
                <rect width="800" height="540" fill="none" stroke="#1e293b" strokeWidth="1.5" rx="16" />

                {/* Header Badge */}
                <rect x="36" y="26" width="190" height="22" rx="4" fill="#f59e0b" fillOpacity="0.15" stroke="#f59e0b" strokeOpacity="0.35" />
                <text x="44" y="41" fill="#fbbf24" fontFamily="system-ui, -apple-system, sans-serif" fontSize="10" fontWeight="bold" letterSpacing="0.08em">
                  {style.toUpperCase()} INFOGRAPHIC · {layout.toUpperCase()}
                </text>

                {/* Key Message Title */}
                <text x="36" y="78" fill="#ffffff" fontFamily="system-ui, -apple-system, sans-serif" fontSize="18" fontWeight="bold">
                  {deliverable.keyMessage.length > 56 ? deliverable.keyMessage.slice(0, 56) + '...' : deliverable.keyMessage}
                </text>
                <line x1="36" y1="96" x2="764" y2="96" stroke="#334155" strokeWidth="1" opacity="0.6" />

                {/* 4 Metric Statistic Cards */}
                <g transform="translate(36, 112)">
                  {deliverable.keyStatistics.slice(0, 4).map((s, idx) => {
                    const colW = 172;
                    const xOffset = idx * 182;
                    return (
                      <g key={idx} transform={`translate(${xOffset}, 0)`}>
                        <rect width={colW} height="88" fill="url(#infographicCardGrad)" rx="10" stroke="#334155" strokeWidth="1" />
                        <rect x="0" y="0" width={colW} height="3" fill="#a855f7" rx="1.5" />
                        <text x="14" y="36" fill="#c084fc" fontFamily="ui-monospace, monospace" fontSize="22" fontWeight="bold">
                          {s.value}
                        </text>
                        <text x="14" y="57" fill="#f8fafc" fontFamily="system-ui, -apple-system, sans-serif" fontSize="11" fontWeight="600">
                          {s.label.length > 18 ? s.label.slice(0, 18) + '...' : s.label}
                        </text>
                        <text x="14" y="74" fill="#94a3b8" fontFamily="system-ui, -apple-system, sans-serif" fontSize="9.5">
                          {s.subtext.length > 22 ? s.subtext.slice(0, 22) + '...' : s.subtext}
                        </text>
                      </g>
                    );
                  })}
                </g>

                {/* Supporting Points / Key Insights */}
                <g transform="translate(36, 218)">
                  <text x="0" y="16" fill="#94a3b8" fontFamily="system-ui, -apple-system, sans-serif" fontSize="11" fontWeight="bold" letterSpacing="0.06em">
                    CORE OBSERVATIONS &amp; RISK VECTORS
                  </text>
                  {deliverable.supportingPoints.slice(0, 4).map((p, idx) => {
                    const rowX = (idx % 2) * 374;
                    const rowY = 28 + Math.floor(idx / 2) * 88;
                    return (
                      <g key={idx} transform={`translate(${rowX}, ${rowY})`}>
                        <rect width="354" height="74" fill="url(#infographicCardGrad)" rx="10" stroke="#1e293b" strokeWidth="1" />
                        <circle cx="20" cy="22" r="3.5" fill="#38bdf8" />
                        <text x="32" y="26" fill="#38bdf8" fontFamily="system-ui, -apple-system, sans-serif" fontSize="11.5" fontWeight="bold">
                          {p.title.length > 36 ? p.title.slice(0, 36) + '...' : p.title}
                        </text>
                        <text x="20" y="47" fill="#cbd5e1" fontFamily="system-ui, -apple-system, sans-serif" fontSize="10">
                          {p.description.length > 50 ? p.description.slice(0, 50) + '...' : p.description}
                        </text>
                        {p.description.length > 50 && (
                          <text x="20" y="62" fill="#94a3b8" fontFamily="system-ui, -apple-system, sans-serif" fontSize="9.5">
                            {p.description.slice(50, 104)}
                          </text>
                        )}
                      </g>
                    );
                  })}
                </g>

                {/* Call to Action Banner */}
                <g transform="translate(36, 464)">
                  <rect width="728" height="46" fill="url(#infographicAccentGrad)" rx="8" />
                  <text x="364" y="28" fill="#ffffff" fontFamily="system-ui, -apple-system, sans-serif" fontSize="12" fontWeight="bold" textAnchor="middle" letterSpacing="0.02em">
                    👉 {deliverable.callToAction}
                  </text>
                </g>
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
