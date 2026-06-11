'use client';

import { useEffect, useRef } from 'react';

type Props = {
  analyserRef: React.RefObject<AnalyserNode | null>;
  isActive?: boolean;
};

function viridis(t: number): [number, number, number] {
  t = Math.max(0, Math.min(1, t));
  const r = Math.round(255 * Math.min(1, Math.max(0, -0.8 + 3.2 * t * t)));
  const g = Math.round(255 * Math.min(1, Math.max(0, -0.2 + 1.8 * t - 0.8 * t * t)));
  const b = Math.round(255 * Math.min(1, Math.max(0, 0.4 + 1.2 * t - 2.0 * t * t)));
  return [r, g, b];
}

export default function LiveSpectrogramStrip({ analyserRef, isActive = false }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (!isActive) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const HEIGHT = 40;
    const WIDTH = canvas.offsetWidth || 300;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = WIDTH * dpr;
    canvas.height = HEIGHT * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    const tick = () => {
      const analyser = analyserRef.current;
      if (!analyser) {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }

      const bins = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(bins);

      const imageData = ctx.getImageData(dpr, 0, (WIDTH - 1) * dpr, HEIGHT * dpr);
      ctx.putImageData(imageData, 0, 0);

      const numBins = bins.length;
      for (let y = 0; y < HEIGHT; y++) {
        const binIndex = Math.floor(((HEIGHT - 1 - y) / HEIGHT) * numBins);
        const value = bins[binIndex] / 255;
        const [r, g, b] = viridis(value);
        ctx.fillStyle = `rgb(${r},${g},${b})`;
        ctx.fillRect(WIDTH - 1, y, 1, 1);
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(rafRef.current);
    };
  }, [isActive, analyserRef]);

  if (!isActive) return null;

  return (
    <div className="mx-5 mt-1">
      <canvas
        ref={canvasRef}
        className="w-full rounded-lg border border-purple-500/20 bg-slate-900/50"
        style={{ height: 40 }}
      />
    </div>
  );
}
