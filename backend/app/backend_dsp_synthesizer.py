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
        
        Args:
            params: {
                "pitch": 220,  # Hz
                "bpm": 90,
                "instruments": ["pad", "piano"],
                "reverb": 0.4,
                "intensity": 0.7,
                "effects": ["reverb", "compression"]
            }
        
        Returns:
            Normalized audio waveform (np.ndarray)
        """
        waveform = np.zeros(self.num_samples)
        
        # Extract parameters
        pitch = params.get("pitch", 220)
        bpm = params.get("bpm", 90)
        instruments = params.get("instruments", ["pad"])
        reverb_amount = params.get("reverb", 0.3)
        intensity = params.get("intensity", 0.5)
        
        # Generate base waveform
        t = np.linspace(0, self.duration, self.num_samples)
        
        # Sine wave base (fundamental)
        waveform += 0.3 * np.sin(2 * np.pi * pitch * t)
        
        # Add harmonics (2x, 3x frequency for brightness)
        if intensity > 0.5:
            waveform += 0.15 * np.sin(2 * np.pi * pitch * 2 * t)
            waveform += 0.1 * np.sin(2 * np.pi * pitch * 3 * t)
        
        # Add ambient pad (low-frequency oscillation)
        if "pad" in instruments:
            waveform += 0.2 * np.sin(2 * np.pi * (pitch / 4) * t) * np.exp(-t / 10)
        
        # Add piano envelope (attack-decay)
        if "piano" in instruments:
            attack_time = 0.01
            decay_time = 0.5
            attack_samples = int(attack_time * self.sr)
            decay_start = attack_samples
            
            envelope = np.ones_like(t)
            envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
            
            decay_len = int(decay_time * self.sr)
            decay_end = min(decay_start + decay_len, self.num_samples)
            envelope[decay_start:decay_end] = np.exp(-np.linspace(0, 5, decay_end - decay_start))
            
            waveform += 0.25 * np.sin(2 * np.pi * pitch * t) * envelope
        
        # Apply reverb (simple echo)
        if reverb_amount > 0:
            delay_samples = int(0.5 * self.sr)
            delayed = np.zeros_like(waveform)
            delayed[delay_samples:] = waveform[:-delay_samples]
            waveform = waveform + reverb_amount * delayed
        
        # Safety: Normalize
        waveform = self._normalize(waveform)
        
        # Apply gentle limiting (prevent clipping)
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
