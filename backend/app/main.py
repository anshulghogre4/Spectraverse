from contextlib import asynccontextmanager
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

# ── Service class imports (graceful degradation) ───────────────────────────

try:
    from app.backend_vision_analyzer import VisionAnalyzer
    _vision_analyzer = VisionAnalyzer(use_azure=bool(os.getenv("AZURE_VISION_API_KEY")))
    VISION_ANALYZER_AVAILABLE = True
except ImportError:
    VISION_ANALYZER_AVAILABLE = False
    _vision_analyzer = None

try:
    from app.backend_audio_analyzer import AudioAnalyzer
    _audio_analyzer = AudioAnalyzer()
    AUDIO_ANALYZER_AVAILABLE = True
except ImportError:
    AUDIO_ANALYZER_AVAILABLE = False
    _audio_analyzer = None

try:
    from app.backend_semantic_mapper import SemanticMapper
    _semantic_mapper_cls = SemanticMapper
    SEMANTIC_MAPPER_AVAILABLE = True
except ImportError:
    SEMANTIC_MAPPER_AVAILABLE = False
    _semantic_mapper_cls = None

try:
    from app.backend_image_to_audio_pipeline import ImageToAudioPipeline
    IMAGE_PIPELINE_AVAILABLE = True
except ImportError:
    IMAGE_PIPELINE_AVAILABLE = False

try:
    from app.backend_audio_to_visual_pipeline import AudioToVisualPipeline
    AUDIO_PIPELINE_AVAILABLE = True
except ImportError:
    AUDIO_PIPELINE_AVAILABLE = False

# ── Semantic mappings ──────────────────────────────────────────────────────

_root = Path(__file__).resolve().parents[2]
_default_mappings_path = _root / "semantic_mappings.json"
SEMANTIC_MAPPINGS_PATH = Path(os.getenv("SEMANTIC_MAPPINGS_PATH", str(_default_mappings_path)))

try:
    with open(SEMANTIC_MAPPINGS_PATH, "r", encoding="utf-8") as f:
        SEMANTIC_MAPPINGS: Dict[str, Any] = json.load(f)
except FileNotFoundError:
    print(f"Warning: semantic_mappings.json not found at {SEMANTIC_MAPPINGS_PATH}")
    SEMANTIC_MAPPINGS = {}

# ── Redis ──────────────────────────────────────────────────────────────────

_redis_client = None

# ── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis_client
    # Startup
    try:
        import redis as _redis
        _redis_client = _redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"), decode_responses=True)
        _redis_client.ping()
        print("✅ Redis connected")
    except Exception as e:
        print(f"⚠️  Redis unavailable ({e}) — caching disabled")
        _redis_client = None

    print("✅ SpectraVerse API starting…")
    print(f"   Semantic mappings loaded: {bool(SEMANTIC_MAPPINGS)} ({list(SEMANTIC_MAPPINGS.keys())})")
    print(f"   VisionAnalyzer: {VISION_ANALYZER_AVAILABLE}")
    print(f"   AudioAnalyzer:  {AUDIO_ANALYZER_AVAILABLE}")

    yield

    # Shutdown
    if _redis_client:
        _redis_client.close()
    print("🛑 SpectraVerse API shutting down…")


# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SpectraVerse API",
    version="0.1.0",
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
        "version": "0.1.0",
        "service": "SpectraVerse API",
        "semantic_mappings_loaded": bool(SEMANTIC_MAPPINGS),
        "vision_analyzer": VISION_ANALYZER_AVAILABLE,
        "audio_analyzer": AUDIO_ANALYZER_AVAILABLE,
        "redis": _redis_client is not None,
    }

# ── Analyze image ──────────────────────────────────────────────────────────

@app.post("/api/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    if file.content_type not in ["image/png", "image/jpeg", "image/webp"]:
        raise HTTPException(status_code=400, detail="Invalid image format. Use PNG, JPEG, or WEBP.")

    image_bytes = await file.read()

    # Prefer the richer VisionAnalyzer class
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

    # Fallback: inline PIL + numpy
    if not PIL_AVAILABLE:
        return {
            "status": "analysis_received",
            "filename": file.filename,
            "features": {},
            "message": "Pillow not installed; install Pillow to enable image analysis",
        }

    if not NUMPY_AVAILABLE:
        return {
            "status": "analysis_received",
            "filename": file.filename,
            "features": {},
            "message": "numpy not installed; install numpy to enable image analysis",
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

        # Prefer the richer AudioAnalyzer class
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

        # Fallback: inline librosa
        if not LIBROSA_AVAILABLE:
            return {
                "status": "analysis_received",
                "filename": file.filename,
                "features": {},
                "message": "librosa not installed; install librosa to enable audio analysis",
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

# ── Generate (Sprint 2+) ───────────────────────────────────────────────────

@app.post("/api/generate/image-to-audio")
async def generate_image_to_audio(
    file: UploadFile = File(...),
    mode: str = "classic",
    style: str = "",
):
    return {
        "job_id": "job-001-placeholder",
        "status": "queued",
        "mode": mode,
        "style": style,
        "message": "Image→Audio generation pipeline — Sprint 2",
    }

@app.post("/api/generate/audio-to-visual")
async def generate_audio_to_visual(
    file: UploadFile = File(...),
    mode: str = "classic",
    style: str = "",
):
    return {
        "job_id": "job-002-placeholder",
        "status": "queued",
        "mode": mode,
        "style": style,
        "message": "Audio→Visual generation pipeline — Sprint 2",
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
