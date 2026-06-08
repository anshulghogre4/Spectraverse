from contextlib import asynccontextmanager
import asyncio
import io
import base64
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path
from dotenv import load_dotenv
import json
import tempfile
import shutil
from typing import Dict, Any

load_dotenv()

# ── Optional dependency guards ─────────────────────────────────────────────

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from PIL import Image, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

try:
    import scipy.io.wavfile as _wavfile
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# ── Semantic mappings path (resolved before service instantiation) ─────────

_root = Path(__file__).resolve().parents[2]
_default_mappings_path = _root / "semantic_mappings.json"
SEMANTIC_MAPPINGS_PATH = Path(os.getenv("SEMANTIC_MAPPINGS_PATH", str(_default_mappings_path)))

try:
    with open(SEMANTIC_MAPPINGS_PATH, "r", encoding="utf-8") as f:
        SEMANTIC_MAPPINGS: Dict[str, Any] = json.load(f)
except FileNotFoundError:
    print(f"⚠️  semantic_mappings.json not found at {SEMANTIC_MAPPINGS_PATH}")
    SEMANTIC_MAPPINGS = {}

# ── Service class imports + instantiation (graceful degradation) ───────────

try:
    from app.backend_vision_analyzer import VisionAnalyzer
    _vision_analyzer = VisionAnalyzer(use_azure=bool(os.getenv("AZURE_VISION_API_KEY")))
    VISION_ANALYZER_AVAILABLE = True
except Exception as e:
    print(f"⚠️  VisionAnalyzer unavailable: {e}")
    VISION_ANALYZER_AVAILABLE = False
    _vision_analyzer = None

try:
    from app.backend_audio_analyzer import AudioAnalyzer
    _audio_analyzer = AudioAnalyzer()
    AUDIO_ANALYZER_AVAILABLE = True
except Exception as e:
    print(f"⚠️  AudioAnalyzer unavailable: {e}")
    AUDIO_ANALYZER_AVAILABLE = False
    _audio_analyzer = None

try:
    from app.backend_semantic_mapper import SemanticMapper
    # Pass absolute path — relative default breaks when CWD ≠ repo root
    _semantic_mapper = SemanticMapper(mappings_path=str(SEMANTIC_MAPPINGS_PATH))
    SEMANTIC_MAPPER_AVAILABLE = True
except Exception as e:
    print(f"⚠️  SemanticMapper unavailable: {e}")
    SEMANTIC_MAPPER_AVAILABLE = False
    _semantic_mapper = None

try:
    from app.backend_dsp_synthesizer import DSPSynthesizer
    _dsp_synthesizer = DSPSynthesizer(sr=22050, duration=15.0)
    DSP_AVAILABLE = True
except Exception as e:
    print(f"⚠️  DSPSynthesizer unavailable: {e}")
    DSP_AVAILABLE = False
    _dsp_synthesizer = None

try:
    from app.backend_image_to_audio_pipeline import ImageToAudioPipeline
    if VISION_ANALYZER_AVAILABLE and SEMANTIC_MAPPER_AVAILABLE and DSP_AVAILABLE:
        _image_pipeline: Any = ImageToAudioPipeline(
            vision_analyzer=_vision_analyzer,
            semantic_mapper=_semantic_mapper,
            dsp_synthesizer=_dsp_synthesizer,
            redis_client=None,
        )
        IMAGE_PIPELINE_AVAILABLE = True
    else:
        IMAGE_PIPELINE_AVAILABLE = False
        _image_pipeline = None
except Exception as e:
    print(f"⚠️  ImageToAudioPipeline unavailable: {e}")
    IMAGE_PIPELINE_AVAILABLE = False
    _image_pipeline = None

try:
    from app.backend_audio_to_visual_pipeline import AudioToVisualPipeline
    if AUDIO_ANALYZER_AVAILABLE and SEMANTIC_MAPPER_AVAILABLE:
        _audio_pipeline: Any = AudioToVisualPipeline(
            audio_analyzer=_audio_analyzer,
            semantic_mapper=_semantic_mapper,
            redis_client=None,
        )
        AUDIO_PIPELINE_AVAILABLE = True
    else:
        AUDIO_PIPELINE_AVAILABLE = False
        _audio_pipeline = None
except Exception as e:
    print(f"⚠️  AudioToVisualPipeline unavailable: {e}")
    AUDIO_PIPELINE_AVAILABLE = False
    _audio_pipeline = None

try:
    from app.backend_spectrogram_detector import SpectrogramDetector
    from app.backend_spectrogram_preprocessor import SpectrogramPreprocessor
    from app.backend_spectrogram_inverter import SpectrogramInverter
    _spec_detector = SpectrogramDetector()
    _spec_inverter = SpectrogramInverter()
    SPECTROGRAM_INVERSION_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Spectrogram inversion unavailable: {e}")
    SPECTROGRAM_INVERSION_AVAILABLE = False
    _spec_detector = None
    _spec_inverter = None

# ── Foundry IQ agent (Sprint 3) ────────────────────────────────────────────
try:
    from app.backend_foundry_agent import (
        FoundryAgent,
        build_foundry_pipeline_response,
    )
    _foundry_agent: Any = FoundryAgent()
    FOUNDRY_AGENT_AVAILABLE = True
except Exception as e:
    print(f"⚠️  FoundryAgent unavailable: {e}")
    FOUNDRY_AGENT_AVAILABLE = False
    _foundry_agent = None
    build_foundry_pipeline_response = None  # type: ignore

# ── WAV encoding helper ────────────────────────────────────────────────────

def _encode_wav_b64(waveform: Any, sample_rate: int = 22050) -> str:
    """Convert numpy float array → base64 WAV string (data: URI ready)."""
    if not NUMPY_AVAILABLE or not SCIPY_AVAILABLE:
        return ""
    try:
        audio_f32 = np.array(waveform, dtype=np.float32)
        buf = io.BytesIO()
        _wavfile.write(buf, sample_rate, audio_f32)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except Exception as e:
        print(f"WAV encoding error: {e}")
        return ""

# ── Redis ──────────────────────────────────────────────────────────────────

_redis_client = None

# ── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis_client

    # Redis
    try:
        import redis as _redis
        _redis_client = _redis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379"), decode_responses=True
        )
        _redis_client.ping()
        print("✅ Redis connected")
    except Exception as e:
        print(f"⚠️  Redis unavailable ({e}) — caching disabled")
        _redis_client = None

    # Pre-load scipy.ndimage to absorb the 1-3s cold-start on first analysis
    try:
        from scipy import ndimage as _  # noqa: F401
        print("✅ scipy.ndimage pre-loaded")
    except Exception:
        pass

    print("✅ SpectraVerse API v0.2.0 ready")
    print(f"   Mappings loaded : {bool(SEMANTIC_MAPPINGS)} — {list(SEMANTIC_MAPPINGS.keys())}")
    print(f"   VisionAnalyzer  : {VISION_ANALYZER_AVAILABLE}")
    print(f"   AudioAnalyzer   : {AUDIO_ANALYZER_AVAILABLE}")
    print(f"   SemanticMapper  : {SEMANTIC_MAPPER_AVAILABLE}")
    print(f"   DSPSynthesizer  : {DSP_AVAILABLE}")
    print(f"   ImagePipeline   : {IMAGE_PIPELINE_AVAILABLE}")
    print(f"   AudioPipeline   : {AUDIO_PIPELINE_AVAILABLE}")
    print(f"   FoundryAgent    : {FOUNDRY_AGENT_AVAILABLE}")
    if FOUNDRY_AGENT_AVAILABLE and _foundry_agent:
        caps = _foundry_agent.capabilities()
        print(f"      provider chain: {caps.get('provider_chain', [])}")
        print(f"      foundry IQ live: {caps.get('foundry_live')}")
        print(f"      providers available: {caps.get('providers_available')}")

    yield

    if _redis_client:
        _redis_client.close()
    print("🛑 SpectraVerse API shutting down…")


# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SpectraVerse API",
    version="0.2.0",
    description="Multimodal AI: Image↔Audio↔Visual via spectrograms & DSP",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.2.0",
        "service": "SpectraVerse API",
        "semantic_mappings_loaded": bool(SEMANTIC_MAPPINGS),
        "capabilities": {
            "vision_analyzer": VISION_ANALYZER_AVAILABLE,
            "audio_analyzer": AUDIO_ANALYZER_AVAILABLE,
            "semantic_mapper": SEMANTIC_MAPPER_AVAILABLE,
            "dsp_synthesizer": DSP_AVAILABLE,
            "image_pipeline": IMAGE_PIPELINE_AVAILABLE,
            "audio_pipeline": AUDIO_PIPELINE_AVAILABLE,
            "spectrogram_inversion": SPECTROGRAM_INVERSION_AVAILABLE,
            "foundry_agent": FOUNDRY_AGENT_AVAILABLE,
        },
        "foundry": (
            _foundry_agent.capabilities() if FOUNDRY_AGENT_AVAILABLE and _foundry_agent else None
        ),
        "redis": _redis_client is not None,
    }

# ── Analyze image ──────────────────────────────────────────────────────────

@app.post("/api/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    if file.content_type not in ["image/png", "image/jpeg", "image/webp"]:
        raise HTTPException(status_code=400, detail="Invalid image format. Use PNG, JPEG, or WEBP.")

    image_bytes = await file.read()

    if VISION_ANALYZER_AVAILABLE and _vision_analyzer is not None:
        features = _vision_analyzer.analyze(image_bytes)
        if "error" in features:
            raise HTTPException(status_code=500, detail=features["error"])
        return {
            "status": "analysis_complete",
            "filename": file.filename,
            "features": features,
            "message": "Image analysis complete (VisionAnalyzer)",
        }

    if not PIL_AVAILABLE:
        return {
            "status": "analysis_received",
            "filename": file.filename,
            "features": {},
            "message": "Pillow not installed — install Pillow to enable image analysis",
        }

    if not NUMPY_AVAILABLE:
        return {
            "status": "analysis_received",
            "filename": file.filename,
            "features": {},
            "message": "numpy not installed — install numpy to enable image analysis",
        }

    tmp_dir = tempfile.mkdtemp(prefix="spectraverse_img_")
    try:
        tmp_path = os.path.join(tmp_dir, file.filename or "upload.bin")
        with open(tmp_path, "wb") as f:
            f.write(image_bytes)

        img = Image.open(tmp_path).convert("RGB")
        gray = img.convert("L")
        stat = list(gray.getdata())
        brightness = float(sum(stat) / len(stat) / 255.0)

        npixels = np.array(img)
        avg = npixels.reshape(-1, 3).mean(axis=0)
        r_mean, g_mean, b_mean = float(avg[0]), float(avg[1]), float(avg[2])
        color_temp = "warm" if r_mean > b_mean else "cool"

        edges = gray.filter(ImageFilter.FIND_EDGES)
        edges_arr = np.array(edges)
        edge_density = float((edges_arr > 20).sum()) / edges_arr.size

        features: Dict[str, Any] = {
            "brightness": round(brightness, 3),
            "avg_color": {"r": int(r_mean), "g": int(g_mean), "b": int(b_mean)},
            "color_temperature": color_temp,
            "texture_edge_density": round(edge_density, 4),
            "scene_type": "unknown",
        }
        return {
            "status": "analysis_complete",
            "filename": file.filename,
            "features": features,
            "message": "Image analysis complete (Pillow fallback)",
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# ── Analyze audio ──────────────────────────────────────────────────────────

@app.post("/api/analyze-audio")
async def analyze_audio(file: UploadFile = File(...)):
    if file.content_type not in ["audio/mpeg", "audio/wav", "audio/ogg", "audio/x-wav"]:
        raise HTTPException(status_code=400, detail="Invalid audio format. Use MP3, WAV, or OGG.")

    tmp_dir = tempfile.mkdtemp(prefix="spectraverse_aud_")
    try:
        tmp_path = os.path.join(tmp_dir, file.filename or "upload.bin")
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        if AUDIO_ANALYZER_AVAILABLE and _audio_analyzer is not None:
            features = _audio_analyzer.analyze(tmp_path)
            if "error" in features:
                raise HTTPException(status_code=500, detail=features["error"])
            return {
                "status": "analysis_complete",
                "filename": file.filename,
                "features": features,
                "message": "Audio analysis complete (AudioAnalyzer)",
            }

        if not LIBROSA_AVAILABLE:
            return {
                "status": "analysis_received",
                "filename": file.filename,
                "features": {},
                "message": "librosa not installed — install librosa to enable audio analysis",
            }

        y, sr = librosa.load(tmp_path, sr=None, mono=True)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        spec_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        centroid = float(np.mean(spec_centroid)) if spec_centroid.size else 0.0

        S = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)
        bass_energy = float(S[freqs <= 250, :].mean()) if S[freqs <= 250, :].size else 0.0
        treble_energy = float(S[freqs >= 4000, :].mean()) if S[freqs >= 4000, :].size else 0.0

        features = {
            "bpm": round(float(tempo), 2),
            "bass_energy": round(bass_energy, 6),
            "treble_energy": round(treble_energy, 6),
            "spectral_centroid": round(centroid, 2),
        }
        return {
            "status": "analysis_complete",
            "filename": file.filename,
            "features": features,
            "message": "Audio analysis complete (librosa fallback)",
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# ── Generate: Image → Audio ────────────────────────────────────────────────

@app.post("/api/generate/image-to-audio")
async def generate_image_to_audio(
    file: UploadFile = File(...),
    mode: str = "classic",
    style: str = "",
    duration: float = 15.0,
):
    if not IMAGE_PIPELINE_AVAILABLE or _image_pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="Image-to-audio pipeline unavailable — check VisionAnalyzer, SemanticMapper, and DSPSynthesizer dependencies",
        )
    if file.content_type not in ["image/png", "image/jpeg", "image/webp"]:
        raise HTTPException(status_code=400, detail="Invalid image format. Use PNG, JPEG, or WEBP.")

    duration = max(1.0, min(duration, 15.0))  # Hard cap: 1-15s
    image_bytes = await file.read()

    # Run blocking pipeline in thread pool — matplotlib takes ~400ms
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _image_pipeline.generate(
            image_bytes,
            mode=mode,
            style=style,
            duration=duration,
            use_cache=False,  # Cache excluded audio_array — disabled until Sprint 3 fix
        ),
    )

    if result.get("status") not in ("success", "fallback_success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))

    audio_array = result.pop("audio_array", None)
    audio_b64 = _encode_wav_b64(audio_array, result.get("sample_rate", 22050)) if audio_array is not None else ""

    return {
        "status": "success",
        "audio_b64": audio_b64,
        "sample_rate": result.get("sample_rate", 22050),
        "duration": result.get("duration", duration),
        "spectrogram": result.get("spectrogram", ""),
        "image_features": result.get("image_features", {}),
        "audio_params": result.get("audio_params", {}),
        "safety_flags": result.get("safety_flags", []),
        "cache_hit": False,
        "mode": mode,
        "style": style,
    }

# ── Generate: Image → Audio with Foundry IQ (Sprint 3) ─────────────────────

@app.post("/api/generate/image-to-audio-foundry")
async def generate_image_to_audio_foundry(
    file: UploadFile = File(...),
    mode: str = "classic",
    style: str = "",
    duration: float = 15.0,
):
    """
    Same as /api/generate/image-to-audio, but routes the parameter decision
    through the Foundry IQ pipeline:

      1. GPT-4o vision → rich semantic description of the image
      2. Foundry IQ knowledge base → music-theory citations grounded in research
      3. GPT-4o-mini → maps description + citations to DSP params

    Returns audio plus the reasoning chain and citations so the UI can render
    the agent's chain-of-thought with footnoted sources.

    Degrades gracefully: if Azure env vars are missing, returns mock citations
    and uses heuristic mapping. The is_mock flag tells the client what happened.
    """
    if not (FOUNDRY_AGENT_AVAILABLE and _foundry_agent and build_foundry_pipeline_response):
        raise HTTPException(
            status_code=503,
            detail="Foundry agent unavailable — backend_foundry_agent module not loaded",
        )
    if not (IMAGE_PIPELINE_AVAILABLE and _image_pipeline and _dsp_synthesizer):
        raise HTTPException(
            status_code=503,
            detail="Image pipeline unavailable — VisionAnalyzer/SemanticMapper/DSPSynthesizer missing",
        )
    if file.content_type not in ["image/png", "image/jpeg", "image/webp"]:
        raise HTTPException(status_code=400, detail="Use PNG, JPEG, or WEBP.")

    duration = max(1.0, min(duration, 15.0))
    image_bytes = await file.read()

    loop = asyncio.get_event_loop()

    def _run() -> Dict[str, Any]:
        # 1. Cheap local feature extraction for heuristic fallback
        image_features: Dict[str, Any] = {}
        try:
            image_features = _vision_analyzer.analyze(image_bytes) if _vision_analyzer else {}
        except Exception as e:
            logger_name = "spectraverse.foundry"
            import logging as _lg
            _lg.getLogger(logger_name).warning("VisionAnalyzer failed: %s", e)

        # 2. Run the 3-stage Foundry pipeline
        foundry_response = build_foundry_pipeline_response(
            _foundry_agent,
            image_bytes,
            style=style,
            image_features=image_features,
        )
        audio_params = foundry_response["audio_params"]

        # 3. Synthesise audio using the grounded params (reuse self.synth correctly)
        _dsp_synthesizer.duration = duration
        _dsp_synthesizer.num_samples = int(_dsp_synthesizer.sr * duration)
        waveform = _dsp_synthesizer.synthesize(audio_params)

        # 4. Encode WAV
        audio_b64 = _encode_wav_b64(waveform, _dsp_synthesizer.sr)

        return {
            **foundry_response,
            "audio_b64": audio_b64,
            "sample_rate": _dsp_synthesizer.sr,
            "duration": duration,
            "image_features": image_features,
            "mode": mode,
            "style": style,
            "status": "success",
        }

    try:
        result = await loop.run_in_executor(None, _run)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Foundry pipeline failed: {e}")

    return result


# ── Generate: Audio → Visual ───────────────────────────────────────────────

@app.post("/api/generate/audio-to-visual")
async def generate_audio_to_visual(
    file: UploadFile = File(...),
    mode: str = "classic",
    style: str = "",
):
    if not AUDIO_PIPELINE_AVAILABLE or _audio_pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="Audio-to-visual pipeline unavailable — check AudioAnalyzer and SemanticMapper dependencies",
        )
    if file.content_type not in ["audio/mpeg", "audio/wav", "audio/ogg", "audio/x-wav"]:
        raise HTTPException(status_code=400, detail="Invalid audio format. Use MP3, WAV, or OGG.")

    audio_bytes = await file.read()

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _audio_pipeline.generate(
            audio_bytes,
            mode=mode,
            style=style,
            use_cache=False,
        ),
    )

    if result.get("status") not in ("success", "fallback_success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))

    return {
        "status": "success",
        "visual_config": result.get("visual_config", {}),
        "audio_features": result.get("audio_features", {}),
        "visual_params": result.get("visual_params", {}),
        "safety_flags": result.get("safety_flags", []),
        "cache_hit": False,
        "mode": mode,
        "style": style,
    }

# ── Mappings ───────────────────────────────────────────────────────────────

@app.get("/api/mappings")
async def get_mappings(section: str = ""):
    if not SEMANTIC_MAPPINGS:
        raise HTTPException(status_code=500, detail="Semantic mappings not loaded")
    if section:
        if section in SEMANTIC_MAPPINGS:
            return SEMANTIC_MAPPINGS[section]
        raise HTTPException(status_code=404, detail=f"Section '{section}' not found")
    return SEMANTIC_MAPPINGS

# ── Spectrogram inversion (Sprint 3) ──────────────────────────────────────────

@app.post("/api/detect-spectrogram")
async def detect_spectrogram(file: UploadFile = File(...)):
    """Detect whether the uploaded image is a spectrogram."""
    if not SPECTROGRAM_INVERSION_AVAILABLE or _spec_detector is None:
        raise HTTPException(status_code=503, detail="Spectrogram detection unavailable")
    image_bytes = await file.read()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: _spec_detector.detect(image_bytes))
    return result


@app.post("/api/invert-spectrogram")
async def invert_spectrogram(
    file: UploadFile = File(...),
    colormap: str = "viridis",
    db_min: float = -80.0,
    db_max: float = 0.0,
    n_iter: int = 64,
    preset: str = "librosa_mel",
):
    """
    Reconstruct audio from a spectrogram image using Griffin-Lim inversion.

    Query params:
        preset:   librosa_mel | chrome_music_lab | wikipedia_speech
        colormap: viridis | magma | plasma | inferno | hot | jet (default: viridis)
        db_min:   minimum dB value in the color scale (default: -80)
        db_max:   maximum dB value in the color scale (default: 0)
        n_iter:   Griffin-Lim iterations — higher = better quality, slower (default: 64)
    """
    if not SPECTROGRAM_INVERSION_AVAILABLE or _spec_inverter is None:
        raise HTTPException(status_code=503, detail="Spectrogram inversion unavailable — check scipy/librosa/Pillow deps")

    if file.content_type not in ["image/png", "image/jpeg", "image/webp"]:
        raise HTTPException(status_code=400, detail="Upload a PNG, JPEG or WEBP spectrogram image")

    n_iter = max(16, min(n_iter, 256))
    image_bytes = await file.read()

    def _run():
        # 1. Detect
        detection = _spec_detector.detect(image_bytes)
        if not detection["is_spectrogram"] and detection["confidence"] < 0.3:
            raise ValueError(
                f"Image does not appear to be a spectrogram "
                f"(confidence: {detection['confidence']:.2f}). "
                f"Try a screenshot from a spectrogram viewer."
            )

        # 2. Use detected colormap if better than default
        effective_colormap = (
            detection.get("colormap_guess", colormap)
            if detection["confidence"] > 0.5
            else colormap
        )

        # 3. Pre-process: crop + colormap invert → magnitude array
        from app.backend_spectrogram_preprocessor import SpectrogramPreprocessor
        preprocessor = SpectrogramPreprocessor(
            colormap=effective_colormap,
            db_min=db_min,
            db_max=db_max,
            auto_crop=True,
        )
        magnitude, prep_meta = preprocessor.extract_magnitude(image_bytes)

        # 4. Invert via Griffin-Lim (using preset config)
        from app.backend_spectrogram_inverter import SpectrogramInverter
        try:
            inverter = SpectrogramInverter.from_preset(preset, n_iter=n_iter)
        except ValueError:
            inverter = SpectrogramInverter(n_iter=n_iter)

        audio, inv_meta = inverter.invert(magnitude)

        # 5. Encode output
        audio_b64 = inverter.encode_wav_b64(audio)
        comparison = inverter.generate_comparison_spectrogram(audio)

        return {
            "status": "success",
            "audio_b64": audio_b64,
            "sample_rate": inverter.sr,
            "duration": inv_meta["duration_seconds"],
            "reconstruction_method": "griffin_lim",
            "n_iter_used": n_iter,
            "preset_used": preset,
            "colormap_used": effective_colormap,
            "spectrogram_type": detection.get("type", "unknown"),
            "confidence": detection["confidence"],
            "comparison_spectrogram": comparison,
            "meta": {**detection, **prep_meta, **inv_meta},
        }

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _run)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inversion failed: {e}")

    return result
