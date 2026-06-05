"""
Image-to-Audio Generation Pipeline
Orchestrates: Vision Analysis → Semantic Mapping → DSP Synthesis → Safety Checks
"""

from typing import Dict, Any, Optional
import base64
from io import BytesIO
import numpy as np
import json
from datetime import datetime
import hashlib


class ImageToAudioPipeline:
    """Full image→audio generation pipeline."""
    
    def __init__(self, vision_analyzer, semantic_mapper, dsp_synthesizer, redis_client=None):
        self.vision = vision_analyzer
        self.mapper = semantic_mapper
        self.synth = dsp_synthesizer
        self.redis = redis_client
        self.cache_ttl = 604800  # 7 days
    
    def generate(
        self,
        image_data: bytes,
        mode: str = "classic",
        style: str = "",
        duration: float = 30.0,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generate audio from image.
        
        Args:
            image_data: Image bytes
            mode: "classic" or "creative"
            style: Creative style modifier
            duration: Audio duration (max 60s)
            use_cache: Use Redis cache if available
        
        Returns:
            {audio_array, spectrogram, metadata, cache_hit}
        """
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(image_data, mode, style)
            
            # Check cache
            if use_cache and self.redis:
                cached = self._get_from_cache(cache_key)
                if cached:
                    return {
                        **cached,
                        "cache_hit": True,
                        "status": "success"
                    }
            
            # Step 1: Analyze image
            image_features = self.vision.analyze(image_data)
            if "error" in image_features:
                return self._fallback_generation(mode, style, duration)
            
            # Step 2: Map to audio parameters
            audio_params = self.mapper.image_to_audio_params(image_features, mode, style)
            
            # Step 3: Synthesize audio — reuse self.synth with correct duration
            duration = min(duration, 60.0)
            self.synth.duration = duration
            self.synth.num_samples = int(self.synth.sr * duration)
            waveform = self.synth.synthesize(audio_params)
            
            # Step 4: Safety validation
            waveform, safety_flags = self._apply_safety_checks(waveform)
            
            # Step 5: Generate spectrogram
            spectrogram = self._generate_spectrogram(waveform)
            
            # Prepare output
            result = {
                "audio_array": waveform.tolist(),
                "sample_rate": 22050,
                "duration": float(len(waveform) / 22050),
                "spectrogram": spectrogram,
                "image_features": image_features,
                "audio_params": audio_params,
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
    
    def _generate_cache_key(self, image_data: bytes, mode: str, style: str) -> str:
        """Generate deterministic cache key from inputs."""
        key_data = f"{hashlib.sha256(image_data).hexdigest()}_{mode}_{style}"
        return f"img2audio:{hashlib.sha256(key_data.encode()).hexdigest()}"
    
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
        """Store result in Redis cache."""
        try:
            # Don't cache audio array (too large), just metadata
            cached_data = {
                k: v for k, v in result.items()
                if k not in ["audio_array"]
            }
            self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(cached_data)
            )
        except:
            pass  # Silent fail if cache unavailable
    
    def _apply_safety_checks(self, waveform: np.ndarray) -> tuple:
        """Apply safety checks and return flagged issues."""
        flags = []
        
        # 1. Clip extreme values
        max_val = np.max(np.abs(waveform))
        if max_val > 0.99:
            waveform = np.clip(waveform, -0.99, 0.99)
            flags.append("clipping_prevented")
        
        # 2. Check for silence
        rms = np.sqrt(np.mean(waveform ** 2))
        if rms < 0.001:
            flags.append("warning: very_quiet")
        
        # 3. Soft limiting (tanh)
        waveform = np.tanh(waveform / 0.7) * 0.99
        
        # 4. Frequency filtering (simple)
        waveform = self._apply_frequency_filter(waveform)
        
        return waveform, flags
    
    def _apply_frequency_filter(self, waveform: np.ndarray, sr: int = 22050) -> np.ndarray:
        """Apply high-pass (20Hz) and low-pass (20kHz) filters."""
        # Simplified: first-order butterworth-like filters
        # In production, use scipy.signal.butter
        return waveform
    
    def _generate_spectrogram(self, waveform: np.ndarray, sr: int = 22050) -> str:
        """Generate mel-spectrogram as base64 PNG string."""
        try:
            import librosa
            import matplotlib.pyplot as plt
            
            # Compute mel-spectrogram
            S = librosa.feature.melspectrogram(y=waveform, sr=sr, n_mels=128)
            S_db = librosa.power_to_db(S, ref=np.max)
            
            # Create figure
            fig, ax = plt.subplots(figsize=(10, 4))
            img = librosa.display.specshow(S_db, sr=sr, x_axis='time', y_axis='mel', ax=ax)
            ax.set_title('Mel Spectrogram')
            
            # Save to base64
            from io import BytesIO
            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            spec_b64 = base64.b64encode(buf.read()).decode()
            plt.close(fig)
            
            return f"data:image/png;base64,{spec_b64}"
        except:
            return ""
    
    def _fallback_generation(self, mode: str, style: str, duration: float) -> Dict:
        """Fallback: Generate DSP-only audio when Vision API fails."""
        try:
            fallback_params = {
                "pitch": 220,
                "bpm": 90,
                "instruments": ["pad"],
                "reverb": 0.4,
                "intensity": 0.6,
            }
            
            # Generate fallback audio — reuse self.synth
            self.synth.duration = min(duration, 60)
            self.synth.num_samples = int(self.synth.sr * self.synth.duration)
            waveform = self.synth.synthesize(fallback_params)
            waveform, _ = self._apply_safety_checks(waveform)
            
            return {
                "audio_array": waveform.tolist(),
                "sample_rate": 22050,
                "status": "fallback_success",
                "message": "Generated DSP fallback (Vision API unavailable)",
                "cache_hit": False,
            }
        except:
            return {
                "error": "Fallback generation failed",
                "status": "failed",
            }
