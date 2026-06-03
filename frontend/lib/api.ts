const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type ImageFeatures = {
  brightness: number;
  avg_color: { r: number; g: number; b: number };
  color_temperature: 'warm' | 'cool';
  texture_edge_density: number;
  scene_type: string;
};

export type AudioFeatures = {
  bpm: number;
  bass_energy: number;
  treble_energy: number;
  spectral_centroid: number;
};

export type AnalysisResult<T = ImageFeatures | AudioFeatures> = {
  status: string;
  filename: string;
  features: T;
  message: string;
};

export async function analyzeImage(file: File): Promise<AnalysisResult<ImageFeatures>> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_URL}/api/analyze-image`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function analyzeAudio(file: File): Promise<AnalysisResult<AudioFeatures>> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_URL}/api/analyze-audio`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function healthCheck(): Promise<{ status: string; version: string; semantic_mappings_loaded: boolean }> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error('Backend unreachable');
  return res.json();
}
