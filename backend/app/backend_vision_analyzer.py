"""
Vision Analysis Service
Extracts semantic features from images.
Features: colors, brightness, objects, scene type, mood, texture
"""

import json
from typing import Dict, Any, Optional
from io import BytesIO
import os

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class VisionAnalyzer:
    """Extract semantic features from images."""

    def __init__(self, use_azure: bool = False):
        self.use_azure = use_azure
        if use_azure:
            self.api_key = os.getenv("AZURE_VISION_API_KEY")
            self.endpoint = os.getenv("AZURE_VISION_ENDPOINT", "https://api.cognitive.microsoft.com")

    def analyze(self, image_data: bytes) -> Dict[str, Any]:
        if not PIL_AVAILABLE or not NUMPY_AVAILABLE:
            return {
                "error": "Pillow and numpy are required for image analysis",
                "status": "analysis_failed",
            }
        try:
            img = Image.open(BytesIO(image_data)).convert("RGB")
            img_array = np.array(img)
            return {
                "brightness": self._extract_brightness(img_array),
                "color_temperature": self._extract_color_temperature(img_array),
                "dominant_colors": self._extract_dominant_colors(img_array),
                "texture_density": self._extract_texture_density(img_array),
                "scene_type": self._infer_scene_type(img_array),
                "mood": self._infer_mood(img_array),
                "has_objects": self._detect_objects_simple(img_array),
                "composition": self._analyze_composition(img_array),
            }
        except Exception as e:
            return {"error": str(e), "status": "analysis_failed"}

    def _extract_brightness(self, img: "np.ndarray") -> float:
        return float(np.mean(img) / 255.0)

    def _extract_color_temperature(self, img: "np.ndarray") -> str:
        r, b = float(np.mean(img[:, :, 0])), float(np.mean(img[:, :, 2]))
        diff = r - b
        if diff > 20:
            return "warm"
        if diff < -20:
            return "cool"
        return "neutral"

    def _extract_dominant_colors(self, img: "np.ndarray", n_colors: int = 3) -> list:
        """Extract dominant colors using deterministic grid sampling."""
        h, w = img.shape[:2]
        # Sample at a regular grid rather than randomly (deterministic + cacheable)
        step_h = max(1, h // (n_colors + 1))
        step_w = max(1, w // (n_colors + 1))
        dominant = []
        for i in range(1, n_colors + 1):
            row = min(i * step_h, h - 1)
            col = min(i * step_w, w - 1)
            dominant.append(tuple(int(x) for x in img[row, col]))
        return dominant

    def _extract_texture_density(self, img: "np.ndarray") -> str:
        try:
            from scipy import ndimage
            gray = np.mean(img, axis=2)
            edges = np.sqrt(
                ndimage.sobel(gray, axis=0) ** 2 + ndimage.sobel(gray, axis=1) ** 2
            )
            density = float(np.mean(edges > 50))
            if density > 0.3:
                return "dense"
            if density > 0.15:
                return "medium"
            return "smooth"
        except ImportError:
            # Fallback without scipy: use standard deviation as proxy
            gray = np.mean(img, axis=2)
            std = float(np.std(gray))
            if std > 60:
                return "dense"
            if std > 30:
                return "medium"
            return "smooth"

    def _infer_scene_type(self, img: "np.ndarray") -> str:
        r = float(np.mean(img[:, :, 0]))
        g = float(np.mean(img[:, :, 1]))
        b = float(np.mean(img[:, :, 2]))
        if b > g > r:
            return "sky"
        if g > r and g > b:
            return "nature"
        if r > g and r > b:
            return "urban"
        return "indoor"

    def _infer_mood(self, img: "np.ndarray") -> str:
        brightness = float(np.mean(img) / 255.0)
        warm_score = float(np.mean(img[:, :, 0])) - float(np.mean(img[:, :, 2]))
        if brightness < 0.3:
            return "dark_mysterious"
        if brightness > 0.7:
            return "warm_energetic" if warm_score > 20 else "bright_airy"
        return "warm_calm" if warm_score > 20 else "cool_serene"

    def _detect_objects_simple(self, img: "np.ndarray") -> bool:
        return bool(float(np.var(np.mean(img, axis=2))) > 500)

    def _analyze_composition(self, img: "np.ndarray") -> str:
        gray = np.mean(img, axis=2)
        h, w = gray.shape
        center = gray[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
        top = gray[: h // 4].flatten()
        bot = gray[3 * h // 4 :].flatten()
        left = gray[:, : w // 4].flatten()
        right = gray[:, 3 * w // 4 :].flatten()
        edges_brightness = float(np.mean(np.concatenate([top, bot, left, right])))
        center_brightness = float(np.mean(center))
        if center_brightness > edges_brightness + 20:
            return "centered"
        if edges_brightness > center_brightness + 20:
            return "edges"
        return "scattered"


class SimpleVisionAnalyzer:
    """Fallback when Pillow/numpy unavailable."""

    def analyze(self, image_data: bytes) -> Dict[str, Any]:
        return {
            "brightness": 0.6,
            "color_temperature": "warm",
            "dominant_colors": [(255, 100, 50), (100, 150, 200)],
            "texture_density": "medium",
            "scene_type": "urban",
            "mood": "warm_energetic",
            "has_objects": True,
            "composition": "scattered",
        }
