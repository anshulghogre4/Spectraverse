"""
SpectrogramInverter
Reconstructs audio from a magnitude spectrogram using Griffin-Lim.

Key findings from research:
- Griffin-Lim with n_iter=64-128 achieves ~70-90% speech intelligibility
- librosa.feature.inverse.mel_to_audio wraps mel→STFT→Griffin-Lim in one call
- power=1.0 for amplitude spectrogram (what our preprocessor returns)
- momentum=0.99 (Fast Griffin-Lim) is default in librosa >= 0.9
- Run with random_state=42 for reproducibility
"""

from __future__ import annotations
import numpy as np
from typing import Dict, Any, Tuple


# Matching librosa defaults used in most publicly shared spectrograms
DEFAULT_SR = 22050
DEFAULT_N_MELS = 128
DEFAULT_N_FFT = 2048
DEFAULT_HOP_LENGTH = 512
DEFAULT_N_ITER = 64   # 64 = good quality/speed tradeoff; use 128 for max quality


class SpectrogramInverter:
    """Invert a magnitude mel spectrogram back to audio using Griffin-Lim."""

    def __init__(
        self,
        sr: int = DEFAULT_SR,
        n_mels: int = DEFAULT_N_MELS,
        n_fft: int = DEFAULT_N_FFT,
        hop_length: int = DEFAULT_HOP_LENGTH,
        n_iter: int = DEFAULT_N_ITER,
    ):
        self.sr = sr
        self.n_mels = n_mels
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_iter = n_iter

    def invert(self, magnitude: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Args:
            magnitude: (H, W) float32 array — mel amplitude spectrogram.
                       H = mel bins (row 0 = lowest freq), W = time frames.

        Returns:
            audio: float32 1-D array, normalised to [-1, 1]
            meta: dict with reconstruction info
        """
        import librosa

        # Resize to expected mel bins if different from our parameter
        mag = self._resize_to_mels(magnitude)

        # Griffin-Lim via librosa's mel_to_audio convenience function.
        # This internally does:
        #   1. mel_to_stft (pseudo-inverse of mel filterbank)
        #   2. griffinlim (phase estimation, n_iter iterations)
        audio = librosa.feature.inverse.mel_to_audio(
            mag,
            sr=self.sr,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            win_length=self.n_fft,
            window="hann",
            center=True,
            power=1.0,        # amplitude (not power) spectrogram
            n_iter=self.n_iter,
        )

        audio = audio.astype(np.float32)

        # Fade in/out (5ms) to avoid click artefacts
        audio = self._fade(audio, fade_samples=int(self.sr * 0.005))

        # Normalise to peak -1 dBFS
        peak = float(np.max(np.abs(audio)))
        if peak > 0:
            audio = audio / peak * 0.95

        duration = len(audio) / self.sr
        rms = float(np.sqrt(np.mean(audio ** 2)))

        meta = {
            "reconstruction_method": "griffin_lim",
            "n_iter": self.n_iter,
            "sr": self.sr,
            "n_mels": self.n_mels,
            "n_fft": self.n_fft,
            "hop_length": self.hop_length,
            "input_shape": list(magnitude.shape),
            "resized_shape": list(mag.shape),
            "duration_seconds": round(duration, 3),
            "peak_amplitude": round(peak, 4),
            "rms": round(rms, 4),
        }

        return audio, meta

    def encode_wav_b64(self, audio: np.ndarray) -> str:
        """Encode float32 audio to base64 WAV string."""
        import io
        import base64
        import scipy.io.wavfile as wavfile

        buf = io.BytesIO()
        wavfile.write(buf, self.sr, audio.astype(np.float32))
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()

    def generate_comparison_spectrogram(self, audio: np.ndarray) -> str:
        """Generate mel spectrogram of the reconstructed audio as base64 PNG."""
        try:
            import librosa
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            S = librosa.feature.melspectrogram(
                y=audio, sr=self.sr, n_fft=self.n_fft,
                hop_length=self.hop_length, n_mels=self.n_mels,
            )
            S_db = librosa.power_to_db(S, ref=np.max)

            fig, ax = plt.subplots(figsize=(8, 3))
            librosa.display.specshow(
                S_db, sr=self.sr, hop_length=self.hop_length,
                x_axis="time", y_axis="mel", ax=ax, cmap="viridis",
            )
            ax.set_title("Reconstructed spectrogram")

            import io, base64
            buf = io.BytesIO()
            plt.savefig(buf, format="png", bbox_inches="tight", dpi=100)
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode()
            plt.close(fig)
            return f"data:image/png;base64,{b64}"
        except Exception:
            return ""

    # ── Helpers ───────────────────────────────────────────────────────────

    def _resize_to_mels(self, mag: np.ndarray) -> np.ndarray:
        """Resize magnitude array rows to self.n_mels using bilinear interpolation."""
        if mag.shape[0] == self.n_mels:
            return mag
        try:
            from PIL import Image as PILImage
            # PIL resize: (width, height) = (T, n_mels)
            img = PILImage.fromarray(mag).resize(
                (mag.shape[1], self.n_mels), PILImage.BILINEAR
            )
            return np.array(img, dtype=np.float32)
        except Exception:
            # Fallback: numpy linear interpolation along axis 0
            old_rows = np.linspace(0, mag.shape[0] - 1, self.n_mels)
            new_mag = np.zeros((self.n_mels, mag.shape[1]), dtype=np.float32)
            for i, r in enumerate(old_rows):
                lo = int(r)
                hi = min(lo + 1, mag.shape[0] - 1)
                frac = r - lo
                new_mag[i] = (1 - frac) * mag[lo] + frac * mag[hi]
            return new_mag

    def _fade(self, audio: np.ndarray, fade_samples: int) -> np.ndarray:
        if fade_samples <= 0 or len(audio) < 2 * fade_samples:
            return audio
        fade_in = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
        fade_out = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
        audio[:fade_samples] *= fade_in
        audio[-fade_samples:] *= fade_out
        return audio
