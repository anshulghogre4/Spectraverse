'use client';

import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  analyzeImage,
  analyzeAudio,
  generateImageToAudio,
  generateImageToAudioFoundry,
  generateAudioToVisual,
  type ImageFeatures,
  type AudioFeatures,
  type GenerationResult,
  type FoundryGenerationResult,
  type VisualGenerationResult,
} from '../lib/api';
import AudioOutputPanel from './AudioOutputPanel';
import VisualOutputPanel from './VisualOutputPanel';
import GenerationProgress from './GenerationProgress';
import FoundryReasoningPanel from './FoundryReasoningPanel';

type Props = {
  type: 'image' | 'audio';
  mode: 'classic' | 'creative';
  style: string;
};

type Phase = 'idle' | 'analysing' | 'analysed' | 'generating' | 'done';

export default function UploadZone({ type, mode, style }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [analysisFeatures, setAnalysisFeatures] = useState<ImageFeatures | AudioFeatures | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [genResult, setGenResult] = useState<GenerationResult | null>(null);
  const [visualResult, setVisualResult] = useState<VisualGenerationResult | null>(null);
  const [foundryResult, setFoundryResult] = useState<FoundryGenerationResult | null>(null);
  const [useFoundry, setUseFoundry] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [genDone, setGenDone] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const acceptedTypes =
    type === 'image'
      ? 'image/png,image/jpeg,image/webp'
      : 'audio/mpeg,audio/wav,audio/x-wav,audio/ogg';

  const clear = () => {
    setFile(null);
    setPreview(null);
    setPhase('idle');
    setAnalysisFeatures(null);
    setGenResult(null);
    setVisualResult(null);
    setFoundryResult(null);
    setError(null);
    setShowDetails(false);
    setGenDone(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── File handling ───────────────────────────────────────────────────────
  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = () => setIsDragging(false);
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  };
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) handleFile(e.target.files[0]);
  };
  const handleFile = (f: File) => {
    if (f.size > 10 * 1024 * 1024) { setError('File too large (max 10MB)'); return; }
    setFile(f);
    setError(null);
    setPhase('idle');
    setAnalysisFeatures(null);
    setGenResult(null);
    setVisualResult(null);
    setFoundryResult(null);
    setGenDone(false);
    if (type === 'image') {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target?.result as string);
      reader.readAsDataURL(f);
    } else {
      setPreview('audio');
    }
  };

  // ── Step 1: Analyse ─────────────────────────────────────────────────────
  const handleAnalyse = async () => {
    if (!file) return;
    setPhase('analysing');
    setError(null);
    try {
      const res = type === 'image' ? await analyzeImage(file) : await analyzeAudio(file);
      if (res.status !== 'analysis_complete') {
        setError(res.message || 'Analysis unavailable — check backend dependencies');
        setPhase('idle');
        return;
      }
      setAnalysisFeatures(res.features as ImageFeatures | AudioFeatures);
      setPhase('analysed');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed — is the backend running?');
      setPhase('idle');
    }
  };

  // ── Step 2: Generate ────────────────────────────────────────────────────
  const handleGenerate = async () => {
    if (!file) return;
    setPhase('generating');
    setGenDone(false);
    setError(null);
    try {
      if (type === 'image') {
        if (useFoundry) {
          const res = await generateImageToAudioFoundry(file, mode, style, 15);
          setGenDone(true);
          setFoundryResult(res);
          setGenResult(res); // FoundryGenerationResult extends GenerationResult
        } else {
          const res = await generateImageToAudio(file, mode, style, 15);
          setGenDone(true);
          setGenResult(res);
        }
      } else {
        const res = await generateAudioToVisual(file, mode, style);
        setGenDone(true);
        setVisualResult(res);
      }
      setPhase('done');
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Generation failed — is the backend running?';
      setError(msg);
      setPhase('analysed'); // fall back so user can retry
      setGenDone(false);
    }
  };

  // ── Colour accents ──────────────────────────────────────────────────────
  const accentBorder = type === 'image' ? 'hover:border-blue-400' : 'hover:border-purple-400';
  const accentBg = type === 'image' ? 'border-blue-400 bg-blue-500/10' : 'border-purple-400 bg-purple-500/10';
  const analyseBtn = type === 'image'
    ? 'bg-gray-700 hover:bg-gray-600 text-gray-200'
    : 'bg-gray-700 hover:bg-gray-600 text-gray-200';
  const generateBtn = type === 'image'
    ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20'
    : 'bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-500/20';

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="space-y-3">

      {/* Drop zone — always visible until done */}
      {phase !== 'done' && (
        <motion.div
          className={`border-2 border-dashed rounded-xl p-6 transition-colors min-h-[160px] flex items-center justify-center ${
            isDragging ? accentBg
            : file ? 'border-green-600/50 bg-green-500/5'
            : `border-gray-600 ${accentBorder}`
          } ${!file ? 'cursor-pointer' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !file && fileInputRef.current?.click()}
          whileHover={!file ? { scale: 1.01 } : {}}
        >
          <input ref={fileInputRef} type="file" hidden accept={acceptedTypes} onChange={handleFileInput} />

          {file ? (
            <div className="text-center w-full">
              {type === 'image' && preview ? (
                <img src={preview} alt="preview" className="w-20 h-20 mx-auto rounded-lg object-cover mb-2" />
              ) : (
                <div className="text-4xl mb-2">🎵</div>
              )}
              <p className="font-semibold text-sm text-gray-200 truncate max-w-xs mx-auto">{file.name}</p>
              <p className="text-xs text-gray-500 mt-1">{(file.size / 1024).toFixed(0)} KB</p>
              {phase === 'idle' && (
                <button
                  onClick={(e) => { e.stopPropagation(); clear(); }}
                  className="mt-1.5 text-xs text-gray-600 hover:text-red-400 transition underline"
                >
                  Remove
                </button>
              )}
            </div>
          ) : (
            <div className="text-center">
              <p className="text-4xl mb-2">{type === 'image' ? '📸' : '🎵'}</p>
              <p className="text-base font-semibold text-gray-200">
                {type === 'image' ? 'Drag image here' : 'Drag audio here'}
              </p>
              <p className="text-sm text-gray-500 mt-1">or click to browse</p>
              <p className="text-xs text-gray-600 mt-2">
                {type === 'image' ? 'PNG, JPEG, WEBP' : 'MP3, WAV, OGG'} · Max 10MB
              </p>
            </div>
          )}
        </motion.div>
      )}

      {/* Step 1: Analyse button */}
      <AnimatePresence>
        {file && phase === 'idle' && (
          <motion.button
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            onClick={handleAnalyse}
            className={`w-full py-3 rounded-xl font-semibold transition flex items-center justify-center gap-2 ${analyseBtn}`}
          >
            {type === 'image' ? '🔍 Analyse Image' : '🔍 Analyse Audio'}
          </motion.button>
        )}

        {/* Analysing spinner */}
        {phase === 'analysing' && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="w-full py-3 rounded-xl bg-gray-800/60 flex items-center justify-center gap-2 text-gray-400 text-sm"
          >
            <Spinner /> Analysing…
          </motion.div>
        )}
      </AnimatePresence>

      {/* Analysis results (collapsible after generation) */}
      <AnimatePresence>
        {analysisFeatures && (phase === 'analysed' || phase === 'generating' || phase === 'done') && (
          <motion.div
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            className="bg-gray-900/50 border border-gray-700/60 rounded-xl overflow-hidden"
          >
            <button
              onClick={() => setShowDetails(v => !v)}
              className="w-full flex items-center justify-between px-4 py-2.5 text-xs text-gray-400 hover:text-gray-200 transition"
            >
              <span className="text-green-400 font-semibold uppercase tracking-widest">✓ Analysis complete</span>
              <span>{showDetails ? '▲ Hide' : '▼ Details'}</span>
            </button>
            <AnimatePresence>
              {showDetails && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="grid grid-cols-2 gap-1.5 px-4 pb-4">
                    {Object.entries(analysisFeatures).map(([k, v]) => (
                      <FeatureTile key={k} label={k} value={v} />
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Step 2: Generate button */}
      <AnimatePresence>
        {phase === 'analysed' && (
          <motion.div
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="space-y-2"
          >
            {/* Foundry IQ toggle — only show for image upload */}
            {type === 'image' && (
              <button
                onClick={() => setUseFoundry(v => !v)}
                className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg border text-xs transition ${
                  useFoundry
                    ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                    : 'bg-gray-800/40 border-gray-700/60 text-gray-400 hover:text-gray-300'
                }`}
              >
                <span className="flex items-center gap-2">
                  <span>🧠</span>
                  <span className="font-semibold">
                    Foundry IQ {useFoundry ? '· ON' : '· OFF'}
                  </span>
                  <span className="opacity-70 hidden sm:inline">
                    {useFoundry ? 'AI reasoning + cited music theory' : 'enable for cited reasoning'}
                  </span>
                </span>
                <span className={`w-8 h-4 rounded-full relative transition-colors ${
                  useFoundry ? 'bg-emerald-500' : 'bg-gray-600'
                }`}>
                  <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${
                    useFoundry ? 'left-4' : 'left-0.5'
                  }`} />
                </span>
              </button>
            )}

            <button
              onClick={handleGenerate}
              className={`w-full py-3 rounded-xl font-semibold transition flex items-center justify-center gap-2 ${generateBtn}`}
            >
              {type === 'image' ? (useFoundry ? '🧠 Generate with Foundry IQ' : '🎶 Generate Audio') : '✨ Generate Visual'}
              {mode === 'creative' && style && (
                <span className="text-xs opacity-70">({style})</span>
              )}
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Generation progress */}
      <AnimatePresence>
        {phase === 'generating' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <GenerationProgress type={type} done={genDone} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="bg-red-900/30 border border-red-500/40 rounded-lg p-3 text-sm text-red-300"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results */}
      {phase === 'done' && foundryResult && (
        <FoundryReasoningPanel
          description={foundryResult.image_description}
          citations={foundryResult.citations}
          reasoningSteps={foundryResult.reasoning_steps}
          isFullyLive={foundryResult.is_fully_live}
          isMock={foundryResult.is_mock}
        />
      )}
      {phase === 'done' && genResult && (
        <AudioOutputPanel result={genResult} onReset={clear} />
      )}
      {phase === 'done' && visualResult && (
        <VisualOutputPanel result={visualResult} onReset={clear} />
      )}
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────────

function FeatureTile({ label, value }: { label: string; value: unknown }) {
  let display: string;
  if (value !== null && typeof value === 'object') {
    display = Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => {
        const n = Number(v);
        return `${k}:${isNaN(n) ? String(v) : Math.round(n)}`;
      })
      .join(' ');
  } else if (typeof value === 'number') {
    display = value > 1 ? String(Math.round(value)) : value.toFixed(4);
  } else {
    display = String(value);
  }
  return (
    <div className="bg-gray-800/60 rounded-lg p-2.5">
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-0.5">{label.replace(/_/g, ' ')}</p>
      <p className="text-xs font-semibold text-gray-100 truncate">{display}</p>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}
