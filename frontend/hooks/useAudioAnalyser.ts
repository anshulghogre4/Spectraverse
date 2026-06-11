'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export type AudioAnalyserState = {
  bassRef: React.MutableRefObject<number>;
  midRef: React.MutableRefObject<number>;
  trebleRef: React.MutableRefObject<number>;
  onsetRef: React.MutableRefObject<number>;
  analyserRef: React.RefObject<AnalyserNode | null>;
  isActive: boolean;
  audioCallbackRef: (el: HTMLAudioElement | null) => void;
};

// WeakMap to track which audio elements already have a MediaElementSource
const sourceMap = new WeakMap<HTMLAudioElement, MediaElementAudioSourceNode>();

export function useAudioAnalyser(
  audioRef?: React.RefObject<HTMLAudioElement | null>,
): AudioAnalyserState {
  const bassRef   = useRef<number>(0);
  const midRef    = useRef<number>(0);
  const trebleRef = useRef<number>(0);
  const onsetRef  = useRef<number>(0);
  const [isActive, setIsActive] = useState(false);

  const ctxRef      = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef      = useRef<number>(0);
  const connectedElRef = useRef<HTMLAudioElement | null>(null);

  const prevBinsRef       = useRef<Uint8Array | null>(null);
  const fluxHistoryRef    = useRef<number[]>([]);

  const startLoop = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;

    cancelAnimationFrame(rafRef.current);
    const bins = new Uint8Array(analyser.frequencyBinCount);

    const tick = () => {
      analyser.getByteFrequencyData(bins);

      bassRef.current   = avg(bins, 0, 7);
      midRef.current    = avg(bins, 8, 63);
      trebleRef.current = avg(bins, 64, 127);

      // Onset detection — spectral flux
      const prev = prevBinsRef.current!;
      let flux = 0;
      for (let i = 0; i < bins.length; i++) {
        const diff = bins[i] - prev[i];
        if (diff > 0) flux += diff;
      }
      prev.set(bins);

      const history = fluxHistoryRef.current;
      history.push(flux);
      if (history.length > 60) history.shift();
      const mean = history.reduce((a, b) => a + b, 0) / (history.length || 1);
      onsetRef.current = flux > 1.3 * mean && mean > 0 ? 1.0 : 0.0;

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const initGraph = useCallback((audioEl: HTMLAudioElement) => {
    if (ctxRef.current) {
      // Already initialized — just resume context if suspended
      if (ctxRef.current.state === 'suspended') {
        ctxRef.current.resume();
      }
      setIsActive(true);
      startLoop();
      return;
    }

    try {
      const ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.8;

      // Reuse existing source if element was already connected (HMR / strict mode)
      let source = sourceMap.get(audioEl);
      if (!source) {
        source = ctx.createMediaElementSource(audioEl);
        sourceMap.set(audioEl, source);
      }
      source.connect(analyser);
      analyser.connect(ctx.destination);

      ctxRef.current = ctx;
      analyserRef.current = analyser;
      prevBinsRef.current = new Uint8Array(analyser.frequencyBinCount);

      setIsActive(true);
      startLoop();
    } catch (e) {
      // createMediaElementSource can fail if element is from a different context
      console.warn('[useAudioAnalyser] initGraph failed:', e);
    }
  }, [startLoop]);

  const connectElement = useCallback((audioEl: HTMLAudioElement) => {
    if (connectedElRef.current === audioEl) return;
    connectedElRef.current = audioEl;

    const onPlay = () => initGraph(audioEl);
    const onPause = () => {
      cancelAnimationFrame(rafRef.current);
    };
    const onEnded = () => {
      cancelAnimationFrame(rafRef.current);
      bassRef.current = midRef.current = trebleRef.current = onsetRef.current = 0;
      setIsActive(false);
    };

    audioEl.addEventListener('play', onPlay);
    audioEl.addEventListener('pause', onPause);
    audioEl.addEventListener('ended', onEnded);

    // If already playing, init immediately
    if (!audioEl.paused) {
      initGraph(audioEl);
    }
  }, [initGraph]);

  // Callback ref for direct use on <audio ref={audioCallbackRef}>
  const audioCallbackRef = useCallback((el: HTMLAudioElement | null) => {
    if (el) connectElement(el);
  }, [connectElement]);

  // Support legacy RefObject pattern with polling fallback
  useEffect(() => {
    if (typeof window === 'undefined' || !window.AudioContext) return;
    if (!audioRef) return;

    const el = audioRef.current;
    if (el) {
      connectElement(el);
    }

    // Poll for element to appear (handles conditional rendering)
    const interval = setInterval(() => {
      const el = audioRef.current;
      if (el && el !== connectedElRef.current) {
        connectElement(el);
        clearInterval(interval);
      }
    }, 100);

    return () => {
      clearInterval(interval);
      cancelAnimationFrame(rafRef.current);
      setIsActive(false);
      bassRef.current = midRef.current = trebleRef.current = onsetRef.current = 0;
    };
  }, [audioRef, connectElement]);

  return { bassRef, midRef, trebleRef, onsetRef, analyserRef, isActive, audioCallbackRef };
}

function avg(bins: Uint8Array, from: number, to: number): number {
  let sum = 0;
  const end = Math.min(to, bins.length - 1);
  for (let i = from; i <= end; i++) sum += bins[i];
  return sum / (end - from + 1) / 255;
}
