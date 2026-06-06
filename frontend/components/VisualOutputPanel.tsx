'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { VisualGenerationResult } from '../lib/api';

type Props = {
  result: VisualGenerationResult;
  onReset: () => void;
};

const MAX_PARTICLES = 600;

// ────────────────────────────────────────────────────────────────────
// Style → Renderer mapping. Each renderer is a totally different scene.
// ────────────────────────────────────────────────────────────────────
type RenderMode =
  | 'orbits'        // Classic — orbital rings around centre
  | 'flow_field'    // Funny — Perlin-flow particles
  | 'lightning'     // Electrifying — neon lightning bolts
  | 'horror'        // Horror — slow drifting smoke + flickers
  | 'aurora'        // Emotional — flowing aurora ribbons
  | 'bass_pulse'    // Bassy — concentric pulse rings on beat
  | 'mandala'       // Spiritual — symmetric kaleidoscope
  | 'glitch';       // Experimental — random grid scan-lines

function pickMode(style: string): RenderMode {
  switch ((style || '').toLowerCase()) {
    case 'funny':         return 'flow_field';
    case 'electrifying':  return 'lightning';
    case 'horror':        return 'horror';
    case 'emotional':     return 'aurora';
    case 'bassy':         return 'bass_pulse';
    case 'spiritual':     return 'mandala';
    case 'experimental':  return 'glitch';
    default:              return 'orbits';
  }
}

export default function VisualOutputPanel({ result, onReset }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);

  const cfg = result.visual_config;
  const palette: string[] = cfg?.colors?.palette ?? ['#7c3aed', '#2563eb', '#06b6d4'];
  const rawCount: number = cfg?.particles?.count ?? 200;
  const count = Math.min(rawCount, MAX_PARTICLES);
  const speed: number = cfg?.particles?.speed ?? 1.0;
  const bpm: number = cfg?.audio_sync?.bpm ?? 90;
  const mode: RenderMode = pickMode(result.style);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = canvas.offsetWidth * dpr;
      canvas.height = canvas.offsetHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    const renderer = createRenderer(mode, canvas, palette, count, speed, bpm);

    const draw = (now: number) => {
      if (!pausedRef.current) {
        renderer(ctx, now);
      }
      rafRef.current = requestAnimationFrame(draw);
    };
    rafRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [count, speed, bpm, palette, mode]);

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
        <div className="flex items-center justify-between px-5 pt-4 pb-3">
          <div className="flex items-center gap-2">
            <span className="text-purple-400 text-lg">✨</span>
            <span className="text-sm font-semibold text-purple-300 uppercase tracking-widest">
              Generated Visual
            </span>
            {result.style && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                {result.style} · {mode.replace(/_/g, ' ')}
              </span>
            )}
          </div>
          <button onClick={onReset} className="text-xs text-gray-500 hover:text-gray-300 transition">
            Try another
          </button>
        </div>

        <div
          className="mx-5 rounded-xl overflow-hidden border border-purple-500/20 bg-gray-950"
          style={{ height: 320 }}
        >
          <canvas ref={canvasRef} className="w-full h-full block" />
        </div>

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

          <div className="grid grid-cols-3 gap-2 text-center">
            <StatBadge label="Mode" value={mode.replace(/_/g, ' ')} />
            <StatBadge label="Particles" value={String(count)} />
            <StatBadge label="BPM" value={String(bpm)} />
          </div>

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

// ════════════════════════════════════════════════════════════════════
//                          RENDERERS
// ════════════════════════════════════════════════════════════════════

type RenderFn = (ctx: CanvasRenderingContext2D, now: number) => void;

function createRenderer(
  mode: RenderMode,
  canvas: HTMLCanvasElement,
  palette: string[],
  count: number,
  speed: number,
  bpm: number,
): RenderFn {
  switch (mode) {
    case 'flow_field':   return flowField(canvas, palette, count, speed);
    case 'lightning':    return lightning(canvas, palette, count, speed, bpm);
    case 'horror':       return horror(canvas, palette, count, speed, bpm);
    case 'aurora':       return aurora(canvas, palette, speed, bpm);
    case 'bass_pulse':   return bassPulse(canvas, palette, count, speed, bpm);
    case 'mandala':      return mandala(canvas, palette, count, speed, bpm);
    case 'glitch':       return glitch(canvas, palette, speed, bpm);
    default:             return orbits(canvas, palette, count, speed, bpm);
  }
}

const W = (c: HTMLCanvasElement) => c.offsetWidth;
const H = (c: HTMLCanvasElement) => c.offsetHeight;
const fade = (ctx: CanvasRenderingContext2D, c: HTMLCanvasElement, alpha = 0.18) => {
  ctx.fillStyle = `rgba(3, 7, 18, ${alpha})`;
  ctx.fillRect(0, 0, W(c), H(c));
};
const beat = (now: number, bpm: number) => {
  const interval = 60_000 / Math.max(20, bpm);
  return ((now % interval) / interval); // 0→1 over one beat
};

// ── Classic: orbital rings ──────────────────────────────────────────
function orbits(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bpm: number): RenderFn {
  const particles = Array.from({ length: count }, (_, i) => ({
    angle: Math.random() * Math.PI * 2,
    radius: 30 + Math.random() * 130,
    speed: (0.005 + Math.random() * 0.01) * speed * (1 + (i % 3) * 0.3),
    color: palette[i % palette.length],
    size: 1.5 + Math.random() * 2,
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.22);
    const cx = W(c) / 2, cy = H(c) / 2;
    const pulse = 1 + 0.15 * Math.sin(beat(now, bpm) * Math.PI * 2);
    for (const p of particles) {
      p.angle += p.speed;
      const x = cx + Math.cos(p.angle) * p.radius * pulse;
      const y = cy + Math.sin(p.angle) * p.radius * pulse;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(x, y, p.size * pulse, 0, Math.PI * 2);
      ctx.fill();
    }
  };
}

// ── Funny: Perlin-style flow field ──────────────────────────────────
function flowField(c: HTMLCanvasElement, palette: string[], count: number, speed: number): RenderFn {
  const particles = Array.from({ length: count }, () => ({
    x: Math.random() * W(c),
    y: Math.random() * H(c),
    color: palette[Math.floor(Math.random() * palette.length)],
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.05);
    const t = now * 0.0003;
    for (const p of particles) {
      const angle = (Math.sin(p.x * 0.012 + t) + Math.cos(p.y * 0.012 - t)) * Math.PI;
      p.x += Math.cos(angle) * 1.6 * speed;
      p.y += Math.sin(angle) * 1.6 * speed;
      if (p.x < 0 || p.x > W(c) || p.y < 0 || p.y > H(c)) {
        p.x = Math.random() * W(c);
        p.y = Math.random() * H(c);
      }
      ctx.fillStyle = p.color;
      ctx.fillRect(p.x, p.y, 2, 2);
    }
  };
}

// ── Electrifying: lightning bolts on beat ───────────────────────────
function lightning(c: HTMLCanvasElement, palette: string[], _count: number, _speed: number, bpm: number): RenderFn {
  let lastBeat = 0;
  let bolt: Array<{x: number; y: number}> = [];
  let boltAlpha = 0;
  return (ctx, now) => {
    fade(ctx, c, 0.25);
    const interval = 60_000 / Math.max(20, bpm);
    if (now - lastBeat > interval) {
      lastBeat = now;
      bolt = [];
      let x = Math.random() * W(c);
      let y = 0;
      while (y < H(c)) {
        bolt.push({ x, y });
        x += (Math.random() - 0.5) * 30;
        y += 8 + Math.random() * 14;
      }
      boltAlpha = 1;
    }
    if (boltAlpha > 0 && bolt.length > 1) {
      ctx.strokeStyle = palette[0];
      ctx.lineWidth = 2;
      ctx.shadowBlur = 16; ctx.shadowColor = palette[1] ?? '#22d3ee';
      ctx.globalAlpha = boltAlpha;
      ctx.beginPath();
      ctx.moveTo(bolt[0].x, bolt[0].y);
      for (let i = 1; i < bolt.length; i++) ctx.lineTo(bolt[i].x, bolt[i].y);
      ctx.stroke();
      ctx.globalAlpha = 1; ctx.shadowBlur = 0;
      boltAlpha -= 0.04;
    }
  };
}

// ── Horror: slow drifting smoke + random glitch flickers ───────────
function horror(c: HTMLCanvasElement, palette: string[], count: number, speed: number, _bpm: number): RenderFn {
  const smoke = Array.from({ length: count }, () => ({
    x: Math.random() * W(c),
    y: Math.random() * H(c),
    r: 20 + Math.random() * 60,
    vy: -(0.05 + Math.random() * 0.15) * speed,
    color: palette[Math.floor(Math.random() * palette.length)],
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.06);
    for (const p of smoke) {
      p.y += p.vy;
      if (p.y < -p.r) { p.y = H(c) + p.r; p.x = Math.random() * W(c); }
      const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r);
      grd.addColorStop(0, hexAlpha(p.color, 0.18));
      grd.addColorStop(1, hexAlpha(p.color, 0));
      ctx.fillStyle = grd;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill();
    }
    // Random flicker
    if (Math.random() < 0.02) {
      ctx.fillStyle = `rgba(255,255,255,${Math.random() * 0.3})`;
      ctx.fillRect(0, 0, W(c), H(c));
    }
  };
}

// ── Emotional: flowing aurora ribbons ──────────────────────────────
function aurora(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number): RenderFn {
  const ribbons = palette.slice(0, 4).map((color, i) => ({ color, phase: i * 0.7 }));
  return (ctx, now) => {
    fade(ctx, c, 0.12);
    const t = now * 0.0008 * speed;
    for (const r of ribbons) {
      ctx.beginPath();
      const grad = ctx.createLinearGradient(0, 0, W(c), 0);
      grad.addColorStop(0, hexAlpha(r.color, 0));
      grad.addColorStop(0.5, hexAlpha(r.color, 0.55));
      grad.addColorStop(1, hexAlpha(r.color, 0));
      ctx.strokeStyle = grad;
      ctx.lineWidth = 30 + 10 * Math.sin(beat(now, bpm) * Math.PI * 2);
      for (let x = 0; x <= W(c); x += 10) {
        const y = H(c) / 2 + Math.sin(x * 0.012 + t + r.phase) * 60
                + Math.cos(x * 0.005 + t * 0.6) * 30;
        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  };
}

// ── Bassy: concentric pulse rings on beat ──────────────────────────
function bassPulse(c: HTMLCanvasElement, palette: string[], _count: number, speed: number, bpm: number): RenderFn {
  const rings: Array<{ r: number; color: string; alpha: number }> = [];
  let lastBeat = 0;
  return (ctx, now) => {
    fade(ctx, c, 0.18);
    const interval = 60_000 / Math.max(20, bpm);
    if (now - lastBeat > interval) {
      lastBeat = now;
      rings.push({ r: 0, color: palette[rings.length % palette.length], alpha: 1 });
    }
    const cx = W(c) / 2, cy = H(c) / 2;
    for (const ring of rings) {
      ring.r += 4 * speed;
      ring.alpha -= 0.012;
      ctx.strokeStyle = hexAlpha(ring.color, ring.alpha);
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(cx, cy, ring.r, 0, Math.PI * 2);
      ctx.stroke();
    }
    while (rings.length && rings[0].alpha <= 0) rings.shift();
  };
}

// ── Spiritual: symmetric kaleidoscope mandala ──────────────────────
function mandala(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bpm: number): RenderFn {
  const spokes = 8;
  const dots = Array.from({ length: count }, () => ({
    angle: Math.random() * Math.PI * 2,
    radius: 10 + Math.random() * 130,
    color: palette[Math.floor(Math.random() * palette.length)],
    drift: (Math.random() - 0.5) * 0.005 * speed,
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.08);
    const cx = W(c) / 2, cy = H(c) / 2;
    const pulse = 1 + 0.1 * Math.sin(beat(now, bpm) * Math.PI * 2);
    for (const d of dots) {
      d.angle += d.drift;
      for (let s = 0; s < spokes; s++) {
        const a = d.angle + (s / spokes) * Math.PI * 2;
        const x = cx + Math.cos(a) * d.radius * pulse;
        const y = cy + Math.sin(a) * d.radius * pulse;
        ctx.fillStyle = hexAlpha(d.color, 0.7);
        ctx.beginPath();
        ctx.arc(x, y, 1.8, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  };
}

// ── Experimental: glitch grid + scan lines ─────────────────────────
function glitch(c: HTMLCanvasElement, palette: string[], _speed: number, bpm: number): RenderFn {
  return (ctx, now) => {
    ctx.fillStyle = '#020617';
    ctx.fillRect(0, 0, W(c), H(c));

    const cellSize = 24;
    const cols = Math.ceil(W(c) / cellSize);
    const rows = Math.ceil(H(c) / cellSize);
    for (let r = 0; r < rows; r++) {
      for (let col = 0; col < cols; col++) {
        if (Math.random() > 0.92) {
          ctx.fillStyle = hexAlpha(palette[Math.floor(Math.random() * palette.length)], 0.6 + Math.random() * 0.4);
          ctx.fillRect(col * cellSize, r * cellSize, cellSize - 2, cellSize - 2);
        }
      }
    }
    // Scan-line on beat
    const scanY = (beat(now, bpm) * H(c)) | 0;
    ctx.fillStyle = hexAlpha(palette[0], 0.5);
    ctx.fillRect(0, scanY, W(c), 2);
  };
}

// ── Helpers ─────────────────────────────────────────────────────────
function hexAlpha(hex: string, alpha: number): string {
  if (!hex.startsWith('#') || hex.length < 7) return hex;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function StatBadge({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-sm font-bold text-gray-100 truncate">{value}</p>
      {note && <p className="text-xs text-gray-600">{note}</p>}
    </div>
  );
}
