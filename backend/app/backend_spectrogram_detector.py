"""
SpectrogramDetector
Determines whether an uploaded image is a spectrogram (vs a regular photo)
and if so, what type (mel, linear/STFT, unknown).

Algorithm:
1. Horizontal banding check — spectrograms have strong row-to-row correlation
2. Colour gradient check — spectrograms use monotone colormaps (not natural colours)
3. Aspect ratio — spectrograms are typically landscape (wider than tall)
4. Entropy distribution — high entropy concentrated in content area, not uniform
"""

from __future__ import annotations
import numpy as np
from typing import Dict, Any
from io import BytesIO


class SpectrogramDetector:
    """Heuristic detector: is this image a spectrogram?"""

    # Confidence thresholds
    IS_SPECTROGRAM_THRESHOLD = 0.45
    COLORMAP_NAMES = ["viridis", "magma", "plasma", "inferno", "hot", "jet", "coolwarm"]

    def detect(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Returns:
            {
              "is_spectrogram": bool,
              "confidence": 0.0–1.0,
              "type": "mel" | "linear" | "unknown",
              "colormap_guess": "viridis" | ...,
              "reason": str
            }
        """
        try:
            img = self._load(image_bytes)
        except Exception as e:
            return {"is_spectrogram": False, "confidence": 0.0, "type": "unknown",
                    "colormap_guess": "viridis", "reason": f"Could not decode image: {e}"}

        scores: Dict[str, float] = {}

        # ── Score 1: horizontal banding (0–1) ────────────────────────────
        # Spectrograms have highly correlated adjacent rows; photos don't
        scores["banding"] = self._horizontal_banding_score(img)

        # ── Score 2: colormap likelihood (0–1) ───────────────────────────
        scores["colormap"], colormap_guess = self._colormap_score(img)

        # ── Score 3: aspect ratio — landscape preferred (0–1) ────────────
        h, w = img.shape[:2]
        ratio = w / max(h, 1)
        scores["aspect"] = min(1.0, ratio / 2.5)  # 2.5:1 = ideal spectrogram

        # ── Score 4: colour saturation — spectrograms are less saturated ──
        scores["saturation"] = self._saturation_score(img)

        # ── Score 5: edge density — spectrograms have horizontal edges ────
        scores["edges"] = self._horizontal_edge_score(img)

        weights = {
            "banding":    0.30,
            "colormap":   0.30,
            "aspect":     0.15,
            "saturation": 0.05,
            "edges":      0.20,
        }
        confidence = sum(scores[k] * weights[k] for k in weights)
        confidence = float(np.clip(confidence, 0.0, 1.0))

        is_spec = confidence >= self.IS_SPECTROGRAM_THRESHOLD
        spec_type = self._infer_type(img) if is_spec else "unknown"

        return {
            "is_spectrogram": is_spec,
            "confidence": round(confidence, 3),
            "type": spec_type,
            "colormap_guess": colormap_guess,
            "reason": self._reason(scores, confidence),
            "scores": {k: round(v, 3) for k, v in scores.items()},
        }

    # ── Internal helpers ──────────────────────────────────────────────────

    def _load(self, image_bytes: bytes) -> np.ndarray:
        from PIL import Image
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        return np.array(img, dtype=np.float32) / 255.0

    def _horizontal_banding_score(self, img: np.ndarray) -> float:
        """High score = adjacent rows are highly correlated (spectrogram-like)."""
        H, W = img.shape[:2]
        # Focus on centre region to avoid axis labels / titles
        y0, y1 = int(H * 0.15), int(H * 0.85)
        x0, x1 = int(W * 0.15), int(W * 0.85)
        gray = img[y0:y1, x0:x1].mean(axis=2)
        row_means = gray.mean(axis=1)
        if len(row_means) < 4:
            return 0.0
        diffs = np.abs(np.diff(row_means))
        smoothness = 1.0 - float(np.clip(diffs.std() / (row_means.std() + 1e-6), 0, 1))
        return float(np.clip(smoothness, 0, 1))

    def _colormap_score(self, img: np.ndarray) -> tuple[float, str]:
        """Check if pixel colours are consistent with a known monotone colormap."""
        try:
            import matplotlib
            import matplotlib.cm as cm
            from scipy.spatial import cKDTree
        except ImportError:
            return 0.5, "viridis"

        H, W, _ = img.shape
        # Sample from the centre 60% of the image to avoid axis labels,
        # titles, and colorbars that appear in spectrogram screenshots.
        y0, y1 = int(H * 0.2), int(H * 0.8)
        x0, x1 = int(W * 0.15), int(W * 0.85)
        centre = img[y0:y1, x0:x1]
        rng = np.random.default_rng(42)
        flat = centre.reshape(-1, 3).astype(np.float32)
        idx = rng.choice(len(flat), min(1500, len(flat)), replace=False)
        sampled = flat[idx]

        best_score = 0.0
        best_cmap = "viridis"

        for cmap_name in self.COLORMAP_NAMES:
            n = 512
            cmap = cm.get_cmap(cmap_name, n) if hasattr(cm, 'get_cmap') else matplotlib.colormaps[cmap_name].resampled(n)
            lut_rgb = cmap(np.linspace(0, 1, n))[:, :3].astype(np.float32)
            tree = cKDTree(lut_rgb)
            dists, _ = tree.query(sampled, k=1)
            mean_dist = float(dists.mean())
            # Use median distance (more robust to chrome outliers) blended
            # with mean.  Softer multiplier tolerates screenshot chrome.
            med_dist = float(np.median(dists))
            blended = 0.6 * med_dist + 0.4 * mean_dist
            score = float(np.clip(1.0 - blended * 3.5, 0, 1))
            if score > best_score:
                best_score = score
                best_cmap = cmap_name

        return best_score, best_cmap

    def _saturation_score(self, img: np.ndarray) -> float:
        """Spectrograms use sequential colormaps — structured saturation pattern."""
        r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
        cmax = np.maximum(np.maximum(r, g), b)
        cmin = np.minimum(np.minimum(r, g), b)
        saturation = (cmax - cmin) / (cmax + 1e-6)
        mean_sat = float(saturation.mean())
        std_sat = float(saturation.std())
        # Screenshots have chrome (axis labels, colorbars) that creates high
        # saturation variance.  Natural photos have BOTH high mean AND high
        # variance.  Spectrograms: moderate mean, any variance.
        # Penalize only when both mean and variance are high (natural photo).
        photo_score = mean_sat * std_sat  # high only for natural photos
        return float(np.clip(1.0 - photo_score * 2.5, 0, 1))

    def _horizontal_edge_score(self, img: np.ndarray) -> float:
        """Spectrograms have predominantly horizontal edges (frequency bands)."""
        try:
            from scipy.ndimage import sobel
        except ImportError:
            return 0.5
        gray = img.mean(axis=2)
        hor_edges = np.abs(sobel(gray, axis=0))  # horizontal edges
        ver_edges = np.abs(sobel(gray, axis=1))  # vertical edges
        h_mean = float(hor_edges.mean())
        v_mean = float(ver_edges.mean())
        total = h_mean + v_mean + 1e-8
        # Higher h_mean ratio → more likely a spectrogram
        return float(np.clip(h_mean / total, 0, 1))

    def _infer_type(self, img: np.ndarray) -> str:
        """
        Infer mel vs linear from energy distribution.
        Mel: more energy in the lower portion (low-freq bands are stretched).
        Linear: energy more uniformly distributed.
        """
        gray = img.mean(axis=2)  # (H, W)
        H = gray.shape[0]
        # Bottom half of image = low frequencies (librosa convention: low=bottom)
        bottom_energy = float(gray[H // 2:, :].mean())
        top_energy = float(gray[: H // 2, :].mean())
        ratio = bottom_energy / (top_energy + 1e-6)
        # Mel: more energy in bottom half (low frequencies dominate in speech/music)
        return "mel" if ratio > 1.05 else "linear"

    def _reason(self, scores: Dict[str, float], confidence: float) -> str:
        top = sorted(scores.items(), key=lambda x: -x[1])[:2]
        drivers = ", ".join(f"{k}={v:.2f}" for k, v in top)
        return f"confidence={confidence:.2f} driven by {drivers}"
