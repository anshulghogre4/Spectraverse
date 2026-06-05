'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { VisualGenerationResult } from '../lib/api';

type Props = {
  result: VisualGenerationResult;
  onReset: () => void;
};

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  alpha: number;
};

const MAX_PARTICLES = 500;

export default function VisualOutputPanel({ result, onReset }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const particlesRef = useRef<Particle[]>([]);
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);

  const cfg = result.visual_config;
  const palette = cfg?.colors?.palette ?? ['#7c3aed', '#2563eb', '#06b6d4'];
  const rawCount = cfg?.particles?.count ?? 200;
  const count = Math.min(rawCount, MAX_PARTICLES);
  const speed = cfg?.particles?.speed ?? 1.0;
  const bpm = cfg?.audio_sync?.bpm ?? 90;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Size canvas to parent
    const resize = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    // Init particles
    particlesRef.current = Array.from({ length: count }, () => makeParticle(canvas, palette, speed));

    const beatInterval = (60 / bpm) * 1000;
    let lastBeat = performance.now();
    let pulseScale = 1;

    const draw = (now: number) => {
      if (!pausedRef.current) {
        // Beat pulse
        if (now - lastBeat > beatInterval) {
          pulseScale = 1.4;
          lastBeat = now;
        }
        pulseScale = pulseScale > 1 ? Math.max(1, pulseScale - 0.02) : 1;

        ctx.fillStyle = 'rgba(3, 7, 18, 0.18)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        for (const p of particlesRef.current) {
          p.x += p.vx * pulseScale;
          p.y += p.vy * pulseScale;

          // Wrap edges
          if (p.x < 0) p.x = canvas.width;
          if (p.x > canvas.width) p.x = 0;
          if (p.y < 0) p.y = canvas.height;
          if (p.y > canvas.height) p.y = 0;

          ctx.beginPath();
          ctx.arc(p.x, p.y, p.radius * pulseScale, 0, Math.PI * 2);
          ctx.fillStyle = hexAlpha(p.color, p.alpha);
          ctx.fill();
        }
      }
      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [count, speed, bpm, palette]);

  const togglePause = () => {
    pausedRef.current = !pausedRef.current;
    setPaused(pausedRef.current);
  };

  const af = result.audio_features as Record<string, unknown>;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0 }}
        className="bg-gray-900/70 border border-purple-500/30 rounded-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-4 pb-3">
          <div className="flex items-center gap-2">
            <span className="text-purple-400 text-lg">✨</span>
            <span className="text-sm font-semibold text-purple-300 uppercase tracking-widest">
              Generated Visual
            </span>
            {result.style && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                {result.style}
              </span>
            )}
          </div>
          <button onClick={onReset} className="text-xs text-gray-500 hover:text-gray-300 transition">
            Try another
          </button>
        </div>

        {/* Canvas */}
        <div className="mx-5 rounded-xl overflow-hidden border border-purple-500/20 bg-gray-950" style={{ height: 260 }}>
          <canvas ref={canvasRef} className="w-full h-full" />
        </div>

        {/* Controls + stats */}
        <div className="px-5 py-4 space-y-3">
          <div className="flex items-center gap-3">
            <button
              onClick={togglePause}
              className="flex-1 py-2.5 rounded-xl font-semibold flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-500 text-white transition text-sm"
            >
              {paused ? '▶ Resume' : '⏸ Pause'}
            </button>
            <div className="flex gap-2">
              {palette.slice(0, 4).map((c, i) => (
                <span
                  key={i}
                  className="w-5 h-5 rounded-full border border-gray-700"
                  style={{ background: c }}
                />
              ))}
            </div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-3 gap-2 text-center">
            <StatBadge label="Particles" value={String(count)} note={rawCount > MAX_PARTICLES ? `capped from ${rawCount}` : undefined} />
            <StatBadge label="Speed" value={speed.toFixed(1)} />
            <StatBadge label="BPM" value={String(bpm)} />
          </div>

          {/* Audio feature summary */}
          {af && Object.keys(af).length > 0 && (
            <details className="group">
              <summary className="text-xs text-gray-600 hover:text-gray-400 cursor-pointer select-none">
                Show audio features
              </summary>
              <div className="mt-2 grid grid-cols-2 gap-1.5">
                {Object.entries(af).slice(0, 8).map(([k, v]) => (
                  <div key={k} className="bg-gray-800/50 rounded-lg px-2.5 py-1.5">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">{k.replace(/_/g, ' ')}</p>
                    <p className="text-xs font-semibold text-gray-200 truncate">
                      {typeof v === 'object' ? JSON.stringify(v) : String(v)}
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

function makeParticle(canvas: HTMLCanvasElement, palette: string[], speed: number): Particle {
  const angle = Math.random() * Math.PI * 2;
  const s = (0.3 + Math.random() * 0.7) * speed;
  return {
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    vx: Math.cos(angle) * s,
    vy: Math.sin(angle) * s,
    radius: 1.5 + Math.random() * 2.5,
    color: palette[Math.floor(Math.random() * palette.length)],
    alpha: 0.4 + Math.random() * 0.6,
  };
}

function hexAlpha(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function StatBadge({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-sm font-bold text-gray-100">{value}</p>
      {note && <p className="text-xs text-gray-600">{note}</p>}
    </div>
  );
}
