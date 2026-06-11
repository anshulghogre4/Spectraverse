'use client';

import { useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { detectSpectrogram, invertSpectrogram, audioToSpectrogram, type InversionResult, type SpectrogramResult } from '../lib/api';
import FoundryReasoningPanel from './FoundryReasoningPanel';
import { useFileUpload } from '../hooks/useFileUpload';
import { useAudioAnalyser } from '../hooks/useAudioAnalyser';
import DropZone from './DropZone';
import InversionOutputPanel from './InversionOutputPanel';
import GenerationProgress from './GenerationProgress';
import StatusPill from './StatusPill';
import LiveSpectrogram from './LiveSpectrogram';

type Phase = 'idle' | 'detecting' | 'detected' | 'inverting' | 'done';
type GenPhase = 'idle' | 'generating' | 'done';
type TabMode = 'invert' | 'generate';

const COLORMAP_OPTIONS = ['viridis', 'magma', 'plasma', 'inferno', 'hot', 'jet'];

const PRESET_OPTIONS = [
  { id: 'librosa_mel',       label: 'librosa mel',        hint: 'sr 22050 · 128 mel · most matplotlib spectrograms' },
  { id: 'chrome_music_lab',  label: 'Chrome Music Lab',   hint: 'sr 44100 · log-linear · 20Hz–20kHz, FFT 2048' },
  { id: 'wikipedia_speech',  label: 'Speech / narrow-band (demo)', hint: 'sr 16000 · linear FFT 1024 · Griffin-Lim recovers timbre, not words' },
];

export default function SpectrogramUploadZone() {
  const [tab, setTab] = useState<TabMode>('generate');

  return (
    <div className="space-y-4">
      {/* Tab toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => setTab('generate')}
          className={`flex-1 py-2 rounded-lg text-sm font-semibold transition ${
            tab === 'generate'
              ? 'bg-teal-500/20 border border-teal-500/50 text-teal-300'
              : 'bg-gray-800/50 border border-gray-700 text-gray-400 hover:text-gray-300'
          }`}
        >
          🎵 Audio → Spectrogram
        </button>
        <button
          onClick={() => setTab('invert')}
          className={`flex-1 py-2 rounded-lg text-sm font-semibold transition ${
            tab === 'invert'
              ? 'bg-teal-500/20 border border-teal-500/50 text-teal-300'
              : 'bg-gray-800/50 border border-gray-700 text-gray-400 hover:text-gray-300'
          }`}
        >
          🔬 Spectrogram → Audio
        </button>
      </div>

      {tab === 'invert' ? <InvertTab /> : <GenerateTab />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
//   Invert Tab (existing spectrogram → audio flow)
// ═══════════════════════════════════════════════════════════════════

function InvertTab() {
  const upload = useFileUpload({
    maxSizeMB: 10,
    accept: ['image/png', 'image/jpeg', 'image/webp'],
    generatePreview: true,
  });

  const [phase, setPhase] = useState<Phase>('idle');
  const [detection, setDetection] = useState<{ confidence: number; colormap_guess: string; type: string; method: string } | null>(null);
  const [colormap, setColormap] = useState('viridis');
  const [preset, setPreset] = useState('librosa_mel');
  const [nIter, setNIter] = useState(64);
  const [useAI, setUseAI] = useState(true);
  const [result, setResult] = useState<InversionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [genDone, setGenDone] = useState(false);

  const clear = () => {
    upload.clear();
    setPhase('idle');
    setDetection(null);
    setResult(null);
    setError(null);
    setGenDone(false);
    setUseAI(true);
  };

  const handleDetect = async () => {
    if (!upload.file) return;
    setPhase('detecting');
    setError(null);
    try {
      const res = await detectSpectrogram(upload.file);
      setDetection({ confidence: res.confidence, colormap_guess: res.colormap_guess, type: res.type, method: res.method || 'heuristic' });
      if (res.colormap_guess && COLORMAP_OPTIONS.includes(res.colormap_guess)) {
        setColormap(res.colormap_guess);
      }
      setPhase('detected');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Detection failed — is the backend running?');
      setPhase('idle');
    }
  };

  const handleInvert = async () => {
    if (!upload.file) return;
    setPhase('inverting');
    setGenDone(false);
    setError(null);
    try {
      const res = await invertSpectrogram(upload.file, { colormap, nIter, preset, aiMode: useAI });
      setGenDone(true);
      setResult(res);
      setPhase('done');
    } catch (e) {
      const raw = e instanceof Error ? e.message : 'Inversion failed';
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
      {phase !== 'done' && (
        <DropZone
          isDragging={upload.isDragging}
          file={upload.file}
          preview={upload.preview}
          type="spectrogram"
          accept="image/png,image/jpeg,image/webp"
          fileInputRef={upload.fileInputRef}
          onDragOver={upload.handleDragOver}
          onDragLeave={upload.handleDragLeave}
          onDrop={upload.handleDrop}
          onFileInput={upload.handleFileInput}
          onClear={clear}
          showRemove={phase === 'idle'}
        />
      )}

      <AnimatePresence>
        {upload.file && phase === 'idle' && (
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

      <AnimatePresence>
        {detection && (phase === 'detected' || phase === 'inverting' || phase === 'done') && (
          <motion.div
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            className="bg-gray-900/50 border border-gray-700/60 rounded-xl px-4 py-3 space-y-3"
          >
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`text-sm font-semibold ${confColor}`}>
                {detection.confidence >= 0.45 ? '✓ Spectrogram detected' : '⚠ May not be a spectrogram'}
              </span>
              <span className="text-xs text-gray-500">
                {(detection.confidence * 100).toFixed(0)}% confidence · {detection.type} · guess: {detection.colormap_guess}
              </span>
              <StatusPill mode={useAI ? 'live' : 'heuristic'} provider={useAI ? 'Foundry IQ' : undefined} />
            </div>

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
              {preset === 'wikipedia_speech' && (
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2 text-xs text-amber-300 mt-2">
                  Griffin-Lim recovers timbre and spectral shape, not intelligible words. This preset works best with the Wikipedia spectrogram-of-speech example.
                </div>
              )}
            </div>

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

      <AnimatePresence>
        {phase === 'detected' && (
          <motion.div
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="space-y-2"
          >
            {/* AI assist toggle */}
            <button
              onClick={() => setUseAI(v => !v)}
              className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg border text-xs transition ${
                useAI
                  ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                  : 'bg-gray-800/40 border-gray-700/60 text-gray-400 hover:text-gray-300'
              }`}
            >
              <span className="flex items-center gap-2">
                <span>{useAI ? '🧠' : '⚙️'}</span>
                <span className="font-semibold">
                  {useAI ? 'AI Vision · ON' : 'Heuristic · ON'}
                </span>
                <span className="opacity-70 hidden sm:inline">
                  {useAI ? 'GPT-4o infers colormap, scale, dB range' : 'Uses detector heuristics only'}
                </span>
              </span>
              <span className={`w-8 h-4 rounded-full relative transition-colors ${useAI ? 'bg-emerald-500' : 'bg-gray-600'}`}>
                <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${useAI ? 'left-4' : 'left-0.5'}`} />
              </span>
            </button>

            <button
              onClick={handleInvert}
              className="w-full py-3 rounded-xl font-semibold transition flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-500 text-white shadow-lg shadow-teal-500/20"
            >
              {useAI ? '🧠 Reconstruct with AI Vision' : '🔊 Reconstruct Audio'}
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {phase === 'inverting' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <GenerationProgress type="image" done={genDone} />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {(error || upload.error) && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="bg-red-900/30 border border-red-500/40 rounded-lg p-3 text-sm text-red-300"
          >
            {error || upload.error}
          </motion.div>
        )}
      </AnimatePresence>

      {phase === 'done' && result && upload.preview && (
        <InversionOutputPanel originalImageSrc={upload.preview} result={result} onReset={clear} showAIReasoning={useAI} />
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
//   Generate Tab (audio → spectrogram image)
// ═══════════════════════════════════════════════════════════════════

function GenerateTab() {
  const upload = useFileUpload({
    maxSizeMB: 10,
    accept: ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/ogg'],
    generatePreview: false,
  });

  const [phase, setPhase] = useState<GenPhase>('idle');
  const [colormap, setColormap] = useState('viridis');
  const [result, setResult] = useState<SpectrogramResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Lossless inversion state
  const [invertPhase, setInvertPhase] = useState<'idle' | 'inverting' | 'done'>('idle');
  const [invertResult, setInvertResult] = useState<InversionResult | null>(null);
  const [invertError, setInvertError] = useState<string | null>(null);

  const clear = () => {
    upload.clear();
    setPhase('idle');
    setResult(null);
    setError(null);
    setInvertPhase('idle');
    setInvertResult(null);
    setInvertError(null);
  };

  const handleGenerate = async () => {
    if (!upload.file) return;
    setPhase('generating');
    setError(null);
    setInvertPhase('idle');
    setInvertResult(null);
    setInvertError(null);
    try {
      const res = await audioToSpectrogram(upload.file, { colormap });
      setResult(res);
      setPhase('done');
    } catch (e) {
      const raw = e instanceof Error ? e.message : 'Generation failed';
      let msg = raw;
      try { msg = JSON.parse(raw).detail ?? raw; } catch {}
      setError(msg);
      setPhase('idle');
    }
  };

  const handleLosslessInvert = async () => {
    if (!result?.spectrogram_raw_b64) return;
    setInvertPhase('inverting');
    setInvertError(null);
    try {
      // Create a small dummy file (the backend requires a file field but will skip it for raw path)
      const dummyBlob = new Blob([new Uint8Array(1)], { type: 'image/png' });
      const dummyFile = new File([dummyBlob], 'raw_inversion.png', { type: 'image/png' });
      const res = await invertSpectrogram(dummyFile, {
        nIter: 100,
        rawB64: result.spectrogram_raw_b64,
        rawParams: result.raw_params ? {
          sr: result.raw_params.sr,
          n_fft: result.raw_params.n_fft,
          hop_length: result.raw_params.hop_length,
          n_mels: result.raw_params.n_mels,
        } : undefined,
      });
      setInvertResult(res);
      setInvertPhase('done');
    } catch (e) {
      const raw = e instanceof Error ? e.message : 'Lossless inversion failed';
      let msg = raw;
      try { msg = JSON.parse(raw).detail ?? raw; } catch {}
      setInvertError(msg);
      setInvertPhase('idle');
    }
  };

  return (
    <div className="space-y-3">
      {phase !== 'done' && (
        <DropZone
          isDragging={upload.isDragging}
          file={upload.file}
          preview={upload.preview}
          type="audio"
          accept="audio/mpeg,audio/wav,audio/x-wav,audio/ogg"
          fileInputRef={upload.fileInputRef}
          onDragOver={upload.handleDragOver}
          onDragLeave={upload.handleDragLeave}
          onDrop={upload.handleDrop}
          onFileInput={upload.handleFileInput}
          onClear={clear}
        />
      )}

      {/* Colormap selector */}
      {upload.file && phase === 'idle' && (
        <div className="bg-gray-900/50 border border-gray-700/60 rounded-xl px-4 py-3">
          <label className="text-xs text-gray-500 block mb-1">Colour map</label>
          <div className="flex gap-2 flex-wrap">
            {COLORMAP_OPTIONS.map((c) => (
              <button
                key={c}
                onClick={() => setColormap(c)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition border ${
                  colormap === c
                    ? 'bg-teal-500/20 border-teal-500/50 text-teal-300'
                    : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>
      )}

      <AnimatePresence>
        {upload.file && phase === 'idle' && (
          <motion.button
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            onClick={handleGenerate}
            className="w-full py-3 rounded-xl font-semibold transition flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-500 text-white shadow-lg shadow-teal-500/20"
          >
            🔬 Generate Spectrogram
          </motion.button>
        )}
        {phase === 'generating' && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="w-full py-3 rounded-xl bg-gray-800/60 flex items-center justify-center gap-2 text-gray-400 text-sm"
          >
            <Spinner /> Generating spectrogram…
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {(error || upload.error) && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="bg-red-900/30 border border-red-500/40 rounded-lg p-3 text-sm text-red-300"
          >
            {error || upload.error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Result */}
      {phase === 'done' && result && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gray-900/70 border border-teal-500/30 rounded-2xl overflow-hidden"
        >
          <div className="flex items-center justify-between px-5 pt-4 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-teal-400 text-lg">🔬</span>
              <span className="text-sm font-semibold text-teal-300 uppercase tracking-widest">
                Generated Spectrogram
              </span>
            </div>
            <button onClick={clear} className="text-xs text-gray-500 hover:text-gray-300 transition">
              Try another
            </button>
          </div>

          <div className="px-5 pb-4 space-y-2">
            <img
              src={`data:image/png;base64,${result.spectrogram_b64}`}
              alt="Generated spectrogram"
              className="w-full rounded-xl border border-teal-500/20"
            />
            <button
              onClick={() => {
                const a = document.createElement('a');
                a.href = `data:image/png;base64,${result.spectrogram_b64}`;
                a.download = `spectrogram-${Date.now()}.png`;
                a.click();
              }}
              className="flex items-center gap-1.5 text-xs text-teal-400 hover:text-teal-300 transition"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5m0 0l5-5m-5 5V3" />
              </svg>
              Download PNG
            </button>
          </div>

          <div className="px-5 pb-4 grid grid-cols-4 gap-2 text-center">
            <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
              <p className="text-xs text-gray-500 uppercase">Duration</p>
              <p className="text-sm font-bold text-gray-100">{result.duration.toFixed(1)}s</p>
            </div>
            <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
              <p className="text-xs text-gray-500 uppercase">Sample Rate</p>
              <p className="text-sm font-bold text-gray-100">{(result.sample_rate / 1000).toFixed(1)}k</p>
            </div>
            <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
              <p className="text-xs text-gray-500 uppercase">Mel Bins</p>
              <p className="text-sm font-bold text-gray-100">{result.n_mels}</p>
            </div>
            <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
              <p className="text-xs text-gray-500 uppercase">Frames</p>
              <p className="text-sm font-bold text-gray-100">{result.frames}</p>
            </div>
          </div>

          {/* Lossless inversion section */}
          {result.spectrogram_raw_b64 && (
            <div className="px-5 pb-4 space-y-3">
              <div className="border-t border-gray-700/50 pt-3">
                {invertPhase === 'idle' && (
                  <button
                    onClick={handleLosslessInvert}
                    className="w-full py-2.5 rounded-xl font-semibold transition flex items-center justify-center gap-2 bg-violet-600 hover:bg-violet-500 text-white shadow-lg shadow-violet-500/20 text-sm"
                  >
                    <span>🔊</span> Invert to Audio (lossless)
                  </button>
                )}
                {invertPhase === 'inverting' && (
                  <div className="w-full py-2.5 rounded-xl bg-gray-800/60 flex items-center justify-center gap-2 text-gray-400 text-sm">
                    <Spinner /> Inverting from raw data (100 iterations)...
                  </div>
                )}
                {invertPhase === 'done' && invertResult && (
                  <LosslessAudioPlayer result={invertResult} />
                )}
                {invertError && (
                  <div className="bg-red-900/30 border border-red-500/40 rounded-lg p-2 text-xs text-red-300">
                    {invertError}
                  </div>
                )}
              </div>
              <p className="text-[10px] text-gray-600 leading-tight">
                Lossless path uses the raw mel spectrogram data (bypasses PNG encoding, cropping, and colormap inversion).
                Much higher quality than re-uploading the PNG image.
              </p>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}

function LosslessAudioPlayer({ result }: { result: InversionResult }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const { analyserRef, isActive } = useAudioAnalyser(audioRef);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-green-400 text-xs font-semibold">Lossless inversion complete</span>
        <span className="text-xs text-gray-500">
          {result.duration.toFixed(1)}s · {result.n_iter_used} iterations · {result.reconstruction_method}
        </span>
      </div>
      <audio
        ref={audioRef}
        controls
        className="w-full h-10 rounded-lg"
        src={`data:audio/wav;base64,${result.audio_b64}`}
      />
      <LiveSpectrogram
        analyserRef={analyserRef}
        isActive={isActive}
        height={100}
      />
      {result.comparison_spectrogram && (
        <details className="text-xs text-gray-500">
          <summary className="cursor-pointer hover:text-gray-300 transition">
            Show reconstruction comparison
          </summary>
          <img
            src={result.comparison_spectrogram}
            alt="Reconstruction comparison"
            className="w-full mt-2 rounded-lg border border-gray-700/50"
          />
        </details>
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
