from contextlib import asynccontextmanager
import asyncio
import io
import base64
from dataclasses import asdict
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
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
    from app.backend_spectrogram_inverter import SpectrogramInverter, VOCOS_AVAILABLE
    _spec_detector = SpectrogramDetector()
    _spec_inverter = SpectrogramInverter()
    SPECTROGRAM_INVERSION_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Spectrogram inversion unavailable: {e}")
    SPECTROGRAM_INVERSION_AVAILABLE = False
    VOCOS_AVAILABLE = False
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

# ── Spectrogram preset auto-selector ──────────────────────────────────────

def _auto_select_preset(detected_type: str, confidence: float) -> str:
    """Pick the best inversion preset from detector output."""
    if confidence < 0.40:
        return 'librosa_mel'
    mapping = {
        'mel':        'librosa_mel',
        'linear':     'wikipedia_speech',
        'log_linear': 'chrome_music_lab',
    }
    return mapping.get(str(detected_type).lower(), 'librosa_mel')

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

_default_cors = "http://localhost:3000,http://localhost:3001"
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_cors).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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
            "vocos_available": VOCOS_AVAILABLE,
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

def _sanitize_for_json(obj):
    """Replace NaN/Inf floats with 0 so JSON serialization doesn't fail."""
    import math
    if isinstance(obj, float):
        return 0.0 if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    if NUMPY_AVAILABLE and isinstance(obj, np.floating):
        val = float(obj)
        return 0.0 if (math.isnan(val) or math.isinf(val)) else val
    if NUMPY_AVAILABLE and isinstance(obj, np.integer):
        return int(obj)
    if NUMPY_AVAILABLE and isinstance(obj, np.ndarray):
        return _sanitize_for_json(obj.tolist())
    return obj


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
            features = _sanitize_for_json(_audio_analyzer.analyze(tmp_path))
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

        features = _sanitize_for_json({
            "bpm": round(float(tempo), 2),
            "bass_energy": round(bass_energy, 6),
            "treble_energy": round(treble_energy, 6),
            "spectral_centroid": round(centroid, 2),
        })
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

    return _sanitize_for_json({
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
    })

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

        # 5. Generate spectrogram image of the synthesised audio
        spectrogram_b64 = ""
        if LIBROSA_AVAILABLE and NUMPY_AVAILABLE:
            try:
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt

                sr = _dsp_synthesizer.sr
                S = librosa.feature.melspectrogram(y=waveform, sr=sr, n_mels=128, n_fft=2048, hop_length=512)
                S_db = librosa.power_to_db(S, ref=np.max)

                fig, ax = plt.subplots(1, 1, figsize=(6, 2), dpi=100)
                img = librosa.display.specshow(S_db, sr=sr, hop_length=512, x_axis="time", y_axis="mel", ax=ax, cmap="viridis")
                ax.set_title("")
                ax.set_xlabel("")
                ax.set_ylabel("")
                ax.set_xticks([])
                ax.set_yticks([])
                fig.tight_layout(pad=0)
                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
                plt.close(fig)
                buf.seek(0)
                spectrogram_b64 = f"data:image/png;base64,{base64.b64encode(buf.read()).decode()}"
            except Exception:
                pass

        return {
            **foundry_response,
            "audio_b64": audio_b64,
            "spectrogram": spectrogram_b64,
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

    return _sanitize_for_json(result)


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

    return _sanitize_for_json({
        "status": "success",
        "visual_config": result.get("visual_config", {}),
        "audio_features": result.get("audio_features", {}),
        "visual_params": result.get("visual_params", {}),
        "safety_flags": result.get("safety_flags", []),
        "cache_hit": False,
        "mode": mode,
        "style": style,
    })

def _describe_audio_features_heuristic(af: dict) -> str:
    """Build a rich human-readable description of audio features for the reasoning panel."""
    bpm = af.get("bpm", 90)
    genre = af.get("genre", "unknown")
    vibe = af.get("vibe", "")
    bass = float(af.get("bass_energy", 0))
    treble = float(af.get("treble_energy", 0))
    complexity = float(af.get("complexity", 0.5))
    pitch = af.get("pitch") or {}
    note = pitch.get("note", "") if isinstance(pitch, dict) else ""
    hz = pitch.get("hz", 0) if isinstance(pitch, dict) else 0
    centroid = float(af.get("spectral_centroid", 0))

    tempo_feel = "slow" if bpm < 70 else "moderate" if bpm < 110 else "fast" if bpm < 145 else "driving"
    bass_desc = "heavy bass" if bass > 0.6 else "moderate bass" if bass > 0.3 else "light bass"
    treble_desc = "bright highs" if treble > 0.5 else "warm mids" if treble > 0.25 else "dark/muffled tone"
    complexity_desc = "complex, layered" if complexity > 0.65 else "moderately textured" if complexity > 0.35 else "sparse, minimal"
    note_desc = f", dominant pitch {note} ({int(hz)} Hz)" if note and hz else ""
    centroid_desc = f", spectral centroid {int(centroid)} Hz" if centroid > 0 else ""

    return (
        f"{genre.title()} track with a {vibe} mood — {tempo_feel} at {bpm} BPM. "
        f"{bass_desc.capitalize()}, {treble_desc}, {complexity_desc} arrangement"
        f"{note_desc}{centroid_desc}."
    )


# ── Generate: Audio → Visual with Foundry IQ ──────────────────────────────

@app.post("/api/generate/audio-to-visual-foundry")
async def generate_audio_to_visual_foundry(
    file: UploadFile = File(...),
    mode: str = "classic",
    style: str = "",
):
    if not FOUNDRY_AGENT_AVAILABLE or not _foundry_agent:
        raise HTTPException(status_code=503, detail="Foundry agent unavailable")
    if file.content_type not in ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/mp3"]:
        raise HTTPException(status_code=400, detail="Audio files only")

    audio_bytes = await file.read()
    loop = asyncio.get_event_loop()

    # Step 1: analyze audio features (analyzer needs a file path, not raw bytes)
    if AUDIO_ANALYZER_AVAILABLE and _audio_analyzer is not None:
        tmp_dir = tempfile.mkdtemp(prefix="spectraverse_a2v_")
        try:
            tmp_path = os.path.join(tmp_dir, file.filename or "upload.bin")
            with open(tmp_path, "wb") as f:
                f.write(audio_bytes)
            audio_features = await loop.run_in_executor(
                None, lambda: _audio_analyzer.analyze(tmp_path)
            )
            if "error" in audio_features:
                audio_features = {}
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    else:
        audio_features = {}

    # Step 1b: LLM audio description (parallel with visual grounding)
    audio_desc, audio_desc_step = await loop.run_in_executor(
        None, lambda: _foundry_agent.describe_audio(audio_features)
    )

    # Step 2: Foundry IQ visual grounding
    foundry_result = await loop.run_in_executor(
        None, lambda: _foundry_agent.audio_to_visual(audio_features, style)
    )

    render_mode = foundry_result.get("render_mode", "orbits")
    palette = foundry_result.get("palette", ["#7c3aed", "#2563eb", "#06b6d4"])

    # Build visual_config compatible with VisualOutputPanel
    visual_config = {
        "type": "canvas2d",
        "render_mode": render_mode,
        "colors": {"palette": palette},
        "particles": {"count": 200, "speed": 1.2},
        "audio_sync": {"bpm": float(audio_features.get("bpm", 90))},
    }

    return _sanitize_for_json({
        "status": "visual_generated",
        "visual_config": visual_config,
        "visual_params": {},
        "safety_flags": [],
        "cache_hit": False,
        "style": style,
        "mode": render_mode,
        "audio_features": audio_features,
        "image_description": audio_desc,
        "citations": foundry_result.get("citations", []),
        "reasoning_steps": [asdict(audio_desc_step)] + foundry_result.get("reasoning_steps", []),
        "provider": foundry_result.get("provider", "mock"),
        "is_mock": foundry_result.get("is_mock", True),
        "is_fully_live": not foundry_result.get("is_mock", True),
    })


# ── Audio to Spectrogram (Sprint 3) ──────────────────────────────────────────

@app.post("/api/audio-to-spectrogram")
async def audio_to_spectrogram(
    file: UploadFile = File(...),
    colormap: str = "viridis",
    n_mels: int = 128,
    n_fft: int = 2048,
    hop_length: int = 512,
):
    """
    Convert an audio file to a mel spectrogram PNG image.

    Query params:
        colormap:   viridis | magma | plasma | inferno | hot | jet (default: viridis)
        n_mels:     number of mel bins (default: 128)
        n_fft:      FFT window size (default: 2048)
        hop_length: hop between frames (default: 512)
    """
    if not LIBROSA_AVAILABLE:
        raise HTTPException(status_code=503, detail="librosa not installed — required for spectrogram generation")

    if file.content_type not in ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/mp3"]:
        raise HTTPException(status_code=400, detail="Upload an audio file (MP3, WAV, OGG)")

    audio_bytes = await file.read()

    def _run():
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Load audio
        tmp_dir = tempfile.mkdtemp(prefix="spectraverse_a2s_")
        try:
            tmp_path = os.path.join(tmp_dir, file.filename or "upload.bin")
            with open(tmp_path, "wb") as f:
                f.write(audio_bytes)
            y, sr = librosa.load(tmp_path, sr=None, mono=True)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        # Generate mel spectrogram
        S = librosa.feature.melspectrogram(
            y=y, sr=sr, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels
        )
        S_db = librosa.power_to_db(S, ref=np.max)

        # Encode raw spectrogram data for lossless round-trip inversion
        raw_bytes = S_db.astype(np.float32).tobytes()
        raw_b64 = base64.b64encode(raw_bytes).decode()

        # Render to PNG — embed exact frame count + hop/sr in PNG tEXt chunk
        # so that inversion can resize the magnitude array back to the correct
        # number of time frames instead of treating every pixel column as a frame.
        actual_frames = S_db.shape[1]
        fig, ax = plt.subplots(figsize=(10, 4))
        img = librosa.display.specshow(
            S_db, sr=sr, hop_length=hop_length,
            x_axis="time", y_axis="mel", ax=ax, cmap=colormap,
        )
        ax.set_title(f"Mel Spectrogram — {file.filename or 'audio'}")
        plt.colorbar(img, ax=ax, format="%+2.0f dB")
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)

        # Inject frame metadata into the PNG tEXt chunk so the inverter
        # can recover exact timing without raw_params.
        try:
            from PIL import Image as _PILImage, PngImagePlugin as _PngMeta
            _png = _PILImage.open(buf)
            _meta = _PngMeta.PngInfo()
            _meta.add_text("spectraverse_frames", str(actual_frames))
            _meta.add_text("spectraverse_hop_length", str(hop_length))
            _meta.add_text("spectraverse_sr", str(sr))
            _meta.add_text("spectraverse_n_mels", str(n_mels))
            buf2 = io.BytesIO()
            _png.save(buf2, format="png", pnginfo=_meta)
            buf2.seek(0)
            img_b64 = base64.b64encode(buf2.read()).decode()
        except Exception:
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode()

        duration = len(y) / sr

        return {
            "status": "success",
            "spectrogram_b64": img_b64,
            "spectrogram_raw_b64": raw_b64,
            "raw_params": {
                "sr": sr,
                "n_fft": n_fft,
                "hop_length": hop_length,
                "n_mels": n_mels,
                "shape": list(S_db.shape),
                "ref_power": "np.max",
            },
            "sample_rate": sr,
            "duration": round(duration, 3),
            "n_mels": n_mels,
            "n_fft": n_fft,
            "hop_length": hop_length,
            "colormap": colormap,
            "frames": S_db.shape[1],
        }

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _run)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spectrogram generation failed: {e}")

    return result


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

# ── Knowledge Base proxy (serves docs so citations aren't blocked by private blob) ──

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"

@app.get("/api/knowledge-base/{category}/{filename}")
async def get_knowledge_doc(category: str, filename: str):
    safe_cat = Path(category).name
    safe_file = Path(filename).name
    filepath = KB_DIR / safe_cat / safe_file
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(filepath.read_text(encoding="utf-8"))

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
    ai_mode: bool = False,
    raw_data: UploadFile = File(None),
    raw_sr: int = 22050,
    raw_n_fft: int = 2048,
    raw_hop_length: int = 512,
    raw_n_mels: int = 128,
):
    """
    Reconstruct audio from a spectrogram image using Griffin-Lim inversion.

    Query params:
        preset:   librosa_mel | chrome_music_lab | wikipedia_speech
        colormap: viridis | magma | plasma | inferno | hot | jet (default: viridis)
        db_min:   minimum dB value in the color scale (default: -80)
        db_max:   maximum dB value in the color scale (default: 0)
        n_iter:   Griffin-Lim iterations — higher = better quality, slower (default: 64)
        raw_b64:  base64-encoded raw float32 mel spectrogram (dB). When provided,
                  skips all image processing (detection, preprocessing, colormap
                  inversion) and inverts directly from the raw data — lossless path.
    """
    if not SPECTROGRAM_INVERSION_AVAILABLE or _spec_inverter is None:
        raise HTTPException(status_code=503, detail="Spectrogram inversion unavailable — check scipy/librosa/Pillow deps")

    # ── Raw data lossless path ──────────────────────────────────────────────
    raw_b64_content = None
    if raw_data is not None:
        raw_b64_content = await raw_data.read()

    if raw_b64_content:
        def _run_raw():
            import librosa
            from app.backend_spectrogram_inverter import SpectrogramInverter

            # Decode raw float32 numpy array from base64.
            # The frontend sends the base64 string as a text blob, so strip
            # any whitespace / padding before decoding.
            raw_text = raw_b64_content.decode("utf-8", errors="ignore").strip()
            raw_bytes = base64.b64decode(raw_text)

            # Safety: reject payloads that would produce arrays > 50 MB
            MAX_RAW_BYTES = 50 * 1024 * 1024
            if len(raw_bytes) > MAX_RAW_BYTES:
                raise ValueError(
                    f"Raw spectrogram data too large ({len(raw_bytes) / 1024 / 1024:.1f} MB). "
                    f"Max supported: {MAX_RAW_BYTES / 1024 / 1024:.0f} MB."
                )

            S_db = np.frombuffer(raw_bytes, dtype=np.float32).copy()
            inferred_n_mels = raw_n_mels
            total_elements = len(S_db)

            if total_elements == 0:
                raise ValueError("Raw spectrogram data is empty")

            # Verify shape is compatible
            if total_elements % inferred_n_mels != 0:
                for candidate in [256, 128, 80, 64]:
                    if total_elements % candidate == 0:
                        inferred_n_mels = candidate
                        break
                else:
                    # Trim trailing bytes so it divides evenly
                    total_elements = (total_elements // inferred_n_mels) * inferred_n_mels
                    S_db = S_db[:total_elements]

            frames = total_elements // inferred_n_mels
            if frames > 10000:
                # Truncate to ~3 min at 512 hop / 22050 sr instead of OOM
                frames = 10000
                total_elements = inferred_n_mels * frames
                S_db = S_db[:total_elements]
            S_db = S_db.reshape(inferred_n_mels, frames)

            S_power = librosa.db_to_power(S_db)
            S_amplitude = np.sqrt(S_power)

            raw_n_iter = max(n_iter, 100)

            # Create inverter with exact params
            inverter = SpectrogramInverter(
                sr=raw_sr,
                n_mels=inferred_n_mels,
                n_fft=raw_n_fft,
                hop_length=raw_hop_length,
                n_iter=raw_n_iter,
                scale="mel",
            )

            # Invert using mel_to_audio directly (bypasses _cap_input_size since
            # we know the exact shape is correct)
            audio = librosa.feature.inverse.mel_to_audio(
                S_amplitude,
                sr=raw_sr,
                n_fft=raw_n_fft,
                hop_length=raw_hop_length,
                win_length=raw_n_fft,
                window="hann",
                center=True,
                power=1.0,
                n_iter=raw_n_iter,
            )

            # Normalize
            audio = audio.astype(np.float32)
            peak = float(np.max(np.abs(audio)))
            if peak > 0:
                audio = audio / peak * 0.95

            # Fade in/out to avoid clicks
            fade_samples = int(raw_sr * 0.005)
            if len(audio) > fade_samples * 2:
                fade_in = np.linspace(0, 1, fade_samples, dtype=np.float32)
                fade_out = np.linspace(1, 0, fade_samples, dtype=np.float32)
                audio[:fade_samples] *= fade_in
                audio[-fade_samples:] *= fade_out

            duration = len(audio) / raw_sr

            audio_b64 = inverter.encode_wav_b64(audio)
            comparison = inverter.generate_comparison_spectrogram(audio)

            return {
                "status": "success",
                "audio_b64": audio_b64,
                "sample_rate": raw_sr,
                "duration": round(duration, 3),
                "reconstruction_method": "griffin_lim_raw",
                "n_iter_used": raw_n_iter,
                "preset_used": "raw_lossless",
                "colormap_used": "n/a",
                "spectrogram_type": "mel",
                "confidence": 1.0,
                "comparison_spectrogram": comparison,
                "preset_auto_selected": False,
                "auto_selected_reason": "Lossless raw data path — no image processing needed",
                "meta": {
                    "raw_path": True,
                    "n_mels": inferred_n_mels,
                    "n_fft": raw_n_fft,
                    "hop_length": raw_hop_length,
                    "sr": raw_sr,
                    "n_iter": raw_n_iter,
                    "input_shape": [inferred_n_mels, frames],
                    "duration_seconds": round(duration, 3),
                },
                "vision_reasoning": None,
                "ai_mode_used": False,
            }

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, _run_raw)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Raw inversion failed: {e}")
        return result

    # ── Image-based inversion path (original) ───────────────────────────────

    if file.content_type not in ["image/png", "image/jpeg", "image/webp"]:
        raise HTTPException(status_code=400, detail="Upload a PNG, JPEG or WEBP spectrogram image")

    n_iter = max(16, min(n_iter, 256))
    image_bytes = await file.read()

    def _run():
        # 0. Read PNG frame metadata (written by audio_to_spectrogram endpoint).
        #    If present, this tells us exactly how many time frames the original
        #    audio had so we can resize the pixel-wide magnitude back to true size.
        sv_frames = None   # avoid int|None syntax — not supported in Python < 3.10
        sv_hop = None
        sv_sr = None
        sv_n_mels = None
        try:
            from PIL import Image as _PILImg
            _pil = _PILImg.open(io.BytesIO(image_bytes))
            _txt = getattr(_pil, "info", {})
            if "spectraverse_frames" in _txt:
                sv_frames = int(_txt["spectraverse_frames"])
                sv_hop = int(_txt.get("spectraverse_hop_length", "512"))
                sv_sr = int(_txt.get("spectraverse_sr", "22050"))
                sv_n_mels = int(_txt.get("spectraverse_n_mels", "128"))
        except Exception:
            pass

        # 1. Detect — reject non-spectrograms early to prevent OOM
        detection = _spec_detector.detect(image_bytes)
        if detection["confidence"] < 0.40:
            raise ValueError(
                f"Image does not appear to be a spectrogram "
                f"(confidence: {detection['confidence']:.0%}). "
                f"Upload a screenshot from a spectrogram viewer (Audacity, librosa, etc.)."
            )

        # 1b. AI mode: ask vision LLM to infer spectrogram parameters
        vision_result: Dict[str, Any] = {}
        if ai_mode and FOUNDRY_AGENT_AVAILABLE and _foundry_agent:
            vision_result = _foundry_agent.describe_spectrogram(image_bytes)

        # 2. Use detected colormap if better than default; AI result takes priority
        if vision_result:
            effective_colormap = vision_result.get("colormap", colormap)
        else:
            effective_colormap = (
                detection.get("colormap_guess", colormap)
                if detection["confidence"] > 0.5
                else colormap
            )

        # 2b. Auto-select preset from detected type; AI scale overrides when available
        detected_type = detection.get("type", "unknown")
        if vision_result:
            ai_scale = vision_result.get("scale", detected_type)
            auto_preset = _auto_select_preset(ai_scale, 1.0)
        else:
            auto_preset = _auto_select_preset(detected_type, detection["confidence"])
        effective_preset = preset if preset != 'librosa_mel' else auto_preset

        # 2c. AI db range overrides defaults when available
        effective_db_min = float(vision_result.get("db_min", db_min)) if vision_result else db_min
        effective_db_max = float(vision_result.get("db_max", db_max)) if vision_result else db_max

        # 3. Pre-process: crop + colormap invert → magnitude array
        from app.backend_spectrogram_preprocessor import SpectrogramPreprocessor
        preprocessor = SpectrogramPreprocessor(
            colormap=effective_colormap,
            db_min=effective_db_min,
            db_max=effective_db_max,
            auto_crop=True,
        )
        magnitude, prep_meta = preprocessor.extract_magnitude(image_bytes)

        # 3b. Frame-accurate resize: if the PNG carried spectraverse metadata,
        #     resize the magnitude width (time axis) from pixel-count → actual
        #     frame count using numpy 1-D interpolation per row.
        #     PIL fromarray on float32 is unreliable across Pillow versions — avoid it.
        if sv_frames and sv_frames > 0 and magnitude.shape[1] != sv_frames:
            try:
                _orig_w = magnitude.shape[1]
                _x_old = np.linspace(0.0, 1.0, _orig_w)
                _x_new = np.linspace(0.0, 1.0, sv_frames)
                _resized = np.empty((magnitude.shape[0], sv_frames), dtype=np.float32)
                for _row in range(magnitude.shape[0]):
                    _resized[_row] = np.interp(_x_new, _x_old, magnitude[_row])
                magnitude = _resized
                prep_meta["frame_resize"] = f"{_orig_w}px → {sv_frames} frames"
            except Exception:
                pass  # fallback: use uncorrected pixel width

        # 4. Invert via Griffin-Lim — if metadata gave exact params, use those;
        #    otherwise fall back to the detected/user-selected preset.
        from app.backend_spectrogram_inverter import SpectrogramInverter
        if sv_sr and sv_hop and sv_n_mels:
            inverter = SpectrogramInverter(
                sr=sv_sr, n_mels=sv_n_mels, n_fft=2048,
                hop_length=sv_hop, n_iter=n_iter, scale="mel",
            )
        else:
            try:
                inverter = SpectrogramInverter.from_preset(effective_preset, n_iter=n_iter)
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
            "preset_used": effective_preset,
            "colormap_used": effective_colormap,
            "spectrogram_type": detection.get("type", "unknown"),
            "confidence": detection["confidence"],
            "comparison_spectrogram": comparison,
            "preset_auto_selected": effective_preset != preset,
            "auto_selected_reason": (
                f"Detector identified {detected_type} scale with {detection['confidence']:.0%} confidence"
                if effective_preset != preset else ""
            ),
            "meta": {**detection, **prep_meta, **inv_meta},
            "vision_reasoning": vision_result.get("reasoning_step") if ai_mode else None,
            "ai_mode_used": ai_mode and FOUNDRY_AGENT_AVAILABLE,
        }

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _run)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except MemoryError:
        raise HTTPException(status_code=422, detail="Image too large for spectrogram inversion. Upload a smaller spectrogram screenshot.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inversion failed: {e}")

    return result
