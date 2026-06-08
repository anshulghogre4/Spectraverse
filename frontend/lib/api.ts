const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type ImageFeatures = {
  brightness: number;
  avg_color?: { r: number; g: number; b: number };
  color_temperature: 'warm' | 'cool' | 'neutral';
  texture_density?: string;
  texture_edge_density?: number;
  scene_type: string;
  mood?: string;
  dominant_colors?: number[][];
  has_objects?: boolean;
  composition?: string;
};

export type AudioFeatures = {
  bpm: number;
  bass_energy: number;
  treble_energy: number;
  spectral_centroid: number;
  pitch?: { hz: number; note: string };
  mfcc?: number[];
  genre?: string;
  vibe?: string;
  complexity?: number;
};

export type AnalysisResult<T = ImageFeatures | AudioFeatures> = {
  status: string;
  filename: string;
  features: Partial<T>;
  message: string;
};

export type GenerationResult = {
  status: string;
  audio_b64: string;
  sample_rate: number;
  duration: number;
  spectrogram: string;
  image_features: Partial<ImageFeatures>;
  audio_params: Record<string, unknown>;
  safety_flags: string[];
  cache_hit: boolean;
  mode: string;
  style: string;
};

export type VisualGenerationResult = {
  status: string;
  visual_config: {
    type: string;
    particles: { count: number; speed: number; size: number; behavior: string };
    colors: { palette: string[]; brightness: number; darkness: number; saturation: number };
    camera?: Record<string, unknown>;
    effects?: { enabled: string[]; intensity: number };
    animation: { duration: number; loopable: boolean; fps: number };
    audio_sync?: { bpm: number; beat_sensitivity: number };
  };
  audio_features: Partial<AudioFeatures>;
  visual_params: Record<string, unknown>;
  safety_flags: string[];
  cache_hit: boolean;
  mode: string;
  style: string;
};

async function post<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: 'POST', body: form });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text);
  }
  return res.json();
}

export async function analyzeImage(file: File): Promise<AnalysisResult<ImageFeatures>> {
  const form = new FormData();
  form.append('file', file);
  return post('/api/analyze-image', form);
}

export async function analyzeAudio(file: File): Promise<AnalysisResult<AudioFeatures>> {
  const form = new FormData();
  form.append('file', file);
  return post('/api/analyze-audio', form);
}

export async function generateImageToAudio(
  file: File,
  mode: string,
  style: string,
  duration = 15,
): Promise<GenerationResult> {
  const form = new FormData();
  form.append('file', file);
  const params = new URLSearchParams({ mode, style, duration: String(duration) });
  const res = await fetch(`${API_URL}/api/generate/image-to-audio?${params}`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text);
  }
  return res.json();
}

// ── Sprint 3: Foundry IQ–powered generation ────────────────────────────────

export type FoundryCitation = {
  ref_id: string;
  doc_key: string;
  title: string;
  content_snippet: string;
};

export type FoundryReasoningStep = {
  stage: 'vision' | 'retrieval' | 'mapping';
  description: string;
  duration_ms?: number;
  tokens_used?: number;
  is_mock?: boolean;
};

export type FoundryGenerationResult = GenerationResult & {
  image_description: string;
  citations: FoundryCitation[];
  reasoning_steps: FoundryReasoningStep[];
  provider: 'azure' | 'openai' | 'gemini' | 'groq' | 'mock';
  providers_available: {
    azure: boolean;
    openai: boolean;
    gemini: boolean;
    groq: boolean;
  };
  is_fully_live: boolean;
  is_mock: boolean;
};

export async function generateImageToAudioFoundry(
  file: File,
  mode: string,
  style: string,
  duration = 15,
): Promise<FoundryGenerationResult> {
  const form = new FormData();
  form.append('file', file);
  const params = new URLSearchParams({ mode, style, duration: String(duration) });
  const res = await fetch(`${API_URL}/api/generate/image-to-audio-foundry?${params}`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text);
  }
  return res.json();
}

export async function generateAudioToVisual(
  file: File,
  mode: string,
  style: string,
): Promise<VisualGenerationResult> {
  const form = new FormData();
  form.append('file', file);
  const params = new URLSearchParams({ mode, style });
  const res = await fetch(`${API_URL}/api/generate/audio-to-visual?${params}`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text);
  }
  return res.json();
}

export type InversionResult = {
  status: string;
  audio_b64: string;
  sample_rate: number;
  duration: number;
  reconstruction_method: string;
  n_iter_used: number;
  colormap_used: string;
  spectrogram_type: string;
  confidence: number;
  comparison_spectrogram: string;
};

export type DetectionResult = {
  is_spectrogram: boolean;
  confidence: number;
  type: string;
  colormap_guess: string;
  reason: string;
};

export async function detectSpectrogram(file: File): Promise<DetectionResult> {
  const form = new FormData();
  form.append('file', file);
  return post('/api/detect-spectrogram', form);
}

export async function invertSpectrogram(
  file: File,
  options: { colormap?: string; dbMin?: number; dbMax?: number; nIter?: number; preset?: string } = {},
): Promise<InversionResult> {
  const { colormap = 'viridis', dbMin = -80, dbMax = 0, nIter = 64, preset = 'librosa_mel' } = options;
  const form = new FormData();
  form.append('file', file);
  const params = new URLSearchParams({
    colormap,
    db_min: String(dbMin),
    db_max: String(dbMax),
    n_iter: String(nIter),
    preset,
  });
  const res = await fetch(`${API_URL}/api/invert-spectrogram?${params}`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text);
  }
  return res.json();
}

export async function healthCheck(): Promise<{
  status: string;
  version: string;
  service: string;
  semantic_mappings_loaded: boolean;
  capabilities: Record<string, boolean>;
}> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error('Backend unreachable');
  return res.json();
}
