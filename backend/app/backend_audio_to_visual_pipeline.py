"""
Audio-to-Visual Generation Pipeline
Mirrors image→audio architecture but generates WebGL/particle configurations
"""

from typing import Dict, Any, Optional
import json
import base64
from datetime import datetime
import hashlib
import numpy as np


class AudioToVisualPipeline:
    """Full audio→visual generation pipeline."""
    
    def __init__(self, audio_analyzer, semantic_mapper, redis_client=None):
        self.analyzer = audio_analyzer
        self.mapper = semantic_mapper
        self.redis = redis_client
        self.cache_ttl = 604800  # 7 days
    
    def generate(
        self,
        audio_data: bytes,
        mode: str = "classic",
        style: str = "",
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generate visual configuration from audio.
        
        Args:
            audio_data: Audio bytes (MP3, WAV, OGG)
            mode: "classic" or "creative"
            style: Visual style modifier
            use_cache: Use Redis cache if available
        
        Returns:
            {visual_config, spectrogram, metadata, cache_hit}
        """
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(audio_data, mode, style)
            
            # Check cache
            if use_cache and self.redis:
                cached = self._get_from_cache(cache_key)
                if cached:
                    return {
                        **cached,
                        "cache_hit": True,
                        "status": "success"
                    }
            
            # Step 1: Analyze audio
            audio_features = self.analyzer.analyze_bytes(audio_data)
            if "error" in audio_features:
                return self._fallback_generation(mode, style)
            
            # Step 2: Map to visual parameters
            visual_params = self.mapper.audio_to_visual_params(audio_features, mode, style)
            
            # Step 3: Generate visual configuration
            visual_config = self._generate_visual_config(visual_params, audio_features)
            
            # Step 4: Safety validation
            visual_config, safety_flags = self._apply_visual_safety_checks(visual_config)
            
            # Prepare output
            result = {
                "visual_config": visual_config,
                "audio_features": audio_features,
                "visual_params": visual_params,
                "safety_flags": safety_flags,
                "cache_hit": False,
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Cache result
            if use_cache and self.redis:
                self._set_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "generation_failed",
                "fallback_available": True
            }
    
    def _generate_cache_key(self, audio_data: bytes, mode: str, style: str) -> str:
        """Generate deterministic cache key."""
        key_data = f"{hashlib.sha256(audio_data).hexdigest()}_{mode}_{style}"
        return f"audio2visual:{hashlib.sha256(key_data.encode()).hexdigest()}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Retrieve from Redis cache."""
        try:
            cached_json = self.redis.get(cache_key)
            if cached_json:
                return json.loads(cached_json)
        except:
            pass
        return None
    
    def _set_cache(self, cache_key: str, result: Dict) -> None:
        """Store in Redis cache."""
        try:
            self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(result)
            )
        except:
            pass
    
    def _generate_visual_config(
        self,
        visual_params: Dict[str, Any],
        audio_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate WebGL/Three.js configuration from visual parameters.
        
        Returns:
            {
                particles: {...},
                colors: [...],
                camera: {...},
                shaders: {...},
                effects: [...]
            }
        """
        return {
            "type": "threejs_scene",
            "particles": {
                "count": visual_params.get("particle_count", 500),
                "speed": visual_params.get("particle_speed", 1.0),
                "size": 2.0,
                "behavior": "audio_reactive",
            },
            "colors": {
                "palette": visual_params.get("color_palette", ["#FF00FF"]),
                "brightness": visual_params.get("brightness", 0.7),
                "darkness": visual_params.get("darkness", 0.3),
                "saturation": 1.0,
            },
            "camera": {
                "fov": 75,
                "position": [0, 0, 100],
                "target": [0, 0, 0],
            },
            "lighting": {
                "ambient": 0.6,
                "directional": 0.8,
                "point_lights": 3,
            },
            "effects": {
                "enabled": visual_params.get("effects", []),
                "intensity": 0.7,
            },
            "animation": {
                "duration": 30.0,
                "loopable": False,
                "fps": 60,
            },
            "audio_sync": {
                "bpm": audio_features.get("bpm", 90),
                "beat_sensitivity": 0.8,
            }
        }
    
    def _apply_visual_safety_checks(self, config: Dict) -> tuple:
        """Apply safety checks for visuals."""
        flags = []
        
        # Check particle count (performance)
        if config["particles"]["count"] > 2000:
            config["particles"]["count"] = 2000
            flags.append("particle_count_capped")
        
        # Check for extreme brightness changes (seizure risk)
        effects = config["effects"]["enabled"]
        if len([e for e in effects if "flash" in e.lower()]) > 2:
            config["effects"]["intensity"] = min(config["effects"]["intensity"], 0.5)
            flags.append("flashing_reduced_for_safety")
        
        # Ensure darkness/brightness don't exceed bounds
        config["colors"]["darkness"] = min(max(config["colors"]["darkness"], 0), 1)
        config["colors"]["brightness"] = min(max(config["colors"]["brightness"], 0), 1)
        
        return config, flags
    
    def _fallback_generation(self, mode: str, style: str) -> Dict:
        """Fallback: Generate procedural-only visuals."""
        return {
            "visual_config": {
                "type": "fallback_procedural",
                "particles": {
                    "count": 300,
                    "speed": 1.0,
                    "behavior": "procedural_motion",
                },
                "colors": {
                    "palette": ["#00FF00", "#FF00FF"],
                    "brightness": 0.7,
                },
                "animation": {
                    "duration": 30.0,
                    "fps": 60,
                }
            },
            "status": "fallback_success",
            "message": "Generated fallback procedural visuals (analyzer unavailable)",
            "cache_hit": False,
        }
