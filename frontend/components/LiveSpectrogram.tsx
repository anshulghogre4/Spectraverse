'use client';

import { useEffect, useRef, useState } from 'react';

type Props = {
  analyserRef: React.RefObject<AnalyserNode | null>;
  isActive: boolean;
  height?: number;
};

// 256-entry viridis LUT (pre-computed for 0-255 input)
const VIRIDIS_LUT: Uint8Array = (() => {
  const lut = new Uint8Array(256 * 3);
  for (let i = 0; i < 256; i++) {
    const t = i / 255;
    const t2 = t * t;
    const t3 = t2 * t;
    lut[i * 3]     = Math.round(255 * Math.max(0, Math.min(1, 0.267 + 0.004 * t + 2.56 * t2 - 1.89 * t3)));
    lut[i * 3 + 1] = Math.round(255 * Math.max(0, Math.min(1, -0.005 + 0.979 * t + 0.372 * t2 - 1.35 * t3)));
    lut[i * 3 + 2] = Math.round(255 * Math.max(0, Math.min(1, 0.329 + 1.42 * t - 4.28 * t2 + 3.67 * t3)));
  }
  return lut;
})();

const AXIS_LABELS = [
  { freq: 0, label: '0 Hz' },
  { freq: 500, label: '500' },
  { freq: 1000, label: '1k' },
  { freq: 2000, label: '2k' },
  { freq: 4000, label: '4k' },
  { freq: 8000, label: '8k' },
  { freq: 12000, label: '12k' },
  { freq: 16000, label: '16k' },
  { freq: 20000, label: '20k' },
];

export default function LiveSpectrogram({ analyserRef, isActive, height = 200 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const [expanded, setExpanded] = useState(false);

  const activeHeight = expanded ? window.innerHeight - 60 : height;

  useEffect(() => {
    if (!isActive) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;

    const GUTTER = 44;

    const setup = () => {
      const w = canvas.parentElement?.clientWidth ?? canvas.clientWidth ?? 300;
      const h = activeHeight;
      canvas.width = w;
      canvas.height = h;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(0, 0, w, h);
      drawAxisLabels(ctx, h, GUTTER);
    };

    setup();
    window.addEventListener('resize', setup);

    const tick = () => {
      const analyser = analyserRef.current;
      const h = canvas.height;
      if (!analyser) {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }

      const bins = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(bins);

      const w = canvas.width;
      const spectroW = w - GUTTER;

      if (spectroW > 1) {
        const imgData = ctx.getImageData(GUTTER + 1, 0, spectroW - 1, h);
        ctx.putImageData(imgData, GUTTER, 0);
      }

      const colData = ctx.createImageData(1, h);
      const pixels = colData.data;
      const numBins = bins.length;

      for (let y = 0; y < h; y++) {
        const binIndex = Math.floor(((h - 1 - y) / h) * numBins);
        const val = bins[binIndex];
        const off = y * 4;
        pixels[off]     = VIRIDIS_LUT[val * 3];
        pixels[off + 1] = VIRIDIS_LUT[val * 3 + 1];
        pixels[off + 2] = VIRIDIS_LUT[val * 3 + 2];
        pixels[off + 3] = 255;
      }
      ctx.putImageData(colData, w - 1, 0);

      // Time cursor
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(w - 0.5, 0);
      ctx.lineTo(w - 0.5, h);
      ctx.stroke();

      // Horizontal grid lines at frequency labels
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.08)';
      const nyquist = 22050;
      for (const { freq } of AXIS_LABELS) {
        if (freq === 0) continue;
        const gy = h - 1 - (freq / nyquist) * h;
        if (gy >= 2 && gy <= h - 2) {
          ctx.beginPath();
          ctx.moveTo(GUTTER, Math.round(gy) + 0.5);
          ctx.lineTo(w, Math.round(gy) + 0.5);
          ctx.stroke();
        }
      }

      // Redraw gutter
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(0, 0, GUTTER, h);
      drawAxisLabels(ctx, h, GUTTER);

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', setup);
    };
  }, [isActive, analyserRef, activeHeight]);

  // ESC key to exit fullscreen
  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExpanded(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [expanded]);

  if (!isActive) {
    return (
      <div
        className="w-full rounded-lg border border-purple-500/20 bg-slate-900/80 flex items-center justify-center"
        style={{ height }}
      >
        <span className="text-xs text-gray-500">Play audio to see live spectrogram</span>
      </div>
    );
  }

  const wrapperClass = expanded
    ? 'fixed inset-0 z-50 bg-slate-950 flex flex-col'
    : 'w-full relative';

  return (
    <div className={wrapperClass}>
      {/* Toolbar */}
      <div className={`flex items-center justify-between px-3 py-1.5 ${expanded ? 'bg-slate-900/90 border-b border-purple-500/20' : ''}`}>
        <span className="text-[10px] text-purple-400 font-mono tracking-wider uppercase">
          Live Spectrogram
        </span>
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-[10px] px-2 py-0.5 rounded border border-purple-500/30 text-purple-300 hover:bg-purple-500/20 transition"
          title={expanded ? 'Exit fullscreen (Esc)' : 'Fullscreen'}
        >
          {expanded ? '✕ Close' : '⛶ Expand'}
        </button>
      </div>
      <canvas
        ref={canvasRef}
        className={`w-full rounded-lg border border-purple-500/20 ${expanded ? 'flex-1 rounded-none border-0' : ''}`}
        style={expanded ? { background: '#0f172a' } : { height, background: '#0f172a' }}
      />
    </div>
  );
}

function drawAxisLabels(ctx: CanvasRenderingContext2D, h: number, gutter: number) {
  ctx.fillStyle = '#94a3b8';
  ctx.font = '10px monospace';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';

  const nyquist = 22050;
  for (const { freq, label } of AXIS_LABELS) {
    const y = h - 1 - (freq / nyquist) * h;
    if (y >= 6 && y <= h - 6) {
      ctx.fillText(label, gutter - 5, y);
      ctx.fillStyle = '#475569';
      ctx.fillRect(gutter - 3, y, 3, 1);
      ctx.fillStyle = '#94a3b8';
    }
  }
}
