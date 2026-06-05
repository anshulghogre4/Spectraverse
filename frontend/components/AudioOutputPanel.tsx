'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';
import type { GenerationResult } from '../lib/api';

type Props = {
  result: GenerationResult;
  onReset: () => void;
};

export default function AudioOutputPanel({ result, onReset }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [audioSrc, setAudioSrc] = useState('');

  // Build data URI once — useState so the audio element src attribute actually updates
  useEffect(() => {
    if (result.audio_b64) {
      setAudioSrc(`data:audio/wav;base64,${result.audio_b64}`);
    }
  }, [result.audio_b64]);

  const togglePlay = () => {
    const el = audioRef.current;
    if (!el) return;
    if (playing) {
      el.pause();
    } else {
      el.play().catch(() => {});
    }
  };

  const caption = buildCaption(result);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0 }}
        className="bg-gray-900/70 border border-blue-500/30 rounded-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <div className="flex items-center gap-2">
            <span className="text-blue-400 text-lg">🎶</span>
            <span className="text-sm font-semibold text-blue-300 uppercase tracking-widest">
              Generated Audio
            </span>
            {result.style && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                {result.style}
              </span>
            )}
          </div>
          <button
            onClick={onReset}
            className="text-xs text-gray-500 hover:text-gray-300 transition"
          >
            Try another
          </button>
        </div>

        {/* Spectrogram */}
        {result.spectrogram ? (
          <div className="mx-5 rounded-xl overflow-hidden border border-gray-700/50">
            <img
              src={result.spectrogram}
              alt="Mel spectrogram"
              className="w-full h-32 object-cover"
            />
          </div>
        ) : (
          <div className="mx-5 h-20 rounded-xl bg-gray-800/60 border border-gray-700/50 flex items-center justify-center">
            <span className="text-xs text-gray-600">Spectrogram unavailable</span>
          </div>
        )}

        {/* Audio player */}
        <div className="px-5 py-4 space-y-3">
          {result.audio_b64 ? (
            <div className="space-y-2">
              <audio
                ref={audioRef}
                src={audioSrc}
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                onEnded={() => setPlaying(false)}
                className="hidden"
              />
              <button
                onClick={togglePlay}
                className="w-full py-3 rounded-xl font-semibold flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white transition"
              >
                {playing ? (
                  <><PauseIcon /> Pause</>
                ) : (
                  <><PlayIcon /> Play Generated Audio</>
                )}
              </button>
              {/* Native controls as fallback */}
              <audio
                src={audioSrc}
                controls
                className="w-full h-8 opacity-60 hover:opacity-100 transition"
                style={{ filter: 'invert(1) hue-rotate(180deg)' }}
              />
            </div>
          ) : (
            <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-3 text-sm text-red-400">
              Audio generation failed — no audio returned
            </div>
          )}

          {/* Semantic caption */}
          <p className="text-xs text-gray-400 leading-relaxed bg-gray-800/40 rounded-lg px-3 py-2">
            {caption}
          </p>

          {/* Audio params grid */}
          {result.audio_params && Object.keys(result.audio_params).length > 0 && (
            <details className="group">
              <summary className="text-xs text-gray-600 hover:text-gray-400 cursor-pointer select-none">
                Show parameters
              </summary>
              <div className="mt-2 grid grid-cols-2 gap-1.5">
                {Object.entries(result.audio_params).map(([k, v]) => (
                  <div key={k} className="bg-gray-800/50 rounded-lg px-2.5 py-1.5">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">{k.replace(/_/g, ' ')}</p>
                    <p className="text-xs font-semibold text-gray-200 truncate">
                      {Array.isArray(v) ? v.join(', ') : String(v)}
                    </p>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

function buildCaption(result: GenerationResult): string {
  const p = result.audio_params as Record<string, unknown>;
  const f = result.image_features as Record<string, unknown>;
  if (!p || Object.keys(p).length === 0) return 'Audio synthesised from image analysis.';

  const parts: string[] = [];
  if (f?.brightness) parts.push(`Brightness ${Number(f.brightness).toFixed(2)}`);
  if (p.pitch) parts.push(`→ ${p.pitch} Hz`);
  if (p.instruments && Array.isArray(p.instruments)) parts.push(`${(p.instruments as string[]).join(' + ')}`);
  if (p.bpm) parts.push(`at ${p.bpm} BPM`);
  if (p.reverb) parts.push(`reverb ${Number(p.reverb).toFixed(1)}`);
  if (result.style) parts.push(`[${result.style} style]`);
  return parts.length > 0 ? parts.join(' · ') : 'Audio synthesised from image analysis.';
}

function PlayIcon() {
  return (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
    </svg>
  );
}
