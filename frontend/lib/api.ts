export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

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
  narration?: string;
};

export type VisualGenerationResult = {
  status: string;
  audio_b64?: string;
  visual_config: {
    type?: string;
    render_mode?: string;
    particles?: { count: number; speed: number; size?: number; behavior?: string };
    colors?: { palette: string[]; brightness?: number; darkness?: number; saturation?: number };
    camera?: Record<string, unknown>;
    effects?: { enabled: string[]; intensity: number };
    animation?: { duration: number; loopable: boolean; fps: number };
    audio_sync?: { bpm: number; beat_sensitivity?: number };
  };
  audio_features: Partial<AudioFeatures>;
  visual_params: Record<string, unknown>;
  safety_flags: string[];
  cache_hit: boolean;
  mode: string;
  style: string;
  is_mock?: boolean;
  provider?: string;
  citations?: FoundryCitation[];
  reasoning_steps?: FoundryReasoningStep[];
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
  source_url?: string;
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
  narration?: string;
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

export type AudioToVisualFoundryResult = VisualGenerationResult & {
  image_description: string;
  citations: FoundryCitation[];
  reasoning_steps: FoundryReasoningStep[];
  provider: 'azure' | 'openai' | 'gemini' | 'groq' | 'mock';
  is_mock: boolean;
  is_fully_live: boolean;
};

export async function generateAudioToVisualFoundry(
  file: File,
  mode: string,
  style: string,
): Promise<AudioToVisualFoundryResult> {
  const form = new FormData();
  form.append('file', file);
  const params = new URLSearchParams({ mode, style });
  const res = await fetch(`${API_URL}/api/generate/audio-to-visual-foundry?${params}`, {
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
  preset_used?: string;
  preset_auto_selected?: boolean;
  auto_selected_reason?: string;
  vision_reasoning?: Record<string, unknown>;
  ai_mode_used?: boolean;
};

export type DetectionResult = {
  is_spectrogram: boolean;
  confidence: number;
  type: string;
  colormap_guess: string;
  reason: string;
  method?: string;
};

export async function detectSpectrogram(file: File): Promise<DetectionResult> {
  const form = new FormData();
  form.append('file', file);
  return post('/api/detect-spectrogram', form);
}

export async function invertSpectrogram(
  file: File,
  options: {
    colormap?: string; dbMin?: number; dbMax?: number; nIter?: number; preset?: string;
    rawB64?: string; rawParams?: { sr: number; n_fft: number; hop_length: number; n_mels: number };
    aiMode?: boolean;
  } = {},
): Promise<InversionResult> {
  const { colormap = 'viridis', dbMin = -80, dbMax = 0, nIter = 64, preset = 'librosa_mel', rawB64, rawParams, aiMode = false } = options;
  const form = new FormData();
  form.append('file', file);
  if (rawB64) {
    const rawBlob = new Blob([rawB64], { type: 'application/octet-stream' });
    form.append('raw_data', rawBlob, 'raw_spectrogram.b64');
  }
  const qp: Record<string, string> = {
    colormap,
    db_min: String(dbMin),
    db_max: String(dbMax),
    n_iter: String(nIter),
    preset,
    ai_mode: String(aiMode),
  };
  if (rawParams) {
    qp.raw_sr = String(rawParams.sr);
    qp.raw_n_fft = String(rawParams.n_fft);
    qp.raw_hop_length = String(rawParams.hop_length);
    qp.raw_n_mels = String(rawParams.n_mels);
  }
  const params = new URLSearchParams(qp);
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

export type SpectrogramResult = {
  status: string;
  spectrogram_b64: string;
  spectrogram_raw_b64?: string;
  raw_params?: {
    sr: number;
    n_fft: number;
    hop_length: number;
    n_mels: number;
    shape: number[];
    ref_power: string;
  };
  sample_rate: number;
  duration: number;
  n_mels: number;
  n_fft: number;
  hop_length: number;
  colormap: string;
  frames: number;
};

export async function audioToSpectrogram(
  file: File,
  options: { colormap?: string; nMels?: number; nFft?: number; hopLength?: number } = {},
): Promise<SpectrogramResult> {
  const { colormap = 'viridis', nMels = 128, nFft = 2048, hopLength = 512 } = options;
  const form = new FormData();
  form.append('file', file);
  const params = new URLSearchParams({
    colormap,
    n_mels: String(nMels),
    n_fft: String(nFft),
    hop_length: String(hopLength),
  });
  const res = await fetch(`${API_URL}/api/audio-to-spectrogram?${params}`, {
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
