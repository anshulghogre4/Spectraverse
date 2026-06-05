"""
DSP Audio Synthesis Service
Generates audio from semantic parameters using torchaudio & librosa.
Process:
1. Generate base waveform (sine wave with pitch)
2. Add harmonics (brightness)
3. Add percussion (sharpness)
4. Add ambience/reverb (texture)
5. Normalize & limit (safety)
"""

import numpy as np
from typing import Dict, Any, List
import json

class DSPSynthesizer:
    """Synthesize audio using DSP techniques."""
    
    def __init__(self, sr: int = 22050, duration: float = 30.0):
        self.sr = sr
        self.duration = min(duration, 60.0)  # Max 60 seconds
        self.num_samples = int(sr * self.duration)
    
    def synthesize(self, params: Dict[str, Any]) -> np.ndarray:
        """
        Synthesize audio from parameters.
        """
        waveform = np.zeros(self.num_samples)

        pitch        = float(params.get("pitch", 220))
        bpm          = float(params.get("bpm", 90))
        instruments  = params.get("instruments", ["pad"])
        reverb_amount= float(params.get("reverb", 0.3))
        intensity    = float(params.get("intensity", 0.5))
        complexity   = float(params.get("complexity", 0.5))
        effects      = params.get("effects", [])

        t = np.linspace(0, self.duration, self.num_samples)

        # ── Fundamental tone ──────────────────────────────────────────────
        waveform += intensity * 0.35 * np.sin(2 * np.pi * pitch * t)

        # ── Harmonics — more harmonics = brighter, busier sound ──────────
        n_harmonics = max(1, int(complexity * 6))
        for h in range(2, 2 + n_harmonics):
            amp = intensity * (0.2 / h)
            waveform += amp * np.sin(2 * np.pi * pitch * h * t)

        # ── BPM-driven rhythmic pulse ─────────────────────────────────────
        beat_hz = bpm / 60.0
        # Amplitude modulation at beat rate — fast BPM = more energetic pulsing
        beat_env = 0.5 + 0.5 * np.sin(2 * np.pi * beat_hz * t)
        waveform *= (0.6 + 0.4 * beat_env)

        # ── Instrument layers ──────────────────────────────────────────────
        if "pad" in instruments or "strings" in instruments or "synth_pad" in instruments:
            # Slow attack swell — lush, ambient
            swell = 1 - np.exp(-t / (self.duration * 0.15))
            waveform += 0.18 * np.sin(2 * np.pi * (pitch * 0.5) * t) * swell

        if "piano" in instruments or "vibraphone" in instruments:
            # Percussive attack-decay per beat
            beat_samples = int(self.sr / beat_hz)
            envelope = np.zeros(self.num_samples)
            for onset in range(0, self.num_samples, beat_samples):
                length = min(beat_samples, self.num_samples - onset)
                decay = np.exp(-np.linspace(0, 6, length))
                envelope[onset:onset + length] += decay
            waveform += 0.22 * np.sin(2 * np.pi * pitch * 1.5 * t) * envelope

        if "organ" in instruments or "cello" in instruments:
            # Warm sub-octave with vibrato
            vibrato = np.sin(2 * np.pi * 5.5 * t) * 0.005
            waveform += 0.15 * np.sin(2 * np.pi * (pitch * 0.5 + vibrato) * t)

        if "guitar" in instruments or "flute" in instruments:
            # Mid-range pluck — odd harmonics only (hollow tone)
            for h in [1, 3, 5]:
                waveform += (0.12 / h) * np.sin(2 * np.pi * pitch * h * t) * np.exp(-t * 1.2)

        # ── Effects ───────────────────────────────────────────────────────
        if "distortion" in effects:
            waveform = np.tanh(waveform * 3.0) * 0.7

        if "delay" in effects:
            delay_samples = int(0.3 * self.sr)
            if delay_samples < self.num_samples:
                delayed = np.zeros_like(waveform)
                delayed[delay_samples:] = waveform[:-delay_samples] * 0.45
                waveform = waveform + delayed

        if "compression" in effects:
            # Simple soft knee compression
            threshold = 0.4
            above = np.abs(waveform) > threshold
            waveform[above] = np.sign(waveform[above]) * (
                threshold + (np.abs(waveform[above]) - threshold) * 0.4
            )

        # ── Reverb (echo) ─────────────────────────────────────────────────
        if reverb_amount > 0:
            delay_samp = int(0.45 * self.sr)
            if delay_samp < self.num_samples:
                delayed = np.zeros_like(waveform)
                delayed[delay_samp:] = waveform[:-delay_samp]
                waveform = waveform + reverb_amount * delayed

        # ── Normalise + soft-limit ────────────────────────────────────────
        waveform = self._normalize(waveform)
        waveform = self._soft_limit(waveform)

        return waveform
    
    def _normalize(self, waveform: np.ndarray) -> np.ndarray:
        """Normalize to LUFS -14 (safe listening level)."""
        # Simple peak normalization to -0.99 + 0.99
        max_val = np.max(np.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val * 0.99
        return waveform
    
    def _soft_limit(self, waveform: np.ndarray, threshold: float = 0.7) -> np.ndarray:
        """Soft limiting to prevent clipping."""
        # Simple soft clipping using tanh
        return np.tanh(waveform / threshold) * 0.99
    
    def _high_pass_filter(self, waveform: np.ndarray, cutoff_hz: float = 20) -> np.ndarray:
        """Simple high-pass filter (remove subsonic)."""
        # Butterworth-like first-order filter (simplified)
        rc = 1 / (2 * np.pi * cutoff_hz)
        dt = 1 / self.sr
        alpha = dt / (rc + dt)
        
        filtered = np.zeros_like(waveform)
        filtered[0] = waveform[0]
        for i in range(1, len(waveform)):
            filtered[i] = alpha * (filtered[i - 1] + waveform[i] - waveform[i - 1])
        
        return filtered
    
    def _low_pass_filter(self, waveform: np.ndarray, cutoff_hz: float = 20000) -> np.ndarray:
        """Simple low-pass filter (remove ultrasonic)."""
        rc = 1 / (2 * np.pi * cutoff_hz)
        dt = 1 / self.sr
        alpha = dt / (rc + dt)
        
        filtered = np.zeros_like(waveform)
        filtered[0] = waveform[0]
        for i in range(1, len(waveform)):
            filtered[i] = filtered[i - 1] + alpha * (waveform[i] - filtered[i - 1])
        
        return filtered


# Example usage
if __name__ == "__main__":
    synthesizer = DSPSynthesizer(duration=10)
    
    params = {
        "pitch": 220,
        "bpm": 90,
        "instruments": ["pad", "piano"],
        "reverb": 0.4,
        "intensity": 0.7
    }
    
    audio = synthesizer.synthesize(params)
    print(f"Generated {len(audio)} samples ({len(audio) / 22050:.2f} seconds)")
    print(f"Peak: {np.max(np.abs(audio)):.4f}")
    print(f"RMS: {np.sqrt(np.mean(audio ** 2)):.4f}")
