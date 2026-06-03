"""
Semantic Mapping Engine
Maps image/audio features → audio/visual parameters
Uses deterministic rules from semantic_mappings.json
All mappings are explainable and cacheable
"""

import json
from typing import Dict, Any, Optional
import os


class SemanticMapper:
    """Map semantic features to generation parameters."""
    
    def __init__(self, mappings_path: str = "../semantic_mappings.json"):
        self.mappings = self._load_mappings(mappings_path)
        self.creative_modifiers = self.mappings.get("creative_mode_modifiers", {})
    
    def _load_mappings(self, path: str) -> Dict[str, Any]:
        """Load semantic mappings JSON."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    # ============================================================
    # IMAGE → AUDIO MAPPING
    # ============================================================
    
    def image_to_audio_params(
        self,
        image_features: Dict[str, Any],
        mode: str = "classic",
        style: str = ""
    ) -> Dict[str, Any]:
        """
        Map image features to audio generation parameters.
        
        Args:
            image_features: {brightness, color_temp, texture, mood, scene}
            mode: "classic" or "creative"
            style: Modifier style (if creative mode)
        
        Returns:
            Audio params: {pitch, bpm, instruments, reverb, intensity, effects}
        """
        # Extract base parameters from image
        brightness = image_features.get("brightness", 0.5)
        color_temp = image_features.get("color_temperature", "neutral")
        texture = image_features.get("texture_density", "medium")
        scene = image_features.get("scene_type", "indoor")
        mood = image_features.get("mood", "neutral")
        
        # Map brightness → pitch
        pitch = self._map_brightness_to_pitch(brightness)
        
        # Map color temperature → instruments
        instruments = self._map_color_to_instruments(color_temp)
        
        # Map texture → complexity
        complexity, layering = self._map_texture_to_complexity(texture)
        
        # Map scene → BPM
        bpm = self._map_scene_to_bpm(scene)
        
        # Base parameters
        params = {
            "pitch": pitch,
            "bpm": bpm,
            "instruments": instruments,
            "complexity": complexity,
            "layering": layering,
            "reverb": self._map_texture_to_reverb(texture),
            "intensity": brightness,  # Brightness → intensity
            "effects": self._infer_effects(image_features),
        }
        
        # Apply creative mode modifiers
        if mode == "creative" and style:
            params = self._apply_creative_modifier(params, style)
        
        return params
    
    def _map_brightness_to_pitch(self, brightness: float) -> int:
        """Map brightness (0-1) to pitch (Hz)."""
        mappings = {
            "0.0-0.2": 110,
            "0.2-0.4": 165,
            "0.4-0.6": 220,
            "0.6-0.8": 330,
            "0.8-1.0": 440,
        }
        
        if brightness < 0.2:
            return 110
        elif brightness < 0.4:
            return 165
        elif brightness < 0.6:
            return 220
        elif brightness < 0.8:
            return 330
        else:
            return 440
    
    def _map_color_to_instruments(self, color_temp: str) -> list:
        """Map color temperature to instrument set."""
        temp_map = {
            "cool": ["strings", "synth_pad", "flute"],
            "neutral": ["piano", "guitar", "vibraphone"],
            "warm": ["pad", "organ", "cello"],
        }
        return temp_map.get(color_temp, ["piano"])
    
    def _map_texture_to_complexity(self, texture: str) -> tuple:
        """Map texture density to complexity and layering."""
        texture_map = {
            "smooth": (0.2, 1),
            "medium": (0.6, 4),
            "dense": (0.9, 8),
        }
        return texture_map.get(texture, (0.5, 2))
    
    def _map_texture_to_reverb(self, texture: str) -> float:
        """Map texture to reverb amount."""
        texture_map = {
            "smooth": 0.8,
            "medium": 0.4,
            "dense": 0.1,
        }
        return texture_map.get(texture, 0.4)
    
    def _map_scene_to_bpm(self, scene: str) -> int:
        """Map scene type to BPM."""
        scene_map = {
            "nature": 70,
            "indoor": 85,
            "sky": 65,
            "water": 75,
            "urban": 100,
        }
        return scene_map.get(scene, 90)
    
    def _infer_effects(self, image_features: Dict) -> list:
        """Infer effects from image characteristics."""
        effects = []
        
        if image_features.get("brightness", 0.5) < 0.3:
            effects.append("distortion")
        
        if image_features.get("texture_density") == "dense":
            effects.append("compression")
        
        if image_features.get("composition") == "scattered":
            effects.append("delay")
        
        if not effects:
            effects = ["reverb"]
        
        return effects
    
    def _apply_creative_modifier(self, params: Dict, style: str) -> Dict:
        """Apply creative mode modifiers to parameters."""
        modifier = self.creative_modifiers.get(style, {})
        
        if "pitch_shift" in modifier:
            params["pitch"] = int(params["pitch"] * modifier["pitch_shift"])
        
        if "tempo_shift" in modifier:
            params["bpm"] = int(params["bpm"] * modifier["tempo_shift"])
        
        if "effect_intensity" in modifier:
            intensity_mult = modifier["effect_intensity"]
            params["intensity"] = min(params.get("intensity", 0.5) * intensity_mult, 1.0)
        
        if "reverb_boost" in modifier:
            params["reverb"] = min(params["reverb"] * modifier["reverb_boost"], 1.0)
        
        return params
    
    # ============================================================
    # AUDIO → VISUAL MAPPING
    # ============================================================
    
    def audio_to_visual_params(
        self,
        audio_features: Dict[str, Any],
        mode: str = "classic",
        style: str = ""
    ) -> Dict[str, Any]:
        """
        Map audio features to visual generation parameters.
        
        Args:
            audio_features: {bpm, bass_energy, treble_energy, centroid, genre, vibe}
            mode: "classic" or "creative"
            style: Modifier style (if creative mode)
        
        Returns:
            Visual params: {particle_count, speed, colors, effects, darkness}
        """
        bpm = audio_features.get("bpm", 90)
        bass = audio_features.get("bass_energy", 0.5)
        treble = audio_features.get("treble_energy", 0.5)
        centroid = audio_features.get("spectral_centroid", 3000)
        
        # Map BPM → animation speed
        particle_speed = self._map_bpm_to_speed(bpm)
        
        # Map bass → darkness
        darkness = self._map_bass_to_darkness(bass)
        
        # Map treble → particle count
        particle_count = self._map_treble_to_particles(treble)
        
        # Map frequency → colors
        colors = self._map_centroid_to_colors(centroid)
        
        # Base parameters
        params = {
            "particle_count": particle_count,
            "particle_speed": particle_speed,
            "color_palette": colors,
            "darkness": darkness,
            "brightness": 1.0 - darkness,
            "effects": self._infer_visual_effects(audio_features),
        }
        
        # Apply creative modifier
        if mode == "creative" and style:
            params = self._apply_visual_modifier(params, style)
        
        return params
    
    def _map_bpm_to_speed(self, bpm: int) -> float:
        """Map BPM to particle animation speed."""
        if bpm < 60:
            return 0.3
        elif bpm < 90:
            return 0.7
        elif bpm < 120:
            return 1.2
        elif bpm < 160:
            return 2.0
        else:
            return 3.0
    
    def _map_bass_to_darkness(self, bass_energy: float) -> float:
        """Map bass energy to darkness (0-1)."""
        return min(bass_energy, 1.0)
    
    def _map_treble_to_particles(self, treble_energy: float) -> int:
        """Map treble energy to particle count."""
        if treble_energy < 0.2:
            return 100
        elif treble_energy < 0.4:
            return 300
        elif treble_energy < 0.6:
            return 600
        elif treble_energy < 0.8:
            return 1000
        else:
            return 1500
    
    def _map_centroid_to_colors(self, centroid: float) -> list:
        """Map spectral centroid to color palette."""
        if centroid < 2000:
            return ["#FF0000", "#FF6600", "#FF9900"]  # Warm
        elif centroid < 5000:
            return ["#00FF00", "#00FF99", "#00FFFF"]  # Neutral
        elif centroid < 8000:
            return ["#0099FF", "#0066FF", "#0033FF"]  # Cool
        else:
            return ["#FF00FF", "#FF00AA", "#FF0055"]  # Bright
    
    def _infer_visual_effects(self, audio_features: Dict) -> list:
        """Infer visual effects from audio."""
        effects = []
        
        bass = audio_features.get("bass_energy", 0.5)
        if bass > 0.7:
            effects.append("bloom")
        
        treble = audio_features.get("treble_energy", 0.5)
        if treble > 0.7:
            effects.append("chromatic_aberration")
        
        if audio_features.get("genre") == "electronic":
            effects.append("glitch")
        
        if not effects:
            effects = ["glow"]
        
        return effects
    
    def _apply_visual_modifier(self, params: Dict, style: str) -> Dict:
        """Apply visual creative modifiers."""
        # Extended visual modifiers could be added here
        return params


# Example usage
if __name__ == "__main__":
    mapper = SemanticMapper()
    
    # Test image → audio
    img_features = {
        "brightness": 0.7,
        "color_temperature": "warm",
        "texture_density": "medium",
        "scene_type": "urban",
        "mood": "energetic",
    }
    
    audio_params = mapper.image_to_audio_params(img_features)
    print("Image → Audio:", audio_params)
    
    # Test audio → visual
    audio_features = {
        "bpm": 120,
        "bass_energy": 0.65,
        "treble_energy": 0.45,
        "spectral_centroid": 3200,
        "genre": "electronic",
    }
    
    visual_params = mapper.audio_to_visual_params(audio_features)
    print("Audio → Visual:", visual_params)
