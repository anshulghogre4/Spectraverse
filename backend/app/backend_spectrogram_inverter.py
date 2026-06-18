"""
SpectrogramInverter
Reconstructs audio from a magnitude spectrogram using Griffin-Lim.

Key findings from research:
- Griffin-Lim with n_iter=64-128 achieves ~70-90% speech intelligibility
- librosa.feature.inverse.mel_to_audio wraps mel→STFT→Griffin-Lim in one call
- power=1.0 for amplitude spectrogram (what our preprocessor returns)
- momentum=0.99 (Fast Griffin-Lim) is default in librosa >= 0.9

Presets (from real-world source code analysis):
- "librosa_mel": sr=22050, n_mels=128, n_fft=2048, hop=512 (matches docs/examples)
- "chrome_music_lab": sr=44100, linear FFT 2048, log freq 20-20000Hz
- "wikipedia_speech": sr=16000, linear FFT 1024, hop=256 (typical for speech)
"""

from __future__ import annotations
import numpy as np
from typing import Dict, Any, Tuple

# Optional neural vocoder — much better quality than Griffin-Lim when available
try:
    import torch
    from vocos import Vocos as _Vocos
    VOCOS_AVAILABLE = True
except ImportError:
    VOCOS_AVAILABLE = False


# Matching librosa defaults used in most publicly shared spectrograms
DEFAULT_SR = 22050
DEFAULT_N_MELS = 128
DEFAULT_N_FFT = 2048
DEFAULT_HOP_LENGTH = 512
DEFAULT_N_ITER = 64

# Hard input cap to prevent OOM on huge uploads (e.g. 1920×1080 screenshots).
# Width cap is kept very large so frame-accurate resize in the endpoint is not
# undone here.  Height cap prevents OOM in the mel filterbank step.
MAX_INPUT_WIDTH = 8192
MAX_INPUT_HEIGHT = 256


PRESETS: Dict[str, Dict[str, Any]] = {
    "librosa_mel": {
        "sr": 22050, "n_mels": 128, "n_fft": 2048, "hop_length": 512,
        "scale": "mel",
    },
    "chrome_music_lab": {
        "sr": 44100, "n_mels": 256, "n_fft": 2048, "hop_length": 1024,
        "scale": "log_linear",   # Chrome Music Lab uses linear FFT on log freq display
    },
    "wikipedia_speech": {
        "sr": 16000, "n_mels": 80, "n_fft": 1024, "hop_length": 256,
        "scale": "linear",
    },
}


class SpectrogramInverter:
    """Invert a magnitude spectrogram back to audio using Griffin-Lim."""

    def __init__(
        self,
        sr: int = DEFAULT_SR,
        n_mels: int = DEFAULT_N_MELS,
        n_fft: int = DEFAULT_N_FFT,
        hop_length: int = DEFAULT_HOP_LENGTH,
        n_iter: int = DEFAULT_N_ITER,
        scale: str = "mel",
    ):
        self.sr = sr
        self.n_mels = n_mels
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_iter = n_iter
        self.scale = scale  # "mel" | "linear" | "log_linear"

    @classmethod
    def from_preset(cls, preset: str, n_iter: int = DEFAULT_N_ITER) -> "SpectrogramInverter":
        if preset not in PRESETS:
            raise ValueError(f"Unknown preset {preset!r}. Available: {list(PRESETS)}")
        p = PRESETS[preset]
        return cls(
            sr=p["sr"], n_mels=p["n_mels"], n_fft=p["n_fft"],
            hop_length=p["hop_length"], scale=p["scale"], n_iter=n_iter,
        )

    def _invert_vocos(self, magnitude: np.ndarray) -> "np.ndarray | None":
        """
        Attempt neural vocoder inversion via Vocos.
        Returns audio numpy array on success, None on failure (so caller can fall back).
        """
        try:
            vocos = _Vocos.from_pretrained("charactr/vocos-mel-24khz")
            mel_spec = torch.from_numpy(magnitude).unsqueeze(0).float()
            with torch.no_grad():
                waveform = vocos.decode(mel_spec)
            return waveform.squeeze().cpu().numpy()
        except Exception:
            return None

    def invert(self, magnitude: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Args:
            magnitude: (H, W) float32 array — amplitude spectrogram.
                       H = freq bins (row 0 = lowest freq), W = time frames.

        Returns:
            audio: float32 1-D array, normalised to [-1, 1]
            meta: dict with reconstruction info
        """
        import librosa

        # Hard cap input to prevent crashes on huge uploads (1920px etc.)
        mag = self._cap_input_size(magnitude)
        mag = self._resize_to_mels(mag)

        # Try Vocos neural vocoder first (much better quality than Griffin-Lim)
        reconstruction_method = "griffin_lim"
        audio = None
        if VOCOS_AVAILABLE:
            audio = self._invert_vocos(mag)
            if audio is not None:
                reconstruction_method = "vocos"

        # Fall back to Griffin-Lim if Vocos is unavailable or failed
        if audio is None:
            if self.scale == "linear" or self.scale == "log_linear":
                # Treat rows as linear STFT bins directly (skip mel filterbank)
                # Resize rows to (1 + n_fft//2) so it matches librosa.griffinlim's expected shape
                expected_bins = 1 + self.n_fft // 2
                mag_stft = self._resize_rows(mag, expected_bins)
                audio = librosa.griffinlim(
                    mag_stft,
                    n_iter=self.n_iter,
                    hop_length=self.hop_length,
                    win_length=self.n_fft,
                    window="hann",
                    center=True,
                )
            else:
                # Mel inversion (standard librosa path).
                audio = librosa.feature.inverse.mel_to_audio(
                    mag,
                    sr=self.sr,
                    n_fft=self.n_fft,
                    hop_length=self.hop_length,
                    win_length=self.n_fft,
                    window="hann",
                    center=True,
                    power=1.0,
                    n_iter=self.n_iter,
                )

        audio = audio.astype(np.float32)
        audio = self._fade(audio, fade_samples=int(self.sr * 0.005))

        peak = float(np.max(np.abs(audio)))
        if peak > 0:
            audio = audio / peak * 0.95

        duration = len(audio) / self.sr
        rms = float(np.sqrt(np.mean(audio ** 2)))

        meta = {
            "reconstruction_method": reconstruction_method,
            "vocoder": "vocos" if VOCOS_AVAILABLE else "griffin_lim",
            "scale": self.scale,
            "n_iter": self.n_iter,
            "sr": self.sr,
            "n_mels": self.n_mels,
            "n_fft": self.n_fft,
            "hop_length": self.hop_length,
            "input_shape": list(magnitude.shape),
            "processed_shape": list(mag.shape),
            "duration_seconds": round(duration, 3),
            "peak_amplitude": round(peak, 4),
            "rms": round(rms, 4),
        }
        return audio, meta

    # ── Encoding helpers ──────────────────────────────────────────────────

    def encode_wav_b64(self, audio: np.ndarray) -> str:
        import io
        import base64
        import scipy.io.wavfile as wavfile
        buf = io.BytesIO()
        wavfile.write(buf, self.sr, audio.astype(np.float32))
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()

    def generate_comparison_spectrogram(self, audio: np.ndarray) -> str:
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

    def _cap_input_size(self, mag: np.ndarray) -> np.ndarray:
        """Downsample huge inputs to prevent OOM / hang on 1920px screenshots."""
        H, W = mag.shape
        if H <= MAX_INPUT_HEIGHT and W <= MAX_INPUT_WIDTH:
            return mag
        try:
            from PIL import Image as PILImage
            target_w = min(W, MAX_INPUT_WIDTH)
            target_h = min(H, MAX_INPUT_HEIGHT)
            return np.array(
                PILImage.fromarray(mag).resize((target_w, target_h), PILImage.BILINEAR),
                dtype=np.float32,
            )
        except Exception:
            # numpy fallback: simple striding
            stride_h = max(1, H // MAX_INPUT_HEIGHT)
            stride_w = max(1, W // MAX_INPUT_WIDTH)
            return mag[::stride_h, ::stride_w].astype(np.float32)

    def _resize_to_mels(self, mag: np.ndarray) -> np.ndarray:
        if mag.shape[0] == self.n_mels:
            return mag
        return self._resize_rows(mag, self.n_mels)

    def _resize_rows(self, mag: np.ndarray, target_rows: int) -> np.ndarray:
        if mag.shape[0] == target_rows:
            return mag
        try:
            from PIL import Image as PILImage
            img = PILImage.fromarray(mag).resize(
                (mag.shape[1], target_rows), PILImage.BILINEAR
            )
            return np.array(img, dtype=np.float32)
        except Exception:
            old_rows = np.linspace(0, mag.shape[0] - 1, target_rows)
            new_mag = np.zeros((target_rows, mag.shape[1]), dtype=np.float32)
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
