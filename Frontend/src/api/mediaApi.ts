import { getApiBaseUrl, workspaceFetch } from './client';

/**
 * Media Studio API — Stable Diffusion Forge image generation + AI video pipeline.
 *
 * Backend modules: Backend/image (image studio), Backend/video (video studio)
 * mounted in Backend/app/main.py under /api/image-studio and /api/media.
 */

// ── Types ────────────────────────────────────────────────────────────────────

export interface GeneratedImageResponse {
  status: string;
  filename: string;
  image_path: string;
  image_url: string;
  generation_time: number;
  device: string;
  steps: number;
  width: number;
  height: number;
  /** True when Forge was offline and a preview placeholder was returned. */
  synthetic: boolean;
  warning?: string | null;
}

export interface SceneImagesResponse {
  status: string;
  images: GeneratedImageResponse[];
  scenes?: Array<{ scene: number; prompt: string }>;
}

export interface PlannedScene {
  scene_number: number;
  duration: number;
  visual_importance: number;
  visual_tier: string;
  narration: string;
  estimated_narration_duration: number;
  max_word_count: number;
  visual_prompt: string;
  on_screen_text: string;
  start_time: number;
  end_time: number;
  transition_type: string;
  transition_duration: number;
  subtitle_start: string;
  subtitle_end: string;
  source_facts: string[];
}

export interface IntelligentVideoPlan {
  title: string;
  target_duration: number;
  total_calculated_duration: number;
  num_scenes: number;
  average_scene_duration: number;
  pacing: string;
  scenes: PlannedScene[];
  timeline: Array<Record<string, unknown>>;
  ffmpeg_sync_metadata: Record<string, unknown>;
}

export interface VideoSceneSummary {
  scene_number: number;
  duration: number;
  visual_importance?: number;
  visual_tier?: string;
  narration: string;
  visual_prompt: string;
  on_screen_text: string;
  start_time?: number;
  end_time?: number;
  transition_type?: string;
  subtitle_start?: string | null;
  subtitle_end?: string | null;
  image_file: string;
  audio_file: string;
}

export interface VideoResponse {
  status: string;
  message: string;
  video_file: string;
  subtitle_file: string;
  scenes: number;
  duration: number;
  video_plan?: IntelligentVideoPlan | null;
  scene_details?: VideoSceneSummary[] | null;
}

export interface VideoRequestPayload {
  text: string;
  target_duration?: number;
  pacing?: 'fast' | 'balanced' | 'cinematic';
  language?: string;
  tone?: string;
  audience?: string;
  voice?: string;
  width?: number;
  height?: number;
  steps?: number;
}

export interface ImageRequestPayload {
  prompt: string;
  negative_prompt?: string;
  mode?: 'fast' | 'balanced' | 'quality';
  width?: number;
  height?: number;
  steps?: number;
  allow_placeholder?: boolean;
}

export interface EnhancePromptPayload {
  text: string;
  style?: string;
  negative_prompt?: string;
  aspect_ratio?: string;
}

export interface EnhancePromptResponse {
  status: string;
  enhanced_prompt: string;
  negative_prompt: string;
  subject: string;
  agent: string;
  llm_used: boolean;
  warning?: string | null;
}

export interface InfographicRenderPayload {
  key_message: string;
  key_statistics: Array<{ value: string; label: string; subtext: string }>;
  supporting_points: Array<{ title: string; description: string }>;
  call_to_action: string;
  layout: string;
  visual_style: string;
  width?: number;
  height?: number;
}

// ── URL helpers ──────────────────────────────────────────────────────────────

export function mediaFileUrl(filename: string): string {
  return `${getApiBaseUrl()}/api/media/video/${encodeURIComponent(filename)}`;
}

export function mediaFileDownloadUrl(filename: string): string {
  return `${getApiBaseUrl()}/api/media/video/${encodeURIComponent(filename)}?download=1`;
}

export function imageFileUrl(filename: string): string {
  return `${getApiBaseUrl()}/api/image-studio/image/${encodeURIComponent(filename)}`;
}

export function imageFileDownloadUrl(filename: string): string {
  return `${getApiBaseUrl()}/api/image-studio/image/${encodeURIComponent(filename)}?download=1`;
}

// ── Image endpoints ──────────────────────────────────────────────────────────

export interface ForgeStatusResponse {
  forge_url: string;
  online: boolean;
  message: string;
  latency_ms?: number;
}

async function fetchWithTimeout<T>(fn: (signal: AbortSignal) => Promise<T>, timeoutMs: number, timeoutMessage: string): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fn(controller.signal);
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error(timeoutMessage);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export const imageStudioApi = {
  getStatus: (): Promise<ForgeStatusResponse> =>
    workspaceFetch('/api/image-studio/status'),

  enhancePrompt: (payload: EnhancePromptPayload): Promise<EnhancePromptResponse> =>
    workspaceFetch('/api/image-studio/enhance-prompt', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  generate: (payload: ImageRequestPayload, timeoutMs = 300_000): Promise<GeneratedImageResponse> =>
    fetchWithTimeout(
      (signal) => workspaceFetch('/api/image-studio/generate-image', {
        method: 'POST',
        body: JSON.stringify(payload),
        signal,
      }),
      timeoutMs,
      'Image generation timed out. Forge may be overloaded — try fewer steps or a smaller resolution.',
    ),

  generateSceneImages: (
    script: string | Record<string, unknown>,
    options: Partial<ImageRequestPayload> = {},
  ): Promise<SceneImagesResponse> =>
    workspaceFetch('/api/image-studio/generate-scene-images', {
      method: 'POST',
      body: JSON.stringify({ script, ...options }),
    }),

  generateSceneImagesFromFile: (file: File): Promise<SceneImagesResponse> => {
    const form = new FormData();
    form.append('file', file);
    return workspaceFetch('/api/image-studio/generate-scene-images-from-file', {
      method: 'POST',
      body: form,
    });
  },

  generateInfographic: (
    payload: InfographicRenderPayload,
    timeoutMs = 60_000,
  ): Promise<GeneratedImageResponse> =>
    fetchWithTimeout(
      (signal) => workspaceFetch('/api/image-studio/generate-infographic', {
        method: 'POST',
        body: JSON.stringify(payload),
        signal,
      }),
      timeoutMs,
      'Infographic rendering timed out. Backend may be busy — try again.',
    ),
};

// ── Video endpoints ──────────────────────────────────────────────────────────

export const videoStudioApi = {
  plan: (payload: {
    text: string;
    target_duration?: number;
    pacing?: string;
    language?: string;
    tone?: string;
    audience?: string;
  }): Promise<IntelligentVideoPlan> =>
    workspaceFetch('/api/media/video/plan', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  generateVideo: (
    payload: VideoRequestPayload,
    timeoutMs = 600_000,
  ): Promise<VideoResponse> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    return workspaceFetch('/api/media/video/generate-video', {
      method: 'POST',
      body: JSON.stringify({
        target_duration: 30,
        pacing: 'balanced',
        language: 'English',
        tone: 'Professional',
        audience: 'General public',
        voice: 'en-US-AriaNeural',
        width: 512,
        height: 512,
        steps: 20,
        ...payload,
      }),
      signal: controller.signal,
    } as RequestInit).finally(() => clearTimeout(timer));
  },
};
