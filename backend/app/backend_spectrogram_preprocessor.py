"""
SpectrogramPreprocessor
Converts a spectrogram PNG into a numpy magnitude array ready for Griffin-Lim.

Pipeline:
1. Load image
2. Auto-crop axes/margins (entropy-based)
3. Invert colormap (RGB pixels → [0,1] normalised values)
4. Convert dB scale → linear amplitude
5. Return (n_mels, T) float32 array
"""

from __future__ import annotations
import numpy as np
from typing import Tuple
from io import BytesIO


# Default assumptions matching librosa's defaults
DEFAULT_DB_MIN = -80.0
DEFAULT_DB_MAX = 0.0
SUPPORTED_COLORMAPS = ["viridis", "magma", "plasma", "inferno", "hot", "jet", "coolwarm"]


class SpectrogramPreprocessor:
    """Convert spectrogram image → mel magnitude array."""

    def __init__(
        self,
        colormap: str = "viridis",
        db_min: float = DEFAULT_DB_MIN,
        db_max: float = DEFAULT_DB_MAX,
        auto_crop: bool = True,
    ):
        self.colormap = colormap
        self.db_min = db_min
        self.db_max = db_max
        self.auto_crop = auto_crop
        self._lut_cache: dict = {}

    def extract_magnitude(self, image_bytes: bytes) -> Tuple[np.ndarray, dict]:
        """
        Args:
            image_bytes: PNG/JPEG image bytes

        Returns:
            magnitude: float32 array (n_mels, T) in linear amplitude
            meta: dict with crop bounds, colormap, db_range, shape info
        """
        img = self._load(image_bytes)
        original_shape = img.shape

        if self.auto_crop:
            img, crop_bounds = self._crop_axes(img)
        else:
            crop_bounds = (0, img.shape[0], 0, img.shape[1])

        # Invert colormap: RGB → [0,1] scalar
        norm_vals = self._invert_colormap(img, self.colormap)

        # Spectrogram images: row 0 = high frequency, last row = low frequency
        # librosa convention: mel bin 0 = lowest frequency → flip vertical axis
        norm_vals = np.flipud(norm_vals)  # (H, W) with row 0 = low freq

        # dB → linear amplitude
        magnitude = self._db_to_amplitude(norm_vals)

        meta = {
            "original_shape": original_shape,
            "cropped_shape": img.shape,
            "crop_bounds": crop_bounds,
            "colormap": self.colormap,
            "db_range": (self.db_min, self.db_max),
            "magnitude_shape": magnitude.shape,
            "magnitude_min": float(magnitude.min()),
            "magnitude_max": float(magnitude.max()),
        }

        return magnitude, meta

    # ── Internal ──────────────────────────────────────────────────────────

    def _load(self, image_bytes: bytes) -> np.ndarray:
        from PIL import Image
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        return np.array(img, dtype=np.float32) / 255.0

    def _crop_axes(self, img: np.ndarray) -> Tuple[np.ndarray, Tuple]:
        """
        Detect and remove axis labels/margins using local variance entropy.
        Returns cropped image and (top, bottom, left, right) crop bounds.
        """
        from scipy.ndimage import uniform_filter

        gray = img.mean(axis=2)  # (H, W)

        # Local variance as activity proxy
        lv = uniform_filter(gray ** 2, 15) - uniform_filter(gray, 15) ** 2

        thresh = lv.mean() * 0.25
        row_active = lv.mean(axis=1) > thresh
        col_active = lv.mean(axis=0) > thresh

        active_rows = np.where(row_active)[0]
        active_cols = np.where(col_active)[0]

        if len(active_rows) < 8 or len(active_cols) < 8:
            # Fallback: conservative fixed-margin crop (7% each side)
            H, W = img.shape[:2]
            margin_h = max(1, H // 14)
            margin_w = max(1, W // 14)
            top, bottom = margin_h, H - margin_h
            left, right = margin_w, W - margin_w
        else:
            pad = 3
            top    = max(0, int(active_rows[0]) - pad)
            bottom = min(img.shape[0], int(active_rows[-1]) + pad + 1)
            left   = max(0, int(active_cols[0]) - pad)
            right  = min(img.shape[1], int(active_cols[-1]) + pad + 1)

        return img[top:bottom, left:right], (top, bottom, left, right)

    def _build_lut(self, cmap_name: str, n: int = 8192):
        import matplotlib.cm as cm
        from scipy.spatial import cKDTree
        c = cm.get_cmap(cmap_name, n)
        v = np.linspace(0.0, 1.0, n, dtype=np.float32)
        rgb = c(v)[:, :3].astype(np.float32)
        return cKDTree(rgb), v

    def _invert_colormap(self, img: np.ndarray, cmap_name: str) -> np.ndarray:
        """
        Map each RGB pixel to its closest scalar value in the colormap LUT.
        Returns (H, W) float32 array in [0, 1].
        """
        key = cmap_name
        if key not in self._lut_cache:
            self._lut_cache[key] = self._build_lut(cmap_name)
        tree, values = self._lut_cache[key]

        H, W, _ = img.shape
        pixels = img.reshape(-1, 3).astype(np.float32)

        # Query in chunks to avoid memory pressure on large images
        chunk = 50_000
        indices = np.empty(len(pixels), dtype=np.int32)
        for start in range(0, len(pixels), chunk):
            end = min(start + chunk, len(pixels))
            _, idx = tree.query(pixels[start:end], k=1)
            indices[start:end] = idx

        return values[indices].reshape(H, W)

    def _db_to_amplitude(self, norm_vals: np.ndarray) -> np.ndarray:
        """
        norm_vals: (H, W) in [0, 1] from colormap inversion.
        Maps [0,1] → [db_min, db_max] → linear amplitude.
        """
        db = norm_vals * (self.db_max - self.db_min) + self.db_min
        # librosa.db_to_amplitude: A = ref * 10^(db/20)
        amplitude = np.power(10.0, db / 20.0).astype(np.float32)
        return amplitude
