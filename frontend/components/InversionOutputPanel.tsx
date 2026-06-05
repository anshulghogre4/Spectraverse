'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { InversionResult } from '../lib/api';

type Props = {
  originalImageSrc: string;
  result: InversionResult;
  onReset: () => void;
};

export default function InversionOutputPanel({ originalImageSrc, result, onReset }: Props) {
  const [audioSrc, setAudioSrc] = useState('');
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (result.audio_b64) {
      setAudioSrc(`data:audio/wav;base64,${result.audio_b64}`);
    }
  }, [result.audio_b64]);

  const togglePlay = () => {
    const el = audioRef.current;
    if (!el) return;
    playing ? el.pause() : el.play().catch(() => {});
  };

  const confidenceColor =
    result.confidence >= 0.8 ? 'text-green-400 border-green-500/40' :
    result.confidence >= 0.5 ? 'text-yellow-400 border-yellow-500/40' :
    'text-red-400 border-red-500/40';

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gray-900/70 border border-teal-500/30 rounded-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-4 pb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-teal-400 text-lg">🔬</span>
            <span className="text-sm font-semibold text-teal-300 uppercase tracking-widest">
              Reconstructed Audio
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full border ${confidenceColor} bg-transparent`}>
              {(result.confidence * 100).toFixed(0)}% confidence
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/30">
              {result.spectrogram_type}
            </span>
            <span className="text-xs text-gray-600">
              Griffin-Lim {result.n_iter_used} iter · {result.colormap_used}
            </span>
          </div>
          <button onClick={onReset} className="text-xs text-gray-500 hover:text-gray-300 transition ml-2 flex-shrink-0">
            Try another
          </button>
        </div>

        {/* Before / After spectrograms */}
        <div className="mx-5 grid grid-cols-2 gap-3 mb-3">
          <div className="rounded-xl overflow-hidden border border-gray-700/50">
            <p className="text-xs text-gray-500 px-2 py-1 bg-gray-900/60 border-b border-gray-700/50">
              Original upload
            </p>
            <img src={originalImageSrc} alt="Original spectrogram" className="w-full h-28 object-cover" />
          </div>
          <div className="rounded-xl overflow-hidden border border-teal-700/40">
            <p className="text-xs text-teal-600 px-2 py-1 bg-gray-900/60 border-b border-teal-700/40">
              Re-synthesised
            </p>
            {result.comparison_spectrogram ? (
              <img
                src={result.comparison_spectrogram}
                alt="Re-synthesised spectrogram"
                className="w-full h-28 object-cover"
              />
            ) : (
              <div className="h-28 flex items-center justify-center text-xs text-gray-600">
                Unavailable
              </div>
            )}
          </div>
        </div>

        {/* Audio player */}
        <div className="px-5 pb-4 space-y-2">
          {audioSrc ? (
            <>
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
                className="w-full py-3 rounded-xl font-semibold flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-500 text-white transition"
              >
                {playing ? (
                  <><PauseIcon /> Pause Playback</>
                ) : (
                  <><PlayIcon /> Play Reconstructed Audio</>
                )}
              </button>
              <audio
                src={audioSrc}
                controls
                className="w-full h-8 opacity-60 hover:opacity-100 transition"
                style={{ filter: 'invert(1) hue-rotate(180deg)' }}
              />
              <p className="text-xs text-gray-500 text-center">
                Duration: {result.duration.toFixed(1)}s · {result.sample_rate} Hz ·{' '}
                {result.reconstruction_method.replace(/_/g, '-')}
              </p>
            </>
          ) : (
            <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-3 text-sm text-red-400">
              Audio reconstruction failed — no audio returned
            </div>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

function PlayIcon() {
  return <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>;
}
function PauseIcon() {
  return <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" /></svg>;
}
