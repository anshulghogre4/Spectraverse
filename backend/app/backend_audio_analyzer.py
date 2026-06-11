"""
Audio Feature Extraction Service
Extracts: BPM, pitch, spectral centroid, bass/treble energy, genre, vibe, complexity.

Energy normalization: all band energies are expressed as a fraction of total spectral
energy, then rescaled relative to a flat-spectrum baseline. This makes them meaningful
for any signal level — quiet birds, loud EDM, or speech all get sensible 0-1 values.
"""

import librosa
import numpy as np
from typing import Dict, Any
import json


class AudioAnalyzer:
    """Extract semantic features from audio files."""

    def __init__(self, sr: int = 22050):
        self.sr = sr

    def analyze_bytes(self, audio_data: bytes) -> Dict[str, Any]:
        """Analyze audio from raw bytes by writing to a temp file."""
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        try:
            tmp.write(audio_data)
            tmp.flush()
            tmp.close()
            return self.analyze(tmp.name)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def analyze(self, audio_path: str) -> Dict[str, Any]:
        """
        Comprehensive audio analysis returning all semantic features.

        Args:
            audio_path: Path to audio file (MP3, WAV, OGG, etc.)

        Returns:
            Dict with features: bpm, pitch, spectral_centroid, bass_energy,
            treble_energy, mid_energy, genre, vibe, complexity, mfcc.
        """
        try:
            y, sr = librosa.load(audio_path, sr=self.sr)

            # Compute STFT once and share across methods
            D = librosa.stft(y)
            S = np.abs(D) ** 2  # power spectrogram

            bass_energy   = self._band_energy_ratio(S, sr, 0, 250)
            mid_energy    = self._band_energy_ratio(S, sr, 250, 4000)
            treble_energy = self._band_energy_ratio(S, sr, 4000, sr // 2)

            return {
                "bpm":               self._extract_bpm(y, sr),
                "pitch":             self._extract_pitch(y, sr),
                "spectral_centroid": self._extract_centroid(y, sr),
                "bass_energy":       round(bass_energy, 4),
                "mid_energy":        round(mid_energy, 4),
                "treble_energy":     round(treble_energy, 4),
                "mfcc":              self._extract_mfcc(y, sr),
                "genre":             self._infer_genre(bass_energy, mid_energy, treble_energy, y, sr),
                "vibe":              self._infer_vibe(bass_energy, mid_energy, treble_energy, y, sr),
                "complexity":        self._extract_complexity(S),
            }

        except Exception as e:
            return {"error": str(e), "status": "analysis_failed"}

    # ── Shared band-energy helper ────────────────────────────────────────

    def _band_energy_ratio(
        self, S: np.ndarray, sr: int, freq_lo: float, freq_hi: float
    ) -> float:
        """
        Return the fraction of total power in [freq_lo, freq_hi] Hz,
        normalized relative to a flat-spectrum baseline so that a signal
        with uniform energy across all bins scores ~0.5 in every band.

        A value > 0.5 means the band has more energy than a flat spectrum
        would predict; < 0.5 means less.
        """
        n_bins = S.shape[0]
        nyquist = sr / 2.0
        lo_bin = int(freq_lo / nyquist * n_bins)
        hi_bin = int(min(freq_hi / nyquist * n_bins, n_bins))
        if hi_bin <= lo_bin:
            return 0.0

        band_power = float(np.sum(S[lo_bin:hi_bin]))
        total_power = float(np.sum(S)) + 1e-12

        actual_frac   = band_power / total_power
        expected_frac = (hi_bin - lo_bin) / n_bins   # flat-spectrum expectation

        # Rescale: actual/expected=1 → 0.5; higher → >0.5; lower → <0.5
        ratio = actual_frac / (expected_frac + 1e-12) / 2.0
        return float(np.clip(ratio, 0.0, 1.0))

    # ── Individual feature extractors ────────────────────────────────────

    def _extract_bpm(self, y: np.ndarray, sr: int) -> int:
        try:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            bpm = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0]
            return int(np.round(bpm))
        except Exception:
            return 90

    def _extract_pitch(self, y: np.ndarray, sr: int) -> Dict[str, float]:
        try:
            f0 = librosa.yin(y, fmin=50, fmax=4000, sr=sr)
            f0_clean = f0[(f0 > 0) & ~np.isnan(f0)]
            if len(f0_clean) == 0:
                return {"hz": 0.0, "note": "—"}
            mean_f0 = float(np.median(f0_clean))
            return {"hz": round(mean_f0, 1), "note": self._hz_to_note(mean_f0)}
        except Exception:
            return {"hz": 0.0, "note": "—"}

    def _extract_centroid(self, y: np.ndarray, sr: int) -> float:
        try:
            return float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        except Exception:
            return 0.0

    def _extract_mfcc(self, y: np.ndarray, sr: int) -> list:
        try:
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            return [round(float(np.mean(m)), 1) for m in mfcc]
        except Exception:
            return []

    def _extract_complexity(self, S: np.ndarray) -> float:
        """Spectral entropy normalized to [0, 1]."""
        try:
            eps = 1e-10
            S_norm = S / (np.sum(S, axis=0, keepdims=True) + eps)
            entropy = -np.sum(S_norm * np.log(S_norm + eps), axis=0)
            return float(np.clip(np.mean(entropy) / np.log(S.shape[0] + eps), 0.0, 1.0))
        except Exception:
            return 0.5

    # ── Semantic inference (now uses relative band ratios) ────────────────

    def _infer_genre(
        self,
        bass: float, mid: float, treble: float,
        y: np.ndarray, sr: int,
    ) -> str:
        """
        Classify into a broad audio category using relative band energies.
        Works for music *and* non-music audio (nature, speech, noise).
        """
        centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        bpm      = self._extract_bpm(y, sr)

        # Nature/organic: very high centroid, minimal bass, no strong beat
        if centroid > 3500 and bass < 0.25 and mid < 0.4:
            return "nature"

        # Speech: mid-dominant, modest centroid, low bass
        if 1500 < centroid < 4000 and mid > 0.55 and bass < 0.3:
            return "speech"

        # Electronic/EDM: strong bass + fast tempo
        if bass > 0.6 and bpm > 130:
            return "electronic"

        # Hip-hop: strong bass, moderate tempo
        if bass > 0.55 and 80 <= bpm <= 130:
            return "hip-hop"

        # Classical/acoustic: low bass, moderate centroid
        if bass < 0.3 and 1000 < centroid < 4000:
            return "classical"

        # Ambient: slow, low bass, wide spread
        if bpm < 85 and bass < 0.4 and treble > 0.4:
            return "ambient"

        # Pop: bright centroid, moderate bass
        if centroid > 3000 and 0.3 <= bass <= 0.6:
            return "pop"

        return "mixed"

    def _infer_vibe(
        self,
        bass: float, mid: float, treble: float,
        y: np.ndarray, sr: int,
    ) -> str:
        """Emotional vibe from relative band balance."""
        centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))

        if bass > 0.65:
            return "dark_heavy"
        if treble > 0.65 and bass < 0.35:
            return "bright_airy"
        if treble > 0.55 and mid > 0.5:
            return "bright_energetic"
        if bass > 0.45 and mid > 0.5:
            return "warm_full"
        if centroid < 1500:
            return "warm_deep"
        if centroid > 4500:
            return "crisp_natural"
        return "balanced"

    # ── Utilities ─────────────────────────────────────────────────────────

    def _hz_to_note(self, hz: float) -> str:
        if hz <= 0:
            return "—"
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        A4  = 440.0
        C0  = A4 * pow(2, -4.75)
        h   = 12 * np.log2(hz / C0)
        octave = int(h // 12)
        n      = int(h % 12)
        return f"{notes[n]}{octave}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        analyzer = AudioAnalyzer()
        result = analyzer.analyze(sys.argv[1])
        print(json.dumps(result, indent=2))
