'use client';

import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { detectSpectrogram, invertSpectrogram, type InversionResult } from '../lib/api';
import InversionOutputPanel from './InversionOutputPanel';
import GenerationProgress from './GenerationProgress';

type Phase = 'idle' | 'detecting' | 'detected' | 'inverting' | 'done';

const COLORMAP_OPTIONS = ['viridis', 'magma', 'plasma', 'inferno', 'hot', 'jet'];

const PRESET_OPTIONS = [
  { id: 'librosa_mel',       label: 'librosa mel',        hint: 'sr 22050 · 128 mel · most matplotlib spectrograms' },
  { id: 'chrome_music_lab',  label: 'Chrome Music Lab',   hint: 'sr 44100 · log-linear · 20Hz–20kHz, FFT 2048' },
  { id: 'wikipedia_speech',  label: 'Speech / Wikipedia', hint: 'sr 16000 · linear FFT 1024 · narrow band speech' },
];

export default function SpectrogramUploadZone() {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [detection, setDetection] = useState<{ confidence: number; colormap_guess: string; type: string } | null>(null);
  const [colormap, setColormap] = useState('viridis');
  const [preset, setPreset] = useState('librosa_mel');
  const [nIter, setNIter] = useState(64);
  const [result, setResult] = useState<InversionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [genDone, setGenDone] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const clear = () => {
    setFile(null);
    setPreview(null);
    setPhase('idle');
    setDetection(null);
    setResult(null);
    setError(null);
    setGenDone(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

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
    setDetection(null);
    setResult(null);
    setGenDone(false);
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target?.result as string);
    reader.readAsDataURL(f);
  };

  // Step 1: detect
  const handleDetect = async () => {
    if (!file) return;
    setPhase('detecting');
    setError(null);
    try {
      const res = await detectSpectrogram(file);
      setDetection({ confidence: res.confidence, colormap_guess: res.colormap_guess, type: res.type });
      // Auto-set colormap from detection
      if (res.colormap_guess && COLORMAP_OPTIONS.includes(res.colormap_guess)) {
        setColormap(res.colormap_guess);
      }
      setPhase('detected');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Detection failed — is the backend running?');
      setPhase('idle');
    }
  };

  // Step 2: invert
  const handleInvert = async () => {
    if (!file) return;
    setPhase('inverting');
    setGenDone(false);
    setError(null);
    try {
      const res = await invertSpectrogram(file, { colormap, nIter, preset });
      setGenDone(true);
      setResult(res);
      setPhase('done');
    } catch (e) {
      const raw = e instanceof Error ? e.message : 'Inversion failed';
      // Parse FastAPI detail from JSON if present
      let msg = raw;
      try { msg = JSON.parse(raw).detail ?? raw; } catch {}
      setError(msg);
      setPhase('detected');
      setGenDone(false);
    }
  };

  const confColor =
    detection?.confidence == null ? 'text-gray-500' :
    detection.confidence >= 0.7 ? 'text-green-400' :
    detection.confidence >= 0.4 ? 'text-yellow-400' :
    'text-red-400';

  return (
    <div className="space-y-3">

      {/* Drop zone */}
      {phase !== 'done' && (
        <motion.div
          className={`border-2 border-dashed rounded-xl p-6 transition-colors min-h-[160px] flex items-center justify-center ${
            isDragging ? 'border-teal-400 bg-teal-500/10'
            : file ? 'border-green-600/50 bg-green-500/5'
            : 'border-gray-600 hover:border-teal-400'
          } ${!file ? 'cursor-pointer' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !file && fileInputRef.current?.click()}
          whileHover={!file ? { scale: 1.01 } : {}}
        >
          <input ref={fileInputRef} type="file" hidden accept="image/png,image/jpeg,image/webp" onChange={handleFileInput} />

          {file ? (
            <div className="text-center w-full">
              {preview && (
                <img src={preview} alt="preview" className="w-full max-h-36 mx-auto rounded-lg object-contain mb-2" />
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
              <p className="text-4xl mb-2">🔬</p>
              <p className="text-base font-semibold text-gray-200">Drag spectrogram here</p>
              <p className="text-sm text-gray-500 mt-1">or click to browse</p>
              <p className="text-xs text-gray-600 mt-2">PNG, JPEG, WEBP · Max 10MB</p>
              <p className="text-xs text-gray-700 mt-1">
                Upload any mel/STFT spectrogram screenshot
              </p>
            </div>
          )}
        </motion.div>
      )}

      {/* Step 1: Detect button */}
      <AnimatePresence>
        {file && phase === 'idle' && (
          <motion.button
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            onClick={handleDetect}
            className="w-full py-3 rounded-xl font-semibold transition flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 text-gray-200"
          >
            🔍 Detect Spectrogram Type
          </motion.button>
        )}
        {phase === 'detecting' && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="w-full py-3 rounded-xl bg-gray-800/60 flex items-center justify-center gap-2 text-gray-400 text-sm"
          >
            <Spinner /> Analysing…
          </motion.div>
        )}
      </AnimatePresence>

      {/* Detection result + settings */}
      <AnimatePresence>
        {detection && (phase === 'detected' || phase === 'inverting' || phase === 'done') && (
          <motion.div
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            className="bg-gray-900/50 border border-gray-700/60 rounded-xl px-4 py-3 space-y-3"
          >
            {/* Detection summary */}
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`text-sm font-semibold ${confColor}`}>
                {detection.confidence >= 0.45 ? '✓ Spectrogram detected' : '⚠ May not be a spectrogram'}
              </span>
              <span className="text-xs text-gray-500">
                {(detection.confidence * 100).toFixed(0)}% confidence · {detection.type} · guess: {detection.colormap_guess}
              </span>
            </div>

            {/* Preset picker — drives sr / FFT / scale */}
            <div>
              <label className="text-xs text-gray-500 block mb-1">Source preset</label>
              <div className="grid grid-cols-3 gap-1">
                {PRESET_OPTIONS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setPreset(p.id)}
                    title={p.hint}
                    className={`px-2 py-1.5 rounded-lg text-xs font-semibold transition border ${
                      preset === p.id
                        ? 'bg-teal-500/20 border-teal-500/50 text-teal-300'
                        : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600 hover:text-gray-300'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-gray-600 mt-1 truncate">
                {PRESET_OPTIONS.find((p) => p.id === preset)?.hint}
              </p>
            </div>

            {/* Settings row */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Colour map</label>
                <select
                  value={colormap}
                  onChange={(e) => setColormap(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-teal-500"
                >
                  {COLORMAP_OPTIONS.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">
                  Quality ({nIter} iterations)
                </label>
                <input
                  type="range" min={16} max={128} step={16}
                  value={nIter}
                  onChange={(e) => setNIter(Number(e.target.value))}
                  className="w-full accent-teal-500"
                />
                <div className="flex justify-between text-xs text-gray-600 mt-0.5">
                  <span>Fast</span><span>Best</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Step 2: Invert button */}
      <AnimatePresence>
        {phase === 'detected' && (
          <motion.button
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            onClick={handleInvert}
            className="w-full py-3 rounded-xl font-semibold transition flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-500 text-white shadow-lg shadow-teal-500/20"
          >
            🔊 Reconstruct Audio
          </motion.button>
        )}
      </AnimatePresence>

      {/* Progress */}
      <AnimatePresence>
        {phase === 'inverting' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <GenerationProgress type="image" done={genDone} />
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

      {/* Result */}
      {phase === 'done' && result && preview && (
        <InversionOutputPanel originalImageSrc={preview} result={result} onReset={clear} />
      )}
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
