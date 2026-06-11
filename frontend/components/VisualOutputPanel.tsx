'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { VisualGenerationResult } from '../lib/api';
import { useAudioAnalyser } from '../hooks/useAudioAnalyser';
import LiveSpectrogram from './LiveSpectrogram';
import LiveSpectrogramStrip from './LiveSpectrogramStrip';
import StatusPill from './StatusPill';

type Props = {
  result: VisualGenerationResult;
  onReset: () => void;
  audioFile?: File;
};

const MAX_PARTICLES = 600;

// ────────────────────────────────────────────────────────────────────
// 50 Render modes — each a self-contained scene
// ────────────────────────────────────────────────────────────────────
type RenderMode =
  | 'orbits' | 'flow_field' | 'lightning' | 'horror' | 'aurora'
  | 'bass_pulse' | 'mandala' | 'glitch' | 'waveform' | 'spectrum_bars'
  | 'fireworks' | 'rain' | 'vortex' | 'matrix' | 'plasma'
  | 'nebula' | 'starfield' | 'rings' | 'dna_helix' | 'kaleidoscope'
  | 'terrain' | 'tunnel' | 'galaxy' | 'ripple' | 'lissajous'
  | 'spirograph' | 'metaballs' | 'fractal_tree' | 'circular_spectrum'
  | 'wave_terrain' | 'interference' | 'pixel_sort' | 'neon_grid'
  | 'pendulum' | 'bubbles' | 'constellation' | 'cube_field'
  | 'frequency_spiral' | 'smoke_trails' | 'bouncing_bars'
  | 'wave_mesh' | 'comet_trails' | 'heartbeat' | 'radar'
  | 'vinyl' | 'equalizer_circle' | 'neon_tunnel' | 'particle_fountain'
  | 'wormhole' | 'laser_show';

const ALL_MODES: RenderMode[] = [
  'orbits','flow_field','lightning','horror','aurora','bass_pulse','mandala','glitch',
  'waveform','spectrum_bars','fireworks','rain','vortex','matrix','plasma','nebula',
  'starfield','rings','dna_helix','kaleidoscope','terrain','tunnel','galaxy','ripple',
  'lissajous','spirograph','metaballs','fractal_tree','circular_spectrum','wave_terrain',
  'interference','pixel_sort','neon_grid','pendulum','bubbles','constellation','cube_field',
  'frequency_spiral','smoke_trails','bouncing_bars','wave_mesh','comet_trails','heartbeat',
  'radar','vinyl','equalizer_circle','neon_tunnel','particle_fountain','wormhole','laser_show',
];

function pickMode(
  style: string,
  audioFeatures: Record<string, unknown> = {},
  visualConfig: Record<string, unknown> = {},
): { mode: RenderMode; source: string } {
  const foundryMode = visualConfig?.render_mode as string;
  if (foundryMode && ALL_MODES.includes(foundryMode as RenderMode)) {
    return { mode: foundryMode as RenderMode, source: `AI: ${foundryMode.replace(/_/g, ' ')}` };
  }

  const explicit = pickModeFromStyle(style);
  if (explicit) return { mode: explicit, source: `style: ${style}` };

  return pickRandomMode(audioFeatures);
}

function pickModeFromStyle(style: string): RenderMode | null {
  switch ((style || '').toLowerCase()) {
    case 'funny':         return 'flow_field';
    case 'electrifying':  return 'lightning';
    case 'horror':        return 'horror';
    case 'emotional':     return 'aurora';
    case 'bassy':         return 'bass_pulse';
    case 'spiritual':     return 'mandala';
    case 'experimental':  return 'glitch';
    default:              return null;
  }
}

// Weighted random selection based on audio features
function pickRandomMode(af: Record<string, unknown>): { mode: RenderMode; source: string } {
  const bass = Number(af.bass_energy ?? 0);
  const treble = Number(af.treble_energy ?? 0);
  const bpm = Number(af.bpm ?? 90);
  const complexity = Number(af.complexity ?? 0.5);

  const hi = bpm > 110, lo = bpm < 80;
  const weights: Record<RenderMode, number> = {
    orbits: 1, flow_field: 1 + treble, lightning: hi ? 2 : 0.5,
    horror: bass > 0.4 ? 0.5 : 0.2, aurora: 1.2, bass_pulse: 1 + bass * 2,
    mandala: 1 + complexity, glitch: hi ? 1.5 : 0.5, waveform: 1,
    spectrum_bars: 1.2, fireworks: 1 + bass, rain: 0.8, vortex: 1 + bass,
    matrix: hi ? 1 : 0.4, plasma: 1, nebula: lo ? 1.2 : 0.7,
    starfield: hi ? 1.5 : 0.8, rings: 1, dna_helix: 0.8 + complexity,
    kaleidoscope: 1 + complexity, terrain: 1, tunnel: hi ? 1.5 : 0.6,
    galaxy: lo ? 1.3 : 0.8, ripple: 1 + bass, lissajous: 1,
    spirograph: 0.9 + complexity, metaballs: 1 + bass, fractal_tree: 0.8 + complexity,
    circular_spectrum: 1.2, wave_terrain: 1, interference: 0.9 + treble,
    pixel_sort: hi ? 1 : 0.5, neon_grid: hi ? 1.3 : 0.6,
    pendulum: lo ? 1.2 : 0.8, bubbles: 0.9, constellation: lo ? 1.3 : 0.7,
    cube_field: 1, frequency_spiral: 1 + treble, smoke_trails: lo ? 1 : 0.6,
    bouncing_bars: 1.2, wave_mesh: 1, comet_trails: hi ? 1.3 : 0.7,
    heartbeat: 1 + bass, radar: 0.9, vinyl: lo ? 1.2 : 0.7,
    equalizer_circle: 1.2, neon_tunnel: hi ? 1.4 : 0.7,
    particle_fountain: 1 + bass, wormhole: hi ? 1.3 : 0.6, laser_show: hi ? 1.5 : 0.5,
  };

  const entries = Object.entries(weights) as [RenderMode, number][];
  const total = entries.reduce((s, [, w]) => s + w, 0);
  let r = Math.random() * total;
  for (const [mode, w] of entries) {
    r -= w;
    if (r <= 0) return { mode, source: `random: ${mode.replace(/_/g, ' ')}` };
  }
  return { mode: 'orbits', source: 'random: orbits' };
}

export default function VisualOutputPanel({ result, onReset, audioFile }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);
  const audioElRef = useRef<HTMLAudioElement | null>(null);

  const { bassRef, onsetRef, analyserRef, isActive } = useAudioAnalyser(audioElRef);

  const [audioObjectUrl, setAudioObjectUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!result.audio_b64 && audioFile) {
      const url = URL.createObjectURL(audioFile);
      setAudioObjectUrl(url);
      return () => URL.revokeObjectURL(url);
    }
  }, [audioFile, result.audio_b64]);

  const cfg = result.visual_config;
  const palette: string[] = cfg?.colors?.palette ?? ['#7c3aed', '#2563eb', '#06b6d4'];
  const rawCount: number = cfg?.particles?.count ?? 200;
  const count = Math.min(rawCount, MAX_PARTICLES);
  const speed: number = cfg?.particles?.speed ?? 1.0;
  const bpm: number = cfg?.audio_sync?.bpm ?? 90;
  const seed = useRef(Math.floor(Math.random() * 1000)).current;
  const { mode, source: modeSource } = pickMode(
    result.style,
    result.audio_features as Record<string, unknown>,
    cfg as Record<string, unknown>,
  );

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

    const renderer = createRenderer(mode, canvas, palette, count, speed, bpm, bassRef, onsetRef, analyserRef, seed);

    const draw = (now: number) => {
      if (!pausedRef.current) {
        // Use audio currentTime when playing for perfect sync
        const audioEl = audioElRef.current;
        const audioNow = (audioEl && !audioEl.paused && audioEl.currentTime > 0)
          ? audioEl.currentTime * 1000
          : now;
        renderer(ctx, audioNow);
      }
      rafRef.current = requestAnimationFrame(draw);
    };
    rafRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [count, speed, bpm, palette, mode, result.audio_b64, seed]);

  const togglePause = () => {
    pausedRef.current = !pausedRef.current;
    setPaused(pausedRef.current);
    const audioEl = audioElRef.current;
    if (audioEl) {
      if (pausedRef.current) audioEl.pause();
      else audioEl.play();
    }
  };

  const af = result.audio_features as Record<string, unknown>;

  const resultAny = result as Record<string, unknown>;
  const statusMode: 'live' | 'heuristic' | 'mock' =
    resultAny.is_mock === false ? 'live'
    : resultAny.is_mock === true && af && Object.keys(af).length > 0 ? 'heuristic'
    : 'mock';
  const statusProvider = typeof resultAny.provider === 'string' ? resultAny.provider : undefined;

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
                {mode.replace(/_/g, ' ')}{isActive ? ' · live' : ''}
              </span>
            )}
            {!result.style && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700/50 text-slate-400 border border-slate-600">
                {mode.replace(/_/g, ' ')} · {modeSource}
              </span>
            )}
            <StatusPill mode={statusMode} provider={statusProvider} />
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

        <LiveSpectrogramStrip analyserRef={analyserRef} isActive={isActive} />

        <div className="mx-5 mt-1">
          <LiveSpectrogram analyserRef={analyserRef} isActive={isActive} height={80} />
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

          {(result.audio_b64 || audioObjectUrl) && (
            <audio
              ref={audioElRef}
              src={result.audio_b64
                ? (result.audio_b64.startsWith('data:') ? result.audio_b64 : `data:audio/wav;base64,${result.audio_b64}`)
                : audioObjectUrl!}
              controls
              className="w-full mt-2 rounded-lg h-8 opacity-80"
            />
          )}

          <div className="grid grid-cols-4 gap-2 text-center">
            <VibeBadge vibe={String(af?.vibe ?? '')} />
            <StatBadge label="Genre" value={String(af?.genre ?? '—')} />
            <StatBadge label="Key" value={String(af?.pitch_note ?? af?.key ?? '—')} />
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
type AudioRef = React.MutableRefObject<number>;

function createRenderer(
  mode: RenderMode,
  canvas: HTMLCanvasElement,
  palette: string[],
  count: number,
  speed: number,
  bpm: number,
  bassRef: AudioRef,
  onsetRef: AudioRef,
  analyserRef: React.RefObject<AnalyserNode | null>,
  seed: number,
): RenderFn {
  const A = analyserRef, S = seed, B = bassRef, O = onsetRef;
  switch (mode) {
    case 'flow_field':       return flowField(canvas, palette, count, speed, B, S);
    case 'lightning':        return lightning(canvas, palette, count, speed, bpm, O, S);
    case 'horror':           return horror(canvas, palette, count, speed, bpm, B, S);
    case 'aurora':           return aurora(canvas, palette, speed, bpm, B, S);
    case 'bass_pulse':       return bassPulse(canvas, palette, count, speed, bpm, B, O);
    case 'mandala':          return mandala(canvas, palette, count, speed, bpm, B, S);
    case 'glitch':           return glitch(canvas, palette, speed, bpm, O, S);
    case 'waveform':         return waveform(canvas, palette, speed, bpm, B, A);
    case 'spectrum_bars':    return spectrumBars(canvas, palette, bpm, B, A);
    case 'fireworks':        return fireworks(canvas, palette, speed, bpm, B, O);
    case 'rain':             return rain(canvas, palette, count, speed, B, O, S);
    case 'vortex':           return vortex(canvas, palette, count, speed, bpm, B, S);
    case 'matrix':           return matrix(canvas, palette, speed, bpm, B, O, S);
    case 'plasma':           return plasma(canvas, palette, speed, bpm, B, S);
    case 'nebula':           return nebula(canvas, palette, count, speed, B, S);
    case 'starfield':        return starfield(canvas, palette, count, speed, B, O, S);
    case 'rings':            return concentricRings(canvas, palette, speed, bpm, B, S);
    case 'dna_helix':        return dnaHelix(canvas, palette, speed, bpm, B, S);
    case 'kaleidoscope':     return kaleidoscope(canvas, palette, count, speed, bpm, B, S);
    case 'terrain':          return terrain(canvas, palette, speed, bpm, B, S);
    case 'tunnel':           return tunnel(canvas, palette, speed, bpm, B, S);
    case 'galaxy':           return galaxy(canvas, palette, count, speed, B, S);
    case 'ripple':           return ripple(canvas, palette, speed, bpm, B, O);
    case 'lissajous':        return lissajous(canvas, palette, speed, bpm, B, S);
    case 'spirograph':       return spirograph(canvas, palette, speed, bpm, B, S);
    case 'metaballs':        return metaballs(canvas, palette, count, speed, B, S);
    case 'fractal_tree':     return fractalTree(canvas, palette, speed, bpm, B, O, S);
    case 'circular_spectrum':return circularSpectrum(canvas, palette, bpm, B, A);
    case 'wave_terrain':     return waveTerrain(canvas, palette, speed, bpm, B, S);
    case 'interference':     return interference(canvas, palette, speed, bpm, B, S);
    case 'pixel_sort':       return pixelSort(canvas, palette, speed, B, O, S);
    case 'neon_grid':        return neonGrid(canvas, palette, speed, bpm, B, S);
    case 'pendulum':         return pendulum(canvas, palette, count, speed, bpm, B, S);
    case 'bubbles':          return bubbles(canvas, palette, count, speed, B, O, S);
    case 'constellation':    return constellation(canvas, palette, count, speed, B, S);
    case 'cube_field':       return cubeField(canvas, palette, speed, bpm, B, S);
    case 'frequency_spiral': return frequencySpiral(canvas, palette, speed, bpm, B, A);
    case 'smoke_trails':     return smokeTrails(canvas, palette, count, speed, B, S);
    case 'bouncing_bars':    return bouncingBars(canvas, palette, bpm, B, O);
    case 'wave_mesh':        return waveMesh(canvas, palette, speed, bpm, B, S);
    case 'comet_trails':     return cometTrails(canvas, palette, count, speed, B, O, S);
    case 'heartbeat':        return heartbeat(canvas, palette, speed, bpm, B, O);
    case 'radar':            return radar(canvas, palette, speed, bpm, B, S);
    case 'vinyl':            return vinyl(canvas, palette, speed, bpm, B, S);
    case 'equalizer_circle': return equalizerCircle(canvas, palette, bpm, B, A);
    case 'neon_tunnel':      return neonTunnel(canvas, palette, speed, bpm, B, S);
    case 'particle_fountain':return particleFountain(canvas, palette, count, speed, B, O);
    case 'wormhole':         return wormhole(canvas, palette, speed, bpm, B, S);
    case 'laser_show':       return laserShow(canvas, palette, speed, bpm, B, O, S);
    default:                 return orbits(canvas, palette, count, speed, bpm, B, S);
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
  return ((now % interval) / interval);
};

// Seeded random — deterministic per seed for reproducibility
function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s & 0x7fffffff) / 0x7fffffff;
  };
}

// ── 1. Orbits: orbital rings ──────────────────────────────────────
function orbits(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const particles = Array.from({ length: count }, (_, i) => ({
    angle: rng() * Math.PI * 2,
    radius: 30 + rng() * 130,
    speed: (0.005 + rng() * 0.01) * speed * (1 + (i % 3) * 0.3),
    color: palette[i % palette.length],
    size: 1.5 + rng() * 2,
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.22);
    const cx = W(c) / 2, cy = H(c) / 2;
    const pulse = 1 + 0.15 * Math.sin(beat(now, bpm) * Math.PI * 2) + bassRef.current * 0.3;
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

// ── 2. Flow field: Perlin-style drifting ──────────────────────────
function flowField(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bassRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const shape = seed % 3; // 0=circle, 1=square, 2=diamond
  const particles = Array.from({ length: count }, () => ({
    x: rng() * W(c),
    y: rng() * H(c),
    color: palette[Math.floor(rng() * palette.length)],
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.05);
    const t = now * 0.0003;
    const bass = bassRef.current;
    for (const p of particles) {
      const angle = (Math.sin(p.x * 0.012 + t) + Math.cos(p.y * 0.012 - t)) * Math.PI;
      const v = (1.6 + bass * 2) * speed;
      p.x += Math.cos(angle) * v;
      p.y += Math.sin(angle) * v;
      if (p.x < 0 || p.x > W(c) || p.y < 0 || p.y > H(c)) {
        p.x = Math.random() * W(c);
        p.y = Math.random() * H(c);
      }
      ctx.fillStyle = p.color;
      const s = 2 + bass * 3;
      if (shape === 0) { ctx.beginPath(); ctx.arc(p.x, p.y, s, 0, Math.PI * 2); ctx.fill(); }
      else if (shape === 1) { ctx.fillRect(p.x - s/2, p.y - s/2, s, s); }
      else { ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(Math.PI / 4); ctx.fillRect(-s/2, -s/2, s, s); ctx.restore(); }
    }
  };
}

// ── 3. Lightning: neon bolts on beat ──────────────────────────────
function lightning(c: HTMLCanvasElement, palette: string[], _count: number, _speed: number, bpm: number, onsetRef: AudioRef, seed: number): RenderFn {
  let lastBeat = 0;
  let bolts: Array<{ points: Array<{x:number;y:number}>; alpha: number; color: string }> = [];
  let prevOnset = 0;
  const boltCount = 1 + (seed % 3); // 1-3 simultaneous bolts
  return (ctx, now) => {
    fade(ctx, c, 0.25);
    const interval = 60_000 / Math.max(20, bpm);
    const onset = onsetRef.current;
    const shouldFire = (onset > 0 && prevOnset === 0) || (onset === 0 && now - lastBeat > interval);
    prevOnset = onset;
    if (shouldFire) {
      lastBeat = now;
      for (let b = 0; b < boltCount; b++) {
        const points: Array<{x:number;y:number}> = [];
        let x = Math.random() * W(c);
        let y = 0;
        while (y < H(c)) {
          points.push({ x, y });
          x += (Math.random() - 0.5) * 40;
          y += 6 + Math.random() * 16;
        }
        bolts.push({ points, alpha: 1, color: palette[b % palette.length] });
      }
    }
    for (const bolt of bolts) {
      if (bolt.alpha > 0 && bolt.points.length > 1) {
        ctx.strokeStyle = bolt.color;
        ctx.lineWidth = 2 + bolt.alpha * 2;
        ctx.shadowBlur = 20; ctx.shadowColor = bolt.color;
        ctx.globalAlpha = bolt.alpha;
        ctx.beginPath();
        ctx.moveTo(bolt.points[0].x, bolt.points[0].y);
        for (let i = 1; i < bolt.points.length; i++) ctx.lineTo(bolt.points[i].x, bolt.points[i].y);
        ctx.stroke();
        ctx.globalAlpha = 1; ctx.shadowBlur = 0;
        bolt.alpha -= 0.04;
      }
    }
    bolts = bolts.filter(b => b.alpha > 0);
  };
}

// ── 4. Horror: smoke + flickers ───────────────────────────────────
function horror(c: HTMLCanvasElement, palette: string[], count: number, speed: number, _bpm: number, bassRef: AudioRef, _seed: number): RenderFn {
  const smoke = Array.from({ length: count }, () => ({
    x: Math.random() * W(c),
    y: Math.random() * H(c),
    r: 20 + Math.random() * 60,
    vy: -(0.05 + Math.random() * 0.15) * speed,
    color: palette[Math.floor(Math.random() * palette.length)],
  }));
  return (ctx, _now) => {
    fade(ctx, c, 0.06);
    const bass = bassRef.current;
    for (const p of smoke) {
      p.y += p.vy * (1 + bass * 3);
      if (p.y < -p.r) { p.y = H(c) + p.r; p.x = Math.random() * W(c); }
      const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * (1 + bass));
      grd.addColorStop(0, hexAlpha(p.color, 0.18 + bass * 0.2));
      grd.addColorStop(1, hexAlpha(p.color, 0));
      ctx.fillStyle = grd;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r * (1 + bass), 0, Math.PI * 2); ctx.fill();
    }
    if (Math.random() < 0.02 + bass * 0.08) {
      ctx.fillStyle = `rgba(255,255,255,${Math.random() * 0.3 + bass * 0.2})`;
      ctx.fillRect(0, 0, W(c), H(c));
    }
  };
}

// ── 5. Aurora: flowing ribbons ────────────────────────────────────
function aurora(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, _seed: number): RenderFn {
  const ribbons = palette.slice(0, 4).map((color, i) => ({ color, phase: i * 0.7 }));
  return (ctx, now) => {
    fade(ctx, c, 0.12);
    const t = now * 0.0008 * speed;
    const bass = bassRef.current;
    for (const r of ribbons) {
      ctx.beginPath();
      const grad = ctx.createLinearGradient(0, 0, W(c), 0);
      grad.addColorStop(0, hexAlpha(r.color, 0));
      grad.addColorStop(0.5, hexAlpha(r.color, 0.55 + bass * 0.3));
      grad.addColorStop(1, hexAlpha(r.color, 0));
      ctx.strokeStyle = grad;
      ctx.lineWidth = 30 + 10 * Math.sin(beat(now, bpm) * Math.PI * 2) + bass * 20;
      for (let x = 0; x <= W(c); x += 10) {
        const y = H(c) / 2 + Math.sin(x * 0.012 + t + r.phase) * (60 + bass * 40)
                + Math.cos(x * 0.005 + t * 0.6) * 30;
        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  };
}

// ── 6. Bass pulse: concentric rings ───────────────────────────────
function bassPulse(c: HTMLCanvasElement, palette: string[], _count: number, speed: number, bpm: number, bassRef: AudioRef, onsetRef: AudioRef): RenderFn {
  const rings: Array<{ r: number; color: string; alpha: number; expandSpeed: number }> = [];
  let lastBeat = 0;
  let prevOnset = 0;
  return (ctx, now) => {
    fade(ctx, c, 0.18);
    const interval = 60_000 / Math.max(20, bpm);
    const onset = onsetRef.current;
    if (onset > 0 && prevOnset === 0) {
      rings.push({ r: 0, color: palette[rings.length % palette.length], alpha: 1, expandSpeed: 4 * speed + bassRef.current * 2 });
    } else if (onset === 0 && now - lastBeat > interval) {
      lastBeat = now;
      rings.push({ r: 0, color: palette[rings.length % palette.length], alpha: 1, expandSpeed: 4 * speed });
    }
    prevOnset = onset;
    const cx = W(c) / 2, cy = H(c) / 2;
    for (const ring of rings) {
      ring.r += ring.expandSpeed;
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

// ── 7. Mandala: symmetric kaleidoscope ────────────────────────────
function mandala(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const spokes = 6 + (seed % 8); // 6-13 spokes
  const rng = seededRandom(seed);
  const dots = Array.from({ length: count }, () => ({
    angle: rng() * Math.PI * 2,
    radius: 10 + rng() * 130,
    color: palette[Math.floor(rng() * palette.length)],
    drift: (rng() - 0.5) * 0.005 * speed,
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.08);
    const cx = W(c) / 2, cy = H(c) / 2;
    const bass = bassRef.current;
    const pulse = 1 + 0.1 * Math.sin(beat(now, bpm) * Math.PI * 2) + bass * 0.25;
    for (const d of dots) {
      d.angle += d.drift * (1 + bass * 2);
      for (let s = 0; s < spokes; s++) {
        const a = d.angle + (s / spokes) * Math.PI * 2;
        const x = cx + Math.cos(a) * d.radius * pulse;
        const y = cy + Math.sin(a) * d.radius * pulse;
        ctx.fillStyle = hexAlpha(d.color, 0.7 + bass * 0.3);
        ctx.beginPath();
        ctx.arc(x, y, 1.8 + bass * 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  };
}

// ── 8. Glitch: random grid + scan lines ───────────────────────────
function glitch(c: HTMLCanvasElement, palette: string[], _speed: number, bpm: number, onsetRef: AudioRef, seed: number): RenderFn {
  const cellSize = 16 + (seed % 3) * 8; // 16, 24, or 32
  return (ctx, now) => {
    ctx.fillStyle = '#020617';
    ctx.fillRect(0, 0, W(c), H(c));
    const onset = onsetRef.current;
    const cols = Math.ceil(W(c) / cellSize);
    const rows = Math.ceil(H(c) / cellSize);
    const density = 0.92 - onset * 0.15;
    for (let r = 0; r < rows; r++) {
      for (let col = 0; col < cols; col++) {
        if (Math.random() > density) {
          ctx.fillStyle = hexAlpha(palette[Math.floor(Math.random() * palette.length)], 0.6 + Math.random() * 0.4);
          ctx.fillRect(col * cellSize, r * cellSize, cellSize - 2, cellSize - 2);
        }
      }
    }
    const scanY = (beat(now, bpm) * H(c)) | 0;
    ctx.fillStyle = hexAlpha(palette[0], 0.5 + onset * 0.4);
    ctx.fillRect(0, scanY, W(c), 2 + onset * 4);
  };
}

// ── 9. Waveform: oscilloscope-style ───────────────────────────────
function waveform(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, analyserRef: React.RefObject<AnalyserNode | null>): RenderFn {
  return (ctx, now) => {
    fade(ctx, c, 0.3);
    const w = W(c), h = H(c);
    const bass = bassRef.current;
    const analyser = analyserRef.current;
    const t = now * 0.001 * speed;

    if (analyser) {
      const bufLen = analyser.frequencyBinCount;
      const data = new Uint8Array(bufLen);
      analyser.getByteTimeDomainData(data);
      for (let layer = 0; layer < 3; layer++) {
        ctx.beginPath();
        ctx.strokeStyle = hexAlpha(palette[layer % palette.length], 0.7 - layer * 0.15);
        ctx.lineWidth = 3 - layer;
        const sliceW = w / bufLen;
        for (let i = 0; i < bufLen; i++) {
          const v = data[i] / 128.0;
          const y = (v * h / 2) + layer * 4;
          if (i === 0) ctx.moveTo(0, y); else ctx.lineTo(i * sliceW, y);
        }
        ctx.stroke();
      }
    } else {
      // Fallback sine wave when no analyser
      for (let layer = 0; layer < 3; layer++) {
        ctx.beginPath();
        ctx.strokeStyle = hexAlpha(palette[layer % palette.length], 0.7 - layer * 0.15);
        ctx.lineWidth = 3 - layer;
        const amp = 40 + bass * 60 + layer * 15;
        const freq = 0.02 + layer * 0.008;
        for (let x = 0; x <= w; x += 2) {
          const y = h / 2 + Math.sin(x * freq + t + layer) * amp * (1 + 0.3 * Math.sin(beat(now, bpm) * Math.PI * 2));
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
    }
  };
}

// ── 10. Spectrum bars: equalizer ──────────────────────────────────
function spectrumBars(c: HTMLCanvasElement, palette: string[], bpm: number, bassRef: AudioRef, analyserRef: React.RefObject<AnalyserNode | null>): RenderFn {
  const smoothed = new Float32Array(64);
  return (ctx, now) => {
    ctx.fillStyle = '#020617';
    ctx.fillRect(0, 0, W(c), H(c));
    const w = W(c), h = H(c);
    const bass = bassRef.current;
    const analyser = analyserRef.current;
    const barCount = 64;
    const barW = w / barCount - 2;
    const beatPulse = 1 + 0.2 * Math.sin(beat(now, bpm) * Math.PI * 2);

    const data = new Uint8Array(analyser?.frequencyBinCount ?? 128);
    if (analyser) analyser.getByteFrequencyData(data);

    for (let i = 0; i < barCount; i++) {
      const raw = analyser ? data[Math.floor(i * data.length / barCount)] / 255 : (0.3 + bass * 0.4) * Math.abs(Math.sin(now * 0.002 + i * 0.3));
      smoothed[i] += (raw - smoothed[i]) * 0.3;
      const barH = smoothed[i] * h * 0.85 * beatPulse;
      const colorIdx = Math.floor(i / (barCount / palette.length)) % palette.length;
      // Bar
      ctx.fillStyle = hexAlpha(palette[colorIdx], 0.8);
      ctx.fillRect(i * (barW + 2), h - barH, barW, barH);
      // Glow cap
      ctx.fillStyle = palette[colorIdx];
      ctx.fillRect(i * (barW + 2), h - barH - 3, barW, 3);
      // Reflection
      ctx.fillStyle = hexAlpha(palette[colorIdx], 0.15);
      ctx.fillRect(i * (barW + 2), h, barW, barH * 0.3);
    }
  };
}

// ── 11. Fireworks: burst on onset ─────────────────────────────────
function fireworks(c: HTMLCanvasElement, palette: string[], speed: number, _bpm: number, bassRef: AudioRef, onsetRef: AudioRef): RenderFn {
  type Spark = { x: number; y: number; vx: number; vy: number; color: string; alpha: number; size: number };
  const sparks: Spark[] = [];
  let prevOnset = 0;
  return (ctx, _now) => {
    fade(ctx, c, 0.12);
    const onset = onsetRef.current;
    const bass = bassRef.current;
    if (onset > 0 && prevOnset === 0) {
      const cx = Math.random() * W(c) * 0.6 + W(c) * 0.2;
      const cy = Math.random() * H(c) * 0.4 + H(c) * 0.1;
      const color = palette[Math.floor(Math.random() * palette.length)];
      const sparkCount = 30 + Math.floor(bass * 40);
      for (let i = 0; i < sparkCount; i++) {
        const angle = Math.random() * Math.PI * 2;
        const vel = (2 + Math.random() * 4) * speed;
        sparks.push({ x: cx, y: cy, vx: Math.cos(angle) * vel, vy: Math.sin(angle) * vel, color, alpha: 1, size: 1.5 + Math.random() * 2 });
      }
    }
    prevOnset = onset;
    for (let i = sparks.length - 1; i >= 0; i--) {
      const s = sparks[i];
      s.x += s.vx;
      s.y += s.vy;
      s.vy += 0.08; // gravity
      s.alpha -= 0.015;
      s.vx *= 0.98;
      if (s.alpha <= 0) { sparks.splice(i, 1); continue; }
      ctx.fillStyle = hexAlpha(s.color, s.alpha);
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
      ctx.fill();
    }
  };
}

// ── 12. Rain: falling streaks ─────────────────────────────────────
function rain(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bassRef: AudioRef, onsetRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const dir = seed % 2 === 0 ? 1 : -0.3; // straight or angled
  const drops = Array.from({ length: count }, () => ({
    x: rng() * W(c),
    y: rng() * H(c),
    len: 8 + rng() * 20,
    speed: (3 + rng() * 5) * speed,
    color: palette[Math.floor(rng() * palette.length)],
    alpha: 0.3 + rng() * 0.5,
  }));
  return (ctx, _now) => {
    fade(ctx, c, 0.15);
    const bass = bassRef.current;
    const onset = onsetRef.current;
    for (const d of drops) {
      d.y += d.speed * (1 + bass * 2);
      d.x += d.speed * dir * 0.3;
      if (d.y > H(c)) { d.y = -d.len; d.x = Math.random() * W(c); }
      if (d.x > W(c)) d.x = 0;
      ctx.strokeStyle = hexAlpha(d.color, d.alpha + onset * 0.3);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(d.x, d.y);
      ctx.lineTo(d.x + dir * d.len * 0.3, d.y + d.len);
      ctx.stroke();
    }
    // Flash on onset
    if (onset > 0) {
      ctx.fillStyle = `rgba(255,255,255,${0.05 + bass * 0.1})`;
      ctx.fillRect(0, 0, W(c), H(c));
    }
  };
}

// ── 13. Vortex: spiral suction ────────────────────────────────────
function vortex(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const dir = seed % 2 === 0 ? 1 : -1;
  const particles = Array.from({ length: count }, () => ({
    angle: rng() * Math.PI * 2,
    dist: 20 + rng() * 160,
    speed: (0.01 + rng() * 0.02) * speed,
    color: palette[Math.floor(rng() * palette.length)],
    size: 1 + rng() * 2.5,
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.1);
    const cx = W(c) / 2, cy = H(c) / 2;
    const bass = bassRef.current;
    const pull = 0.2 + bass * 0.8;
    const beatPhase = beat(now, bpm);
    for (const p of particles) {
      p.angle += p.speed * dir * (1 + bass * 2);
      p.dist -= pull * 0.3;
      if (p.dist < 5) { p.dist = 160; p.angle = Math.random() * Math.PI * 2; }
      const wobble = Math.sin(beatPhase * Math.PI * 2) * 5;
      const x = cx + Math.cos(p.angle) * (p.dist + wobble);
      const y = cy + Math.sin(p.angle) * (p.dist + wobble);
      ctx.fillStyle = hexAlpha(p.color, 0.6 + bass * 0.4);
      ctx.beginPath();
      ctx.arc(x, y, p.size * (1 + bass * 0.5), 0, Math.PI * 2);
      ctx.fill();
    }
  };
}

// ── 14. Matrix: falling character columns ─────────────────────────
function matrix(c: HTMLCanvasElement, palette: string[], speed: number, _bpm: number, bassRef: AudioRef, onsetRef: AudioRef, seed: number): RenderFn {
  const colW = 14;
  const cols = Math.ceil(W(c) / colW);
  const rng = seededRandom(seed);
  const drops = Array.from({ length: cols }, () => rng() * H(c) / 14);
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&*+=<>{}[]SpectraVerse';
  return (ctx, _now) => {
    ctx.fillStyle = 'rgba(3, 7, 18, 0.06)';
    ctx.fillRect(0, 0, W(c), H(c));
    const bass = bassRef.current;
    const onset = onsetRef.current;
    ctx.font = '12px monospace';
    for (let i = 0; i < cols; i++) {
      const ch = chars[Math.floor(Math.random() * chars.length)];
      const colorIdx = i % palette.length;
      ctx.fillStyle = onset > 0
        ? '#ffffff'
        : hexAlpha(palette[colorIdx], 0.7 + bass * 0.3);
      ctx.fillText(ch, i * colW, drops[i] * 14);
      if (drops[i] * 14 > H(c) && Math.random() > 0.975) {
        drops[i] = 0;
      }
      drops[i] += (0.6 + bass * 0.8) * speed;
    }
  };
}

// ── 15. Plasma: sine-interference color field ─────────────────────
function plasma(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const step = 8;
  const phaseOffset = (seed % 10) * 0.3;
  return (ctx, now) => {
    const w = W(c), h = H(c);
    const t = now * 0.0005 * speed + phaseOffset;
    const bass = bassRef.current;
    const beatV = beat(now, bpm);
    for (let x = 0; x < w; x += step) {
      for (let y = 0; y < h; y += step) {
        const v1 = Math.sin(x * 0.02 + t);
        const v2 = Math.sin(y * 0.015 - t * 0.7);
        const v3 = Math.sin((x + y) * 0.01 + t * 0.5);
        const v4 = Math.sin(Math.sqrt(((x - w/2)**2 + (y - h/2)**2)) * 0.02 - t);
        const v = (v1 + v2 + v3 + v4 + bass * Math.sin(beatV * Math.PI * 2)) / 4;
        const idx = Math.floor(((v + 1) / 2) * (palette.length - 1));
        ctx.fillStyle = hexAlpha(palette[Math.max(0, Math.min(idx, palette.length - 1))], 0.85);
        ctx.fillRect(x, y, step, step);
      }
    }
  };
}

// ── 16. Nebula: drifting gradient clouds ──────────────────────────
function nebula(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bassRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const clouds = Array.from({ length: Math.min(count, 40) }, () => ({
    x: rng() * W(c),
    y: rng() * H(c),
    r: 40 + rng() * 100,
    vx: (rng() - 0.5) * 0.5 * speed,
    vy: (rng() - 0.5) * 0.3 * speed,
    color: palette[Math.floor(rng() * palette.length)],
    phase: rng() * Math.PI * 2,
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.04);
    const bass = bassRef.current;
    const t = now * 0.001;
    for (const cl of clouds) {
      cl.x += cl.vx;
      cl.y += cl.vy;
      if (cl.x < -cl.r) cl.x = W(c) + cl.r;
      if (cl.x > W(c) + cl.r) cl.x = -cl.r;
      if (cl.y < -cl.r) cl.y = H(c) + cl.r;
      if (cl.y > H(c) + cl.r) cl.y = -cl.r;
      const pulse = cl.r * (1 + 0.2 * Math.sin(t + cl.phase) + bass * 0.4);
      const grd = ctx.createRadialGradient(cl.x, cl.y, 0, cl.x, cl.y, pulse);
      grd.addColorStop(0, hexAlpha(cl.color, 0.2 + bass * 0.2));
      grd.addColorStop(0.6, hexAlpha(cl.color, 0.08));
      grd.addColorStop(1, hexAlpha(cl.color, 0));
      ctx.fillStyle = grd;
      ctx.beginPath();
      ctx.arc(cl.x, cl.y, pulse, 0, Math.PI * 2);
      ctx.fill();
    }
  };
}

// ── 17. Starfield: 3D zoom ────────────────────────────────────────
function starfield(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bassRef: AudioRef, onsetRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const stars = Array.from({ length: Math.min(count, 400) }, () => ({
    x: (rng() - 0.5) * 2,
    y: (rng() - 0.5) * 2,
    z: rng(),
    color: palette[Math.floor(rng() * palette.length)],
  }));
  return (ctx, _now) => {
    ctx.fillStyle = '#020617';
    ctx.fillRect(0, 0, W(c), H(c));
    const w = W(c), h = H(c);
    const cx = w / 2, cy = h / 2;
    const bass = bassRef.current;
    const onset = onsetRef.current;
    const zSpeed = (0.01 + bass * 0.03) * speed * (onset > 0 ? 3 : 1);
    for (const s of stars) {
      s.z -= zSpeed;
      if (s.z <= 0.01) { s.z = 1; s.x = (Math.random() - 0.5) * 2; s.y = (Math.random() - 0.5) * 2; }
      const sx = cx + (s.x / s.z) * w * 0.5;
      const sy = cy + (s.y / s.z) * h * 0.5;
      const size = (1 - s.z) * 3 + bass * 2;
      const alpha = (1 - s.z) * 0.8 + 0.2;
      ctx.fillStyle = hexAlpha(s.color, alpha);
      ctx.beginPath();
      ctx.arc(sx, sy, Math.max(0.5, size), 0, Math.PI * 2);
      ctx.fill();
      // Streak trail
      const tx = cx + (s.x / (s.z + zSpeed * 4)) * w * 0.5;
      const ty = cy + (s.y / (s.z + zSpeed * 4)) * h * 0.5;
      ctx.strokeStyle = hexAlpha(s.color, alpha * 0.4);
      ctx.lineWidth = Math.max(0.3, size * 0.5);
      ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(tx, ty); ctx.stroke();
    }
  };
}

// ── 18. Rings: concentric rotating rings with gaps ────────────────
function concentricRings(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const ringCount = 6 + (seed % 6);
  const rng = seededRandom(seed);
  const ringsData = Array.from({ length: ringCount }, (_, i) => ({
    radius: 20 + i * 25,
    rotation: rng() * Math.PI * 2,
    speed: (0.005 + rng() * 0.015) * speed * (i % 2 === 0 ? 1 : -1),
    gap: 0.3 + rng() * 1.0,
    color: palette[i % palette.length],
    width: 2 + rng() * 4,
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.15);
    const cx = W(c) / 2, cy = H(c) / 2;
    const bass = bassRef.current;
    const beatPhase = beat(now, bpm);
    for (const r of ringsData) {
      r.rotation += r.speed * (1 + bass * 2);
      const pulse = r.radius * (1 + 0.1 * Math.sin(beatPhase * Math.PI * 2) + bass * 0.2);
      ctx.strokeStyle = hexAlpha(r.color, 0.6 + bass * 0.4);
      ctx.lineWidth = r.width;
      ctx.beginPath();
      ctx.arc(cx, cy, pulse, r.rotation, r.rotation + Math.PI * 2 - r.gap);
      ctx.stroke();
    }
  };
}

// ── 19. DNA Helix: rotating double helix ──────────────────────────
function dnaHelix(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const orient = seed % 2; // 0=vertical, 1=horizontal
  return (ctx, now) => {
    fade(ctx, c, 0.15);
    const w = W(c), h = H(c);
    const bass = bassRef.current;
    const t = now * 0.002 * speed;
    const beatV = beat(now, bpm);
    const beatPulse = 1 + 0.15 * Math.sin(beatV * Math.PI * 2);
    const steps = 60;
    const c1 = palette[0], c2 = palette[1 % palette.length];

    for (let i = 0; i < steps; i++) {
      const frac = i / steps;
      const phase = frac * Math.PI * 4 + t;
      const amp = (30 + bass * 25) * beatPulse;
      let x1: number, y1: number, x2: number, y2: number;
      if (orient === 0) {
        const yy = frac * h;
        x1 = w / 2 + Math.sin(phase) * amp;
        y1 = yy;
        x2 = w / 2 + Math.sin(phase + Math.PI) * amp;
        y2 = yy;
      } else {
        const xx = frac * w;
        x1 = xx;
        y1 = h / 2 + Math.sin(phase) * amp;
        x2 = xx;
        y2 = h / 2 + Math.sin(phase + Math.PI) * amp;
      }
      const depth = (Math.sin(phase) + 1) / 2;
      // Rungs
      if (i % 4 === 0) {
        ctx.strokeStyle = hexAlpha(palette[2 % palette.length], 0.2 + bass * 0.3);
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
      }
      // Nodes
      const s1 = 3 + depth * 3 + bass * 2;
      const s2 = 3 + (1 - depth) * 3 + bass * 2;
      ctx.fillStyle = hexAlpha(c1, 0.5 + depth * 0.5);
      ctx.beginPath(); ctx.arc(x1, y1, s1, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = hexAlpha(c2, 0.5 + (1 - depth) * 0.5);
      ctx.beginPath(); ctx.arc(x2, y2, s2, 0, Math.PI * 2); ctx.fill();
    }
  };
}

// ── 20. Kaleidoscope: 6-fold mirror symmetry ──────────────────────
function kaleidoscope(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const folds = 6;
  const rng = seededRandom(seed);
  const shapes = Array.from({ length: Math.min(count, 80) }, () => ({
    angle: rng() * Math.PI * 2 / folds,
    dist: 10 + rng() * 120,
    size: 2 + rng() * 6,
    drift: (rng() - 0.5) * 0.008 * speed,
    radialSpeed: (rng() - 0.5) * 0.4 * speed,
    color: palette[Math.floor(rng() * palette.length)],
    shapeType: Math.floor(rng() * 3),
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.1);
    const cx = W(c) / 2, cy = H(c) / 2;
    const bass = bassRef.current;
    const beatPhase = beat(now, bpm);
    const pulse = 1 + 0.1 * Math.sin(beatPhase * Math.PI * 2) + bass * 0.2;
    for (const s of shapes) {
      s.angle += s.drift * (1 + bass);
      s.dist += s.radialSpeed;
      if (s.dist > 150 || s.dist < 5) s.radialSpeed *= -1;
      const sz = s.size * pulse;
      ctx.fillStyle = hexAlpha(s.color, 0.6 + bass * 0.3);
      for (let f = 0; f < folds; f++) {
        const a = s.angle + (f / folds) * Math.PI * 2;
        const x = cx + Math.cos(a) * s.dist * pulse;
        const y = cy + Math.sin(a) * s.dist * pulse;
        // Mirror
        const aMirror = -s.angle + (f / folds) * Math.PI * 2;
        const xm = cx + Math.cos(aMirror) * s.dist * pulse;
        const ym = cy + Math.sin(aMirror) * s.dist * pulse;
        if (s.shapeType === 0) {
          ctx.beginPath(); ctx.arc(x, y, sz, 0, Math.PI * 2); ctx.fill();
          ctx.beginPath(); ctx.arc(xm, ym, sz, 0, Math.PI * 2); ctx.fill();
        } else if (s.shapeType === 1) {
          ctx.fillRect(x - sz/2, y - sz/2, sz, sz);
          ctx.fillRect(xm - sz/2, ym - sz/2, sz, sz);
        } else {
          ctx.beginPath();
          ctx.moveTo(x, y - sz); ctx.lineTo(x + sz, y + sz); ctx.lineTo(x - sz, y + sz);
          ctx.fill();
          ctx.beginPath();
          ctx.moveTo(xm, ym - sz); ctx.lineTo(xm + sz, ym + sz); ctx.lineTo(xm - sz, ym + sz);
          ctx.fill();
        }
      }
    }
  };
}

// ── 21. Terrain: wireframe mountains ──────────────────────────────
function terrain(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const rows = 30, cols = 40;
  const phaseOff = (seed % 10) * 0.5;
  return (ctx, now) => {
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, W(c), H(c));
    const w = W(c), h = H(c), bass = bassRef.current;
    const t = now * 0.0005 * speed + phaseOff;
    const cellW = w / cols, cellH = h / rows * 0.6;
    for (let r = 0; r < rows; r++) {
      ctx.beginPath();
      ctx.strokeStyle = hexAlpha(palette[r % palette.length], 0.4 + (r / rows) * 0.5);
      ctx.lineWidth = 1;
      for (let ci = 0; ci <= cols; ci++) {
        const x = ci * cellW;
        const baseY = h * 0.3 + r * cellH;
        const elevation = (Math.sin(ci * 0.3 + t + r * 0.2) + Math.sin(ci * 0.15 - t * 0.7)) * (20 + bass * 40);
        const beatBump = Math.sin(beat(now, bpm) * Math.PI * 2) * 5;
        const y = baseY - elevation - beatBump;
        if (ci === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  };
}

// ── 22. Tunnel: zooming perspective rings ─────────────────────────
function tunnel(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const ringCount = 20;
  const rng = seededRandom(seed);
  const rings = Array.from({ length: ringCount }, (_, i) => ({
    z: i / ringCount, color: palette[Math.floor(rng() * palette.length)],
    sides: 4 + (seed % 5),
  }));
  return (ctx, now) => {
    ctx.fillStyle = 'rgba(3,7,18,0.2)'; ctx.fillRect(0, 0, W(c), H(c));
    const cx = W(c) / 2, cy = H(c) / 2, bass = bassRef.current;
    const zSpeed = (0.005 + bass * 0.015) * speed;
    const beatPhase = beat(now, bpm);
    for (const r of rings) {
      r.z -= zSpeed;
      if (r.z <= 0.05) r.z = 1;
      const scale = 1 / r.z;
      const sz = (30 + bass * 20) * scale;
      const rot = now * 0.0003 * speed + r.z * 2;
      ctx.strokeStyle = hexAlpha(r.color, (1 - r.z) * 0.7);
      ctx.lineWidth = (1 - r.z) * 3 + Math.sin(beatPhase * Math.PI * 2) * 1;
      ctx.beginPath();
      for (let i = 0; i <= r.sides; i++) {
        const a = (i / r.sides) * Math.PI * 2 + rot;
        const x = cx + Math.cos(a) * sz, y = cy + Math.sin(a) * sz;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.closePath(); ctx.stroke();
    }
  };
}

// ── 23. Galaxy: rotating particle cloud ───────────────────────────
function galaxy(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bassRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const stars = Array.from({ length: Math.min(count, 500) }, () => {
    const arm = Math.floor(rng() * 3);
    const dist = rng() * 150;
    const offset = rng() * 0.4 - 0.2;
    return { arm, dist, offset, color: palette[Math.floor(rng() * palette.length)], size: 0.5 + rng() * 2 };
  });
  return (ctx, now) => {
    fade(ctx, c, 0.06);
    const cx = W(c) / 2, cy = H(c) / 2, bass = bassRef.current;
    const t = now * 0.0002 * speed;
    for (const s of stars) {
      const baseAngle = (s.arm / 3) * Math.PI * 2 + s.dist * 0.015 + t;
      const angle = baseAngle + s.offset;
      const d = s.dist * (1 + bass * 0.3);
      const x = cx + Math.cos(angle) * d;
      const y = cy + Math.sin(angle) * d * 0.6;
      ctx.fillStyle = hexAlpha(s.color, 0.5 + bass * 0.4);
      ctx.beginPath(); ctx.arc(x, y, s.size + bass, 0, Math.PI * 2); ctx.fill();
    }
  };
}

// ── 24. Ripple: concentric water ripples ──────────────────────────
function ripple(c: HTMLCanvasElement, palette: string[], speed: number, _bpm: number, bassRef: AudioRef, onsetRef: AudioRef): RenderFn {
  const waves: Array<{ x: number; y: number; r: number; alpha: number; color: string }> = [];
  let prevOnset = 0;
  return (ctx, _now) => {
    fade(ctx, c, 0.1);
    const onset = onsetRef.current, bass = bassRef.current;
    if (onset > 0 && prevOnset === 0) {
      waves.push({ x: Math.random() * W(c), y: Math.random() * H(c), r: 0, alpha: 1, color: palette[Math.floor(Math.random() * palette.length)] });
    }
    prevOnset = onset;
    for (let i = waves.length - 1; i >= 0; i--) {
      const w = waves[i];
      w.r += (3 + bass * 5) * speed;
      w.alpha -= 0.008;
      if (w.alpha <= 0) { waves.splice(i, 1); continue; }
      ctx.strokeStyle = hexAlpha(w.color, w.alpha);
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(w.x, w.y, w.r, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.arc(w.x, w.y, w.r * 0.7, 0, Math.PI * 2); ctx.stroke();
    }
  };
}

// ── 25. Lissajous: parametric X-Y curves ─────────────────────────
function lissajous(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const a = 2 + (seed % 5), b = 3 + (seed % 4);
  return (ctx, now) => {
    fade(ctx, c, 0.08);
    const w = W(c), h = H(c), bass = bassRef.current;
    const t = now * 0.001 * speed;
    const amp = Math.min(w, h) * 0.35 * (1 + bass * 0.3);
    const beatV = Math.sin(beat(now, bpm) * Math.PI * 2);
    ctx.beginPath();
    ctx.strokeStyle = hexAlpha(palette[0], 0.8);
    ctx.lineWidth = 2 + bass * 2;
    for (let i = 0; i <= 360; i++) {
      const th = (i / 360) * Math.PI * 2;
      const x = w / 2 + Math.sin(a * th + t) * amp;
      const y = h / 2 + Math.sin(b * th + t * 0.7 + beatV * 0.3) * amp * 0.8;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
    // Second curve offset
    ctx.beginPath();
    ctx.strokeStyle = hexAlpha(palette[1 % palette.length], 0.5);
    ctx.lineWidth = 1.5;
    for (let i = 0; i <= 360; i++) {
      const th = (i / 360) * Math.PI * 2;
      const x = w / 2 + Math.sin(a * th + t + 0.5) * amp * 0.9;
      const y = h / 2 + Math.sin(b * th + t * 0.7 + 0.5) * amp * 0.7;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
  };
}

// ── 26. Spirograph: epitrochoid curves ────────────────────────────
function spirograph(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const R = 80 + (seed % 40), r0 = 30 + (seed % 20), d = 40 + (seed % 30);
  return (ctx, now) => {
    fade(ctx, c, 0.04);
    const cx = W(c) / 2, cy = H(c) / 2, bass = bassRef.current;
    const t = now * 0.0003 * speed;
    const sc = 1 + bass * 0.3 + 0.1 * Math.sin(beat(now, bpm) * Math.PI * 2);
    ctx.beginPath();
    ctx.strokeStyle = hexAlpha(palette[0], 0.7);
    ctx.lineWidth = 1.5;
    for (let i = 0; i <= 1000; i++) {
      const th = (i / 1000) * Math.PI * 20 + t;
      const x = cx + ((R - r0) * Math.cos(th) + d * Math.cos(((R - r0) / r0) * th)) * sc;
      const y = cy + ((R - r0) * Math.sin(th) - d * Math.sin(((R - r0) / r0) * th)) * sc;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
  };
}

// ── 27. Metaballs: merging blobs ──────────────────────────────────
function metaballs(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bassRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const blobs = Array.from({ length: Math.min(count, 8) }, () => ({
    x: rng() * W(c), y: rng() * H(c), vx: (rng() - 0.5) * 2 * speed, vy: (rng() - 0.5) * 2 * speed,
    r: 40 + rng() * 60, color: palette[Math.floor(rng() * palette.length)],
  }));
  return (ctx, _now) => {
    fade(ctx, c, 0.08);
    const bass = bassRef.current;
    for (const b of blobs) {
      b.x += b.vx * (1 + bass); b.y += b.vy * (1 + bass);
      if (b.x < 0 || b.x > W(c)) b.vx *= -1;
      if (b.y < 0 || b.y > H(c)) b.vy *= -1;
      const rad = b.r * (1 + bass * 0.5);
      const grd = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, rad);
      grd.addColorStop(0, hexAlpha(b.color, 0.5 + bass * 0.3));
      grd.addColorStop(0.7, hexAlpha(b.color, 0.15));
      grd.addColorStop(1, hexAlpha(b.color, 0));
      ctx.fillStyle = grd;
      ctx.beginPath(); ctx.arc(b.x, b.y, rad, 0, Math.PI * 2); ctx.fill();
    }
  };
}

// ── 28. Fractal Tree: recursive branching ─────────────────────────
function fractalTree(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, onsetRef: AudioRef, seed: number): RenderFn {
  const baseAngle = -Math.PI / 2;
  const branchAngle = 0.4 + (seed % 5) * 0.08;
  return (ctx, now) => {
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, W(c), H(c));
    const bass = bassRef.current, onset = onsetRef.current;
    const beatV = beat(now, bpm);
    const sway = Math.sin(now * 0.001 * speed) * 0.1 + onset * 0.15;
    const drawBranch = (x: number, y: number, angle: number, len: number, depth: number) => {
      if (depth > 10 || len < 3) return;
      const x2 = x + Math.cos(angle) * len;
      const y2 = y + Math.sin(angle) * len;
      ctx.strokeStyle = hexAlpha(palette[depth % palette.length], 0.5 + bass * 0.4);
      ctx.lineWidth = Math.max(0.5, (10 - depth) * 0.6);
      ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x2, y2); ctx.stroke();
      const nextLen = len * (0.7 + beatV * 0.05 + bass * 0.05);
      drawBranch(x2, y2, angle - branchAngle + sway, nextLen, depth + 1);
      drawBranch(x2, y2, angle + branchAngle + sway, nextLen, depth + 1);
    };
    drawBranch(W(c) / 2, H(c) * 0.9, baseAngle, 60 + bass * 20, 0);
  };
}

// ── 29. Circular Spectrum: radial frequency bars ──────────────────
function circularSpectrum(c: HTMLCanvasElement, palette: string[], bpm: number, bassRef: AudioRef, analyserRef: React.RefObject<AnalyserNode | null>): RenderFn {
  const smoothed = new Float32Array(64);
  return (ctx, now) => {
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, W(c), H(c));
    const cx = W(c) / 2, cy = H(c) / 2, bass = bassRef.current;
    const analyser = analyserRef.current;
    const data = new Uint8Array(analyser?.frequencyBinCount ?? 128);
    if (analyser) analyser.getByteFrequencyData(data);
    const barCount = 64, baseR = 60 + bass * 20;
    const beatPulse = 1 + 0.15 * Math.sin(beat(now, bpm) * Math.PI * 2);
    for (let i = 0; i < barCount; i++) {
      const raw = analyser ? data[Math.floor(i * data.length / barCount)] / 255 : 0.3 * Math.abs(Math.sin(now * 0.002 + i * 0.3));
      smoothed[i] += (raw - smoothed[i]) * 0.3;
      const angle = (i / barCount) * Math.PI * 2 - Math.PI / 2;
      const barH = smoothed[i] * 100 * beatPulse;
      const x1 = cx + Math.cos(angle) * baseR, y1 = cy + Math.sin(angle) * baseR;
      const x2 = cx + Math.cos(angle) * (baseR + barH), y2 = cy + Math.sin(angle) * (baseR + barH);
      ctx.strokeStyle = palette[i % palette.length];
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }
  };
}

// ── 30. Wave Terrain: 3D perspective grid ─────────────────────────
function waveTerrain(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const gridX = 30, gridZ = 20, phOff = (seed % 10) * 0.4;
  return (ctx, now) => {
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, W(c), H(c));
    const w = W(c), h = H(c), bass = bassRef.current;
    const t = now * 0.0004 * speed + phOff;
    const beatV = Math.sin(beat(now, bpm) * Math.PI * 2);
    for (let z = gridZ; z >= 0; z--) {
      ctx.beginPath();
      const zFrac = z / gridZ;
      const perspY = h * 0.3 + zFrac * h * 0.5;
      const perspScale = 0.3 + zFrac * 0.7;
      ctx.strokeStyle = hexAlpha(palette[z % palette.length], 0.3 + zFrac * 0.6);
      ctx.lineWidth = 1;
      for (let x = 0; x <= gridX; x++) {
        const xFrac = x / gridX;
        const px = w * 0.1 + xFrac * w * 0.8;
        const elev = (Math.sin(xFrac * 6 + t + z * 0.3) + Math.cos(xFrac * 3 - t * 0.5)) * (15 + bass * 30) * perspScale + beatV * 5;
        const py = perspY - elev;
        if (x === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      }
      ctx.stroke();
    }
  };
}

// ── 31. Interference: overlapping wave patterns ───────────────────
function interference(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const step = 6;
  const sources = [{ x: 0.3, y: 0.3 }, { x: 0.7, y: 0.7 }, { x: 0.5, y: 0.2 }];
  const phOff = (seed % 10) * 0.5;
  return (ctx, now) => {
    const w = W(c), h = H(c), bass = bassRef.current;
    const t = now * 0.002 * speed + phOff;
    const beatV = beat(now, bpm);
    for (let x = 0; x < w; x += step) {
      for (let y = 0; y < h; y += step) {
        let v = 0;
        for (const s of sources) {
          const dx = x - s.x * w, dy = y - s.y * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          v += Math.sin(dist * 0.05 - t + bass * 2);
        }
        v = (v / sources.length + 1) / 2 + beatV * 0.1;
        const idx = Math.floor(v * (palette.length - 1));
        ctx.fillStyle = hexAlpha(palette[Math.max(0, Math.min(idx, palette.length - 1))], 0.8);
        ctx.fillRect(x, y, step, step);
      }
    }
  };
}

// ── 32. Pixel Sort: sorted color columns ──────────────────────────
function pixelSort(c: HTMLCanvasElement, palette: string[], speed: number, bassRef: AudioRef, onsetRef: AudioRef, seed: number): RenderFn {
  const colW = 4, rng = seededRandom(seed);
  const cols = Math.ceil(800 / colW);
  const heights = Array.from({ length: cols }, () => rng());
  return (ctx, _now) => {
    fade(ctx, c, 0.15);
    const w = W(c), h = H(c), bass = bassRef.current, onset = onsetRef.current;
    for (let i = 0; i < cols; i++) {
      heights[i] += (Math.random() - 0.5) * 0.05 * speed * (1 + onset * 3);
      heights[i] = Math.max(0.05, Math.min(1, heights[i]));
      const barH = heights[i] * h * (0.5 + bass * 0.5);
      const x = (i / cols) * w;
      ctx.fillStyle = hexAlpha(palette[i % palette.length], 0.6 + bass * 0.3);
      ctx.fillRect(x, h - barH, (w / cols) - 1, barH);
    }
  };
}

// ── 33. Neon Grid: perspective grid with glow ─────────────────────
function neonGrid(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, _seed: number): RenderFn {
  return (ctx, now) => {
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, W(c), H(c));
    const w = W(c), h = H(c), bass = bassRef.current;
    const t = now * 0.001 * speed;
    const gridLines = 15;
    const horizon = h * 0.4;
    const beatV = Math.sin(beat(now, bpm) * Math.PI * 2);
    // Horizontal lines (perspective)
    ctx.shadowBlur = 8; ctx.shadowColor = palette[0];
    for (let i = 0; i < gridLines; i++) {
      const frac = (i + (t * 2) % 1) / gridLines;
      const y = horizon + frac * frac * (h - horizon);
      ctx.strokeStyle = hexAlpha(palette[0], 0.3 + frac * 0.5 + bass * 0.2);
      ctx.lineWidth = 1 + frac * 2;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }
    // Vertical lines converging to horizon
    for (let i = -8; i <= 8; i++) {
      const topX = w / 2 + i * 20;
      const botX = w / 2 + i * (w / 8);
      ctx.strokeStyle = hexAlpha(palette[1 % palette.length], 0.3 + bass * 0.3);
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(topX, horizon); ctx.lineTo(botX, h); ctx.stroke();
    }
    ctx.shadowBlur = 0;
    // Sun glow
    const sunR = 30 + bass * 15 + beatV * 5;
    const grd = ctx.createRadialGradient(w / 2, horizon, 0, w / 2, horizon, sunR * 3);
    grd.addColorStop(0, hexAlpha(palette[2 % palette.length], 0.6));
    grd.addColorStop(1, hexAlpha(palette[2 % palette.length], 0));
    ctx.fillStyle = grd;
    ctx.beginPath(); ctx.arc(w / 2, horizon, sunR * 3, 0, Math.PI * 2); ctx.fill();
  };
}

// ── 34. Pendulum: swinging weighted pendulums ─────────────────────
function pendulum(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const pends = Array.from({ length: Math.min(count, 15) }, (_, i) => ({
    length: 60 + rng() * 100, phase: rng() * Math.PI * 2,
    freq: 0.5 + rng() * 1.5, color: palette[i % palette.length],
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.12);
    const cx = W(c) / 2, bass = bassRef.current;
    const t = now * 0.001 * speed;
    const beatV = beat(now, bpm);
    for (const p of pends) {
      const angle = Math.sin(t * p.freq + p.phase) * (0.6 + bass * 0.4) + Math.sin(beatV * Math.PI * 2) * 0.1;
      const x = cx + Math.sin(angle) * p.length;
      const y = Math.cos(angle) * p.length + 10;
      ctx.strokeStyle = hexAlpha(p.color, 0.4);
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(cx, 10); ctx.lineTo(x, y); ctx.stroke();
      ctx.fillStyle = hexAlpha(p.color, 0.8 + bass * 0.2);
      ctx.beginPath(); ctx.arc(x, y, 5 + bass * 4, 0, Math.PI * 2); ctx.fill();
    }
  };
}

// ── 35. Bubbles: rising + popping ─────────────────────────────────
function bubbles(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bassRef: AudioRef, onsetRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const bubs = Array.from({ length: Math.min(count, 60) }, () => ({
    x: rng() * W(c), y: rng() * H(c), r: 5 + rng() * 20,
    vy: -(0.3 + rng() * 1) * speed, vx: (rng() - 0.5) * 0.5,
    color: palette[Math.floor(rng() * palette.length)],
  }));
  return (ctx, _now) => {
    fade(ctx, c, 0.1);
    const bass = bassRef.current, onset = onsetRef.current;
    for (const b of bubs) {
      b.y += b.vy * (1 + bass * 2);
      b.x += b.vx + Math.sin(b.y * 0.02) * 0.5;
      if (b.y < -b.r || (onset > 0 && Math.random() < 0.1)) {
        b.y = H(c) + b.r; b.x = Math.random() * W(c); b.r = 5 + Math.random() * 20;
      }
      ctx.strokeStyle = hexAlpha(b.color, 0.5 + bass * 0.3);
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(b.x, b.y, b.r * (1 + bass * 0.2), 0, Math.PI * 2); ctx.stroke();
      // Highlight
      ctx.fillStyle = hexAlpha(b.color, 0.15);
      ctx.beginPath(); ctx.arc(b.x - b.r * 0.3, b.y - b.r * 0.3, b.r * 0.3, 0, Math.PI * 2); ctx.fill();
    }
  };
}

// ── 36. Constellation: connected star network ─────────────────────
function constellation(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bassRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const nodes = Array.from({ length: Math.min(count, 80) }, () => ({
    x: rng() * W(c), y: rng() * H(c),
    vx: (rng() - 0.5) * 0.5 * speed, vy: (rng() - 0.5) * 0.5 * speed,
    color: palette[Math.floor(rng() * palette.length)], size: 1 + rng() * 2,
  }));
  const connectDist = 100;
  return (ctx, _now) => {
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, W(c), H(c));
    const bass = bassRef.current;
    for (const n of nodes) {
      n.x += n.vx * (1 + bass); n.y += n.vy * (1 + bass);
      if (n.x < 0 || n.x > W(c)) n.vx *= -1;
      if (n.y < 0 || n.y > H(c)) n.vy *= -1;
    }
    // Lines
    const dist = connectDist + bass * 50;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < dist) {
          ctx.strokeStyle = hexAlpha(nodes[i].color, (1 - d / dist) * 0.4);
          ctx.lineWidth = 0.5;
          ctx.beginPath(); ctx.moveTo(nodes[i].x, nodes[i].y); ctx.lineTo(nodes[j].x, nodes[j].y); ctx.stroke();
        }
      }
    }
    for (const n of nodes) {
      ctx.fillStyle = hexAlpha(n.color, 0.7 + bass * 0.3);
      ctx.beginPath(); ctx.arc(n.x, n.y, n.size + bass * 2, 0, Math.PI * 2); ctx.fill();
    }
  };
}

// ── 37. Cube Field: 3D cubes zooming past ─────────────────────────
function cubeField(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const cubes = Array.from({ length: 30 }, () => ({
    x: (rng() - 0.5) * 2, y: (rng() - 0.5) * 2, z: rng(),
    color: palette[Math.floor(rng() * palette.length)],
  }));
  return (ctx, now) => {
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, W(c), H(c));
    const w = W(c), h = H(c), cx = w / 2, cy = h / 2, bass = bassRef.current;
    const beatV = beat(now, bpm);
    const zSpeed = (0.008 + bass * 0.02) * speed;
    for (const cu of cubes) {
      cu.z -= zSpeed;
      if (cu.z <= 0.05) { cu.z = 1; cu.x = (Math.random() - 0.5) * 2; cu.y = (Math.random() - 0.5) * 2; }
      const scale = 1 / cu.z;
      const sx = cx + cu.x * scale * w * 0.3;
      const sy = cy + cu.y * scale * h * 0.3;
      const sz = (8 + bass * 8) * scale;
      const rot = now * 0.001 + cu.z * 5;
      ctx.save(); ctx.translate(sx, sy); ctx.rotate(rot + beatV * 0.3);
      ctx.strokeStyle = hexAlpha(cu.color, (1 - cu.z) * 0.8);
      ctx.lineWidth = 1.5;
      ctx.strokeRect(-sz / 2, -sz / 2, sz, sz);
      ctx.restore();
    }
  };
}

// ── 38. Frequency Spiral: spectral data on spiral path ────────────
function frequencySpiral(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, analyserRef: React.RefObject<AnalyserNode | null>): RenderFn {
  const smoothed = new Float32Array(64);
  return (ctx, now) => {
    fade(ctx, c, 0.2);
    const cx = W(c) / 2, cy = H(c) / 2, bass = bassRef.current;
    const analyser = analyserRef.current;
    const data = new Uint8Array(analyser?.frequencyBinCount ?? 128);
    if (analyser) analyser.getByteFrequencyData(data);
    const t = now * 0.0005 * speed;
    const beatV = beat(now, bpm);
    const bins = 64;
    for (let i = 0; i < bins; i++) {
      const raw = analyser ? data[Math.floor(i * data.length / bins)] / 255 : 0.3 * Math.abs(Math.sin(now * 0.002 + i * 0.2));
      smoothed[i] += (raw - smoothed[i]) * 0.3;
      const angle = (i / bins) * Math.PI * 6 + t;
      const baseDist = 20 + (i / bins) * 120;
      const dist = baseDist + smoothed[i] * 50 * (1 + 0.15 * Math.sin(beatV * Math.PI * 2));
      const x = cx + Math.cos(angle) * dist;
      const y = cy + Math.sin(angle) * dist;
      const sz = 2 + smoothed[i] * 5 + bass * 2;
      ctx.fillStyle = hexAlpha(palette[i % palette.length], 0.6 + smoothed[i] * 0.4);
      ctx.beginPath(); ctx.arc(x, y, sz, 0, Math.PI * 2); ctx.fill();
    }
  };
}

// ── 39. Smoke Trails: flowing ribbon particles ────────────────────
function smokeTrails(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bassRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const trails = Array.from({ length: Math.min(count, 20) }, () => ({
    points: Array.from({ length: 20 }, () => ({ x: rng() * W(c), y: rng() * H(c) })),
    color: palette[Math.floor(rng() * palette.length)],
    vx: (rng() - 0.5) * 2 * speed, vy: (rng() - 0.5) * speed,
  }));
  return (ctx, now) => {
    fade(ctx, c, 0.06);
    const bass = bassRef.current;
    const t = now * 0.001;
    for (const tr of trails) {
      const head = tr.points[0];
      head.x += (tr.vx + Math.sin(t + head.y * 0.01) * 2) * (1 + bass);
      head.y += (tr.vy + Math.cos(t + head.x * 0.01)) * (1 + bass);
      if (head.x < 0 || head.x > W(c)) tr.vx *= -1;
      if (head.y < 0 || head.y > H(c)) tr.vy *= -1;
      for (let i = tr.points.length - 1; i > 0; i--) {
        tr.points[i].x += (tr.points[i - 1].x - tr.points[i].x) * 0.3;
        tr.points[i].y += (tr.points[i - 1].y - tr.points[i].y) * 0.3;
      }
      ctx.beginPath();
      ctx.strokeStyle = hexAlpha(tr.color, 0.5 + bass * 0.3);
      ctx.lineWidth = 3 + bass * 3;
      ctx.moveTo(tr.points[0].x, tr.points[0].y);
      for (let i = 1; i < tr.points.length; i++) {
        ctx.lineTo(tr.points[i].x, tr.points[i].y);
      }
      ctx.stroke();
    }
  };
}

// ── 40. Bouncing Bars: gravity bars that bounce on beat ───────────
function bouncingBars(c: HTMLCanvasElement, palette: string[], bpm: number, bassRef: AudioRef, onsetRef: AudioRef): RenderFn {
  const barCount = 32;
  const heights = new Float32Array(barCount);
  const velocities = new Float32Array(barCount);
  return (ctx, now) => {
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, W(c), H(c));
    const w = W(c), h = H(c), bass = bassRef.current, onset = onsetRef.current;
    const barW = w / barCount - 2;
    const beatV = beat(now, bpm);
    for (let i = 0; i < barCount; i++) {
      if (onset > 0) velocities[i] = -(5 + Math.random() * 10 + bass * 8);
      velocities[i] += 0.4; // gravity
      heights[i] += velocities[i];
      if (heights[i] > 0) { heights[i] = 0; velocities[i] *= -0.5; }
      const barH = Math.abs(heights[i]) + 5 + bass * 10;
      ctx.fillStyle = hexAlpha(palette[i % palette.length], 0.7 + 0.1 * Math.sin(beatV * Math.PI * 2));
      ctx.fillRect(i * (barW + 2) + 1, h - barH, barW, barH);
    }
  };
}

// ── 41. Wave Mesh: connected oscillating dots ─────────────────────
function waveMesh(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const cols = 20, rows = 12, phOff = (seed % 10) * 0.3;
  return (ctx, now) => {
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, W(c), H(c));
    const w = W(c), h = H(c), bass = bassRef.current;
    const t = now * 0.001 * speed + phOff;
    const beatV = beat(now, bpm);
    const pts: { x: number; y: number }[][] = [];
    for (let r = 0; r < rows; r++) {
      pts[r] = [];
      for (let ci = 0; ci < cols; ci++) {
        const bx = (ci + 0.5) * (w / cols), by = (r + 0.5) * (h / rows);
        const off = Math.sin(ci * 0.5 + t + r * 0.3) * (8 + bass * 15) + Math.sin(beatV * Math.PI * 2) * 3;
        pts[r][ci] = { x: bx, y: by + off };
      }
    }
    // Lines
    for (let r = 0; r < rows; r++) {
      for (let ci = 0; ci < cols; ci++) {
        const p = pts[r][ci];
        ctx.fillStyle = hexAlpha(palette[(r + ci) % palette.length], 0.7 + bass * 0.3);
        ctx.beginPath(); ctx.arc(p.x, p.y, 2 + bass * 2, 0, Math.PI * 2); ctx.fill();
        if (ci < cols - 1) {
          ctx.strokeStyle = hexAlpha(palette[(r + ci) % palette.length], 0.25);
          ctx.lineWidth = 0.5;
          ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(pts[r][ci + 1].x, pts[r][ci + 1].y); ctx.stroke();
        }
        if (r < rows - 1) {
          ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(pts[r + 1][ci].x, pts[r + 1][ci].y); ctx.stroke();
        }
      }
    }
  };
}

// ── 42. Comet Trails: streaking particles with tail ───────────────
function cometTrails(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bassRef: AudioRef, onsetRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const comets = Array.from({ length: Math.min(count, 15) }, () => ({
    x: rng() * W(c), y: rng() * H(c),
    angle: rng() * Math.PI * 2, speed: (2 + rng() * 4) * speed,
    color: palette[Math.floor(rng() * palette.length)],
    trail: [] as { x: number; y: number }[],
  }));
  return (ctx, _now) => {
    fade(ctx, c, 0.08);
    const bass = bassRef.current, onset = onsetRef.current;
    for (const cm of comets) {
      if (onset > 0 && Math.random() < 0.3) cm.angle += (Math.random() - 0.5) * 1.5;
      cm.x += Math.cos(cm.angle) * cm.speed * (1 + bass * 2);
      cm.y += Math.sin(cm.angle) * cm.speed * (1 + bass * 2);
      if (cm.x < 0 || cm.x > W(c) || cm.y < 0 || cm.y > H(c)) {
        cm.x = W(c) / 2; cm.y = H(c) / 2; cm.angle = Math.random() * Math.PI * 2;
      }
      cm.trail.push({ x: cm.x, y: cm.y });
      if (cm.trail.length > 30) cm.trail.shift();
      for (let i = 0; i < cm.trail.length; i++) {
        const alpha = (i / cm.trail.length) * 0.6;
        const sz = (i / cm.trail.length) * (3 + bass * 3);
        ctx.fillStyle = hexAlpha(cm.color, alpha);
        ctx.beginPath(); ctx.arc(cm.trail[i].x, cm.trail[i].y, sz, 0, Math.PI * 2); ctx.fill();
      }
    }
  };
}

// ── 43. Heartbeat: pulsing heart shape ────────────────────────────
function heartbeat(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, onsetRef: AudioRef): RenderFn {
  let pulseSize = 1;
  let prevOnset = 0;
  return (ctx, now) => {
    fade(ctx, c, 0.15);
    const cx = W(c) / 2, cy = H(c) / 2, bass = bassRef.current, onset = onsetRef.current;
    if (onset > 0 && prevOnset === 0) pulseSize = 1.4 + bass * 0.3;
    prevOnset = onset;
    pulseSize += (1 - pulseSize) * 0.05;
    const beatV = beat(now, bpm);
    const scale = (50 + bass * 20) * pulseSize * (1 + 0.1 * Math.sin(beatV * Math.PI * 2));
    const t = now * 0.001 * speed;
    ctx.beginPath();
    ctx.fillStyle = hexAlpha(palette[0], 0.6 + bass * 0.3);
    for (let i = 0; i <= 360; i++) {
      const a = (i / 360) * Math.PI * 2;
      const r = scale * (Math.sin(a) * Math.sqrt(Math.abs(Math.cos(a))) / (Math.sin(a) + 1.4) - 2 * Math.sin(a) + 2);
      const x = cx + Math.cos(a + t * 0.2) * r;
      const y = cy - Math.sin(a + t * 0.2) * r + scale * 0.5;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.fill();
  };
}

// ── 44. Radar: rotating sweep line ────────────────────────────────
function radar(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const rng = seededRandom(seed);
  const blips: { angle: number; dist: number; color: string }[] =
    Array.from({ length: 20 }, () => ({ angle: rng() * Math.PI * 2, dist: 30 + rng() * 120, color: palette[Math.floor(rng() * palette.length)] }));
  return (ctx, now) => {
    fade(ctx, c, 0.06);
    const cx = W(c) / 2, cy = H(c) / 2, bass = bassRef.current;
    const t = now * 0.001 * speed;
    const sweepAngle = t % (Math.PI * 2);
    const maxR = Math.min(W(c), H(c)) * 0.42;
    // Grid circles
    for (let i = 1; i <= 4; i++) {
      ctx.strokeStyle = hexAlpha(palette[0], 0.15);
      ctx.lineWidth = 0.5;
      ctx.beginPath(); ctx.arc(cx, cy, maxR * i / 4, 0, Math.PI * 2); ctx.stroke();
    }
    // Sweep
    const grd = ctx.createConicGradient(sweepAngle, cx, cy);
    grd.addColorStop(0, hexAlpha(palette[0], 0.4 + bass * 0.3));
    grd.addColorStop(0.15, hexAlpha(palette[0], 0));
    grd.addColorStop(1, hexAlpha(palette[0], 0));
    ctx.fillStyle = grd;
    ctx.beginPath(); ctx.arc(cx, cy, maxR, 0, Math.PI * 2); ctx.fill();
    // Blips
    const beatV = beat(now, bpm);
    for (const b of blips) {
      const angleDiff = ((sweepAngle - b.angle) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
      if (angleDiff < 0.3) {
        const alpha = (0.3 - angleDiff) / 0.3;
        const sz = 3 + bass * 3 + Math.sin(beatV * Math.PI * 2) * 1;
        ctx.fillStyle = hexAlpha(b.color, alpha * 0.8);
        ctx.beginPath(); ctx.arc(cx + Math.cos(b.angle) * b.dist, cy + Math.sin(b.angle) * b.dist, sz, 0, Math.PI * 2); ctx.fill();
      }
    }
  };
}

// ── 45. Vinyl: spinning record ────────────────────────────────────
function vinyl(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, _seed: number): RenderFn {
  return (ctx, now) => {
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, W(c), H(c));
    const cx = W(c) / 2, cy = H(c) / 2, bass = bassRef.current;
    const maxR = Math.min(W(c), H(c)) * 0.42;
    const rot = now * 0.001 * speed * (1 + bass * 0.5);
    const beatV = beat(now, bpm);
    // Grooves
    for (let r = 20; r < maxR; r += 4) {
      const groove = r + Math.sin(rot + r * 0.1) * (1 + bass * 2);
      ctx.strokeStyle = hexAlpha(palette[Math.floor(r / 20) % palette.length], 0.15 + bass * 0.15 + (r === Math.floor(maxR * beatV) ? 0.4 : 0));
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(cx, cy, groove, 0, Math.PI * 2); ctx.stroke();
    }
    // Label
    const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, 25);
    grd.addColorStop(0, palette[0]);
    grd.addColorStop(1, hexAlpha(palette[1 % palette.length], 0.8));
    ctx.fillStyle = grd;
    ctx.beginPath(); ctx.arc(cx, cy, 25 + bass * 5, 0, Math.PI * 2); ctx.fill();
    // Spindle
    ctx.fillStyle = '#111';
    ctx.beginPath(); ctx.arc(cx, cy, 4, 0, Math.PI * 2); ctx.fill();
  };
}

// ── 46. Equalizer Circle: circular bar equalizer ──────────────────
function equalizerCircle(c: HTMLCanvasElement, palette: string[], bpm: number, bassRef: AudioRef, analyserRef: React.RefObject<AnalyserNode | null>): RenderFn {
  const smoothed = new Float32Array(32);
  return (ctx, now) => {
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, W(c), H(c));
    const cx = W(c) / 2, cy = H(c) / 2, bass = bassRef.current;
    const analyser = analyserRef.current;
    const data = new Uint8Array(analyser?.frequencyBinCount ?? 128);
    if (analyser) analyser.getByteFrequencyData(data);
    const bars = 32, baseR = 50 + bass * 15;
    const beatP = 1 + 0.1 * Math.sin(beat(now, bpm) * Math.PI * 2);
    for (let i = 0; i < bars; i++) {
      const raw = analyser ? data[Math.floor(i * data.length / bars)] / 255 : 0.3;
      smoothed[i] += (raw - smoothed[i]) * 0.3;
      const angle = (i / bars) * Math.PI * 2 - Math.PI / 2;
      const barH = smoothed[i] * 80 * beatP;
      const barW = (Math.PI * 2 / bars) * 0.7;
      ctx.fillStyle = hexAlpha(palette[i % palette.length], 0.7 + smoothed[i] * 0.3);
      ctx.beginPath();
      ctx.arc(cx, cy, baseR, angle - barW / 2, angle + barW / 2);
      ctx.arc(cx, cy, baseR + barH, angle + barW / 2, angle - barW / 2, true);
      ctx.fill();
    }
  };
}

// ── 47. Neon Tunnel: zooming neon rings ───────────────────────────
function neonTunnel(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, _seed: number): RenderFn {
  return (ctx, now) => {
    ctx.fillStyle = 'rgba(3,7,18,0.15)'; ctx.fillRect(0, 0, W(c), H(c));
    const cx = W(c) / 2, cy = H(c) / 2, bass = bassRef.current;
    const t = now * 0.002 * speed;
    const beatV = beat(now, bpm);
    const maxR = Math.max(W(c), H(c)) * 0.6;
    ctx.shadowBlur = 12;
    for (let i = 0; i < 15; i++) {
      const frac = ((i / 15 + t * 0.1) % 1);
      const r = frac * maxR;
      const alpha = (1 - frac) * 0.6 + bass * 0.2;
      const color = palette[i % palette.length];
      ctx.shadowColor = color;
      ctx.strokeStyle = hexAlpha(color, alpha);
      ctx.lineWidth = 2 + (1 - frac) * 4 + Math.sin(beatV * Math.PI * 2) * 1;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.shadowBlur = 0;
  };
}

// ── 48. Particle Fountain: upward particle spray ──────────────────
function particleFountain(c: HTMLCanvasElement, palette: string[], count: number, speed: number, bassRef: AudioRef, onsetRef: AudioRef): RenderFn {
  type P = { x: number; y: number; vx: number; vy: number; color: string; alpha: number; size: number };
  const particles: P[] = [];
  let prevOnset = 0;
  return (ctx, _now) => {
    fade(ctx, c, 0.1);
    const bass = bassRef.current, onset = onsetRef.current;
    // Spawn
    const spawnCount = onset > 0 && prevOnset === 0 ? 20 + Math.floor(bass * 20) : 2;
    prevOnset = onset;
    const cx = W(c) / 2;
    for (let i = 0; i < spawnCount && particles.length < Math.min(count, 500); i++) {
      particles.push({
        x: cx + (Math.random() - 0.5) * 20, y: H(c),
        vx: (Math.random() - 0.5) * 3 * speed, vy: -(4 + Math.random() * 6 + bass * 4) * speed,
        color: palette[Math.floor(Math.random() * palette.length)], alpha: 1, size: 1.5 + Math.random() * 2,
      });
    }
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.x += p.vx; p.y += p.vy; p.vy += 0.12; p.alpha -= 0.008;
      if (p.alpha <= 0 || p.y > H(c) + 10) { particles.splice(i, 1); continue; }
      ctx.fillStyle = hexAlpha(p.color, p.alpha);
      ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2); ctx.fill();
    }
  };
}

// ── 49. Wormhole: spiraling vortex tunnel ─────────────────────────
function wormhole(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, seed: number): RenderFn {
  const layers = 25, phOff = (seed % 10) * 0.4;
  return (ctx, now) => {
    ctx.fillStyle = 'rgba(3,7,18,0.12)'; ctx.fillRect(0, 0, W(c), H(c));
    const cx = W(c) / 2, cy = H(c) / 2, bass = bassRef.current;
    const t = now * 0.001 * speed + phOff;
    const beatV = beat(now, bpm);
    for (let i = 0; i < layers; i++) {
      const frac = i / layers;
      const r = (10 + frac * 180) * (1 + bass * 0.3);
      const spiralAngle = frac * Math.PI * 4 + t * (1 + frac);
      const wobble = Math.sin(beatV * Math.PI * 2 + i * 0.5) * 5;
      const x = cx + Math.cos(spiralAngle) * wobble;
      const y = cy + Math.sin(spiralAngle) * wobble;
      ctx.strokeStyle = hexAlpha(palette[i % palette.length], 0.3 + (1 - frac) * 0.5);
      ctx.lineWidth = 1 + (1 - frac) * 3;
      ctx.beginPath();
      ctx.ellipse(x, y, r, r * 0.7, spiralAngle * 0.1, 0, Math.PI * 2);
      ctx.stroke();
    }
  };
}

// ── 50. Laser Show: converging laser beams ────────────────────────
function laserShow(c: HTMLCanvasElement, palette: string[], speed: number, bpm: number, bassRef: AudioRef, onsetRef: AudioRef, seed: number): RenderFn {
  const beamCount = 8 + (seed % 8);
  let prevOnset = 0, flash = 0;
  return (ctx, now) => {
    ctx.fillStyle = `rgba(3,7,18,${0.2 + flash * 0.3})`; ctx.fillRect(0, 0, W(c), H(c));
    const w = W(c), h = H(c), bass = bassRef.current, onset = onsetRef.current;
    if (onset > 0 && prevOnset === 0) flash = 1;
    prevOnset = onset;
    flash *= 0.9;
    const t = now * 0.001 * speed;
    const beatV = beat(now, bpm);
    ctx.shadowBlur = 15;
    for (let i = 0; i < beamCount; i++) {
      const angle = (i / beamCount) * Math.PI * 2 + t;
      const len = 200 + bass * 100 + Math.sin(beatV * Math.PI * 2 + i) * 30;
      const sx = w / 2, sy = h * 0.8;
      const ex = sx + Math.cos(angle - Math.PI / 2) * len;
      const ey = sy + Math.sin(angle - Math.PI / 2) * len;
      const color = palette[i % palette.length];
      ctx.shadowColor = color;
      ctx.strokeStyle = hexAlpha(color, 0.5 + bass * 0.4 + flash * 0.3);
      ctx.lineWidth = 2 + bass * 2;
      ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey); ctx.stroke();
    }
    ctx.shadowBlur = 0;
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

function VibeBadge({ vibe }: { vibe: string }) {
  const VIBE_COLORS: Record<string, string> = {
    dark_heavy:       'bg-indigo-900/60 text-indigo-300 border-indigo-700',
    bright_energetic: 'bg-amber-900/60 text-amber-300 border-amber-700',
    warm_deep:        'bg-orange-900/60 text-orange-300 border-orange-700',
    melancholic:      'bg-slate-800/60 text-slate-300 border-slate-600',
    aggressive:       'bg-red-900/60 text-red-300 border-red-700',
    serene:           'bg-teal-900/60 text-teal-300 border-teal-700',
  };
  const cls = VIBE_COLORS[vibe] ?? 'bg-gray-800/60 text-gray-300 border-gray-600';
  return (
    <div className={`rounded-lg px-2 py-1.5 border ${cls}`}>
      <p className="text-xs uppercase tracking-wide opacity-70">Vibe</p>
      <p className="text-sm font-bold truncate">{vibe || '—'}</p>
    </div>
  );
}
