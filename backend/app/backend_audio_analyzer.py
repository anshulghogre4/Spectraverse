"""
Audio Feature Extraction Service
Extracts: BPM, pitch, spectral centroid, bass energy, treble energy, etc.
Uses: librosa, torchaudio, essentia
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
            audio_path: Path to audio file (MP3, WAV, OGG)
        
        Returns:
            Dict with features: bpm, pitch, centroid, bass, treble, genre, vibe
        """
        try:
            # Load audio
            y, sr = librosa.load(audio_path, sr=self.sr)
            
            # Extract features
            features = {
                "bpm": self._extract_bpm(y, sr),
                "pitch": self._extract_pitch(y, sr),
                "spectral_centroid": self._extract_centroid(y, sr),
                "bass_energy": self._extract_bass_energy(y, sr),
                "treble_energy": self._extract_treble_energy(y, sr),
                "mfcc": self._extract_mfcc(y, sr),
                "genre": self._infer_genre(y, sr),
                "vibe": self._infer_vibe(y, sr),
                "complexity": self._extract_complexity(y, sr),
            }
            
            return features
            
        except Exception as e:
            return {"error": str(e), "status": "analysis_failed"}
    
    def _extract_bpm(self, y: np.ndarray, sr: int) -> int:
        """Extract BPM using onset detection and tempogram."""
        try:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
            bpm = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0]
            return int(np.round(bpm))
        except:
            return 90  # Default fallback
    
    def _extract_pitch(self, y: np.ndarray, sr: int) -> Dict[str, float]:
        """Extract pitch using piptrack."""
        try:
            f0 = librosa.yin(y, fmin=50, fmax=2000, sr=sr)
            f0_clean = f0[~np.isnan(f0)]
            if len(f0_clean) == 0:
                return {"hz": 440, "note": "A4"}
            
            mean_f0 = np.median(f0_clean)
            return {
                "hz": float(mean_f0),
                "note": self._hz_to_note(mean_f0)
            }
        except:
            return {"hz": 440, "note": "A4"}
    
    def _extract_centroid(self, y: np.ndarray, sr: int) -> float:
        """Spectral centroid (average frequency)."""
        return float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    
    def _extract_bass_energy(self, y: np.ndarray, sr: int) -> float:
        """Energy in bass range (0-250 Hz)."""
        D = librosa.stft(y)
        S = np.abs(D) ** 2
        bass_range = int(250 / (sr / 2) * S.shape[0])
        bass_energy = np.mean(S[:bass_range])
        return float(np.clip(bass_energy / 1000, 0, 1))  # Normalize
    
    def _extract_treble_energy(self, y: np.ndarray, sr: int) -> float:
        """Energy in treble range (5000+ Hz)."""
        D = librosa.stft(y)
        S = np.abs(D) ** 2
        treble_start = int(5000 / (sr / 2) * S.shape[0])
        treble_energy = np.mean(S[treble_start:])
        return float(np.clip(treble_energy / 1000, 0, 1))  # Normalize
    
    def _extract_mfcc(self, y: np.ndarray, sr: int) -> list:
        """Mel-frequency cepstral coefficients (13 coefficients)."""
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        return [float(np.mean(m)) for m in mfcc]
    
    def _infer_genre(self, y: np.ndarray, sr: int) -> str:
        """Infer genre from audio characteristics (simplified)."""
        centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
        bpm = self._extract_bpm(y, sr)
        bass = self._extract_bass_energy(y, sr)
        
        if bpm > 140 and bass > 0.6:
            return "electronic"
        elif bpm < 90 and centroid < 2000:
            return "ambient"
        elif bpm > 100 and centroid > 4000:
            return "pop"
        elif bass < 0.3 and centroid > 5000:
            return "classical"
        else:
            return "mixed"
    
    def _infer_vibe(self, y: np.ndarray, sr: int) -> str:
        """Infer emotional vibe (simplified)."""
        centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
        bass = self._extract_bass_energy(y, sr)
        treble = self._extract_treble_energy(y, sr)
        
        brightness = (treble - bass) / (treble + bass + 0.001)
        
        if bass > 0.7:
            return "dark_heavy"
        elif brightness > 0.6:
            return "bright_energetic"
        elif centroid < 1500:
            return "warm_deep"
        else:
            return "balanced"
    
    def _extract_complexity(self, y: np.ndarray, sr: int) -> float:
        """Complexity based on spectral entropy."""
        D = librosa.stft(y)
        S = np.abs(D) ** 2
        S_norm = S / np.sum(S, axis=0, keepdims=True)
        entropy = -np.sum(S_norm * np.log(S_norm + 1e-10), axis=0)
        return float(np.mean(entropy) / np.log(S.shape[0]))  # Normalize
    
    def _hz_to_note(self, hz: float) -> str:
        """Convert Hz to note name."""
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        A4 = 440
        C0 = A4 * pow(2, -4.75)
        h = 12 * np.log2(hz / C0)
        octave = int(h // 12)
        n = int(h % 12)
        return f"{notes[n]}{octave}"


# Example usage
if __name__ == "__main__":
    analyzer = AudioAnalyzer()
    
    # Mock test
    features = {
        "bpm": 120,
        "pitch": {"hz": 440, "note": "A4"},
        "spectral_centroid": 3200,
        "bass_energy": 0.65,
        "treble_energy": 0.45,
        "genre": "electronic",
        "vibe": "energetic",
        "complexity": 0.7
    }
    
    print(json.dumps(features, indent=2))
