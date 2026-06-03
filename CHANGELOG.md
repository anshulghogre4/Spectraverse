# Changelog

All notable changes to SpectraVerse are documented here.  
Format: `[Date] · Sprint · Component · Change`

---

## [2026-06-02] · Sprint 1 · Implementation & Hardening

**Session type**: Full implementation, multi-agent audit, blocker remediation  
**Status**: ✅ SPRINT 1 COMPLETE — all blockers resolved, app runnable end-to-end

### Added

- `backend/app/__init__.py` — marks `app/` as a Python package (required for test imports)
- `backend/requirements-dev.txt` — separates dev dependencies (`pytest`, `pytest-asyncio`, `httpx`) from production image
- `frontend/lib/api.ts` — typed API client: `analyzeImage()`, `analyzeAudio()`, `healthCheck()` with full TypeScript types (`ImageFeatures`, `AudioFeatures`, `AnalysisResult<T>`)
- `frontend/next.config.js` — Next.js config with `output: 'standalone'` for production Docker builds
- `frontend/jest.config.js` — Jest config with `jsdom` environment, `ts-jest` transform, CSS mock
- `frontend/__mocks__/styleMock.js` — CSS import mock for Jest
- `frontend/.env.local` — sets `NEXT_PUBLIC_API_URL=http://localhost:8000` for local dev
- `.env.example` — documents all required environment variables with inline comments
- `docs/CHANGELOG.md` → moved to project root as `CHANGELOG.md`

### Changed

**Backend**

| File | What changed |
|---|---|
| `backend/requirements.txt` | Fixed `numpy==2.4.6` (non-existent on PyPI) → `numpy>=1.26.0,<3.0`; added `Pillow>=10.0.0`, `scipy>=1.11.0`, `matplotlib>=3.7.0`; moved `pytest`/`pytest-asyncio` to `requirements-dev.txt` |
| `backend/app/main.py` | Complete rewrite: separate `numpy` import guard (decoupled from librosa); imports + instantiates all 6 service classes with graceful degradation; replaced deprecated `@app.on_event` with `lifespan` context manager; wired Redis client with try/except fallback; `analyze_image` now delegates to `VisionAnalyzer`; `analyze_audio` now delegates to `AudioAnalyzer`; `SEMANTIC_MAPPINGS_PATH` respects `SEMANTIC_MAPPINGS_PATH` env var (Docker-safe) |
| `backend/app/backend_vision_analyzer.py` | Guarded `from PIL import Image` in try/except at module level (was a hard import crash); replaced non-deterministic `np.random.randint` color sampling with deterministic grid sampling; added scipy fallback for texture density when scipy unavailable |
| `backend/Dockerfile` | Updated base image `python:3.11-slim` → `python:3.13-slim` (matches `.python-version`); added `apt-get upgrade -y` to patch OS CVEs; replaced `HEALTHCHECK CMD curl` (curl absent in slim) with `python -c "urllib.request.urlopen(...)"` |
| `backend/tests/test_api.py` | Fixed `from backend.app.main import app` → `from app.main import app` (correct for running pytest from `backend/`); tests now valid |

**Frontend**

| File | What changed |
|---|---|
| `frontend/package.json` | Fixed invalid `three` version `^r156` → `^0.156.0`; moved `typescript` from `dependencies` → `devDependencies`; added `jest-environment-jsdom`, `ts-jest`, `@testing-library/user-event`, `@types/three` |
| `frontend/tsconfig.json` | Removed `"types": ["node", "react", "react-dom"]` override — blocked `@types/three` auto-resolution; TypeScript now auto-discovers all `@types/*` packages |
| `frontend/components/UploadZone.tsx` | Added `mode`/`style` props; added `audio/x-wav` to accepted MIME types; added `analysis_received` status guard (surfaces backend message as error instead of silent empty result); fixed `FeatureTile` NaN guard for object-valued features; added `'use client'` directive |
| `frontend/Dockerfile` | Refactored to multi-stage build (builder + runner); upgraded `node:18-alpine` → `node:20-alpine`; added `apk upgrade --no-cache`; added `ARG NEXT_PUBLIC_API_URL` + `ENV` so API URL is baked in at build time; `npm ci` → `npm install` (no lock file yet); runner copies only `.next/standalone` + `.next/static` (~100MB vs ~700MB) |

**Infrastructure**

| File | What changed |
|---|---|
| `docker-compose.yml` | Both `build:` blocks changed to `context: .` with explicit `dockerfile:` path (fixes COPY path mismatch in both Dockerfiles); added `SEMANTIC_MAPPINGS_PATH`, `AZURE_BLOB_KEY`, `AZURE_VISION_API_KEY` env vars to backend; added `semantic_mappings.json` bind-mount (rule changes don't require rebuild); Redis port changed from `ports` → `expose` (no longer exposed to host); added Redis named volume + `--appendonly yes` for persistence; added `healthcheck` on Redis (`redis-cli ping`); backend `depends_on` now waits for Redis `service_healthy`; added `restart: unless-stopped` on all services; frontend build now passes `NEXT_PUBLIC_API_URL` as build arg |
| `.gitignore` | Added `.next/`; removed `package-lock.json` from ignore list (lock files must be committed); changed `*.local` → explicit `.env.local` + `.env.*.local`; added explanatory comments |

### Fixed (blocker-severity issues resolved)

1. `docker-compose up` would fail to build — both Dockerfiles used wrong COPY paths relative to their build context
2. Backend HEALTHCHECK permanently failed — `curl` not available in `python:3.13-slim`
3. `semantic_mappings.json` always empty in Docker — path resolution `parents[2]` resolves to `/` inside container; fixed via explicit env var
4. `numpy==2.4.6` does not exist on PyPI — `pip install` fails, blocking all installs
5. `Pillow` missing — all image analysis silently returned stubs
6. `scipy` missing — `VisionAnalyzer._extract_texture_density` raised `ImportError` at runtime
7. `test_api.py` broken import — `ModuleNotFoundError: No module named 'backend'`
8. No `jest.config.js` — all frontend tests crashed on first JSX token
9. `jest-environment-jsdom` missing — `npm test` failed immediately
10. No `next.config.js` — build could not configure standalone output

---

## [2026-05-29] · Sprint 1 · Planning & Scaffold

**Session type**: Initial planning, documentation, scaffold generation  
**Status**: ✅ Planning complete — scaffold templates produced

### Added

- `SETUP.md` — complete local dev environment guide (Next.js + FastAPI + Docker), steps 1–6
- `QUICK_START.md` — 5-minute quickstart for returning developers
- `semantic_mappings.json` — deterministic AI mapping rules:
  - `image_to_audio`: brightness → tempo, color_temp → instrument, texture → rhythm, edges → frequency, scene → style
  - `audio_to_visual`: BPM → particle speed, bass_energy → color intensity, treble → brightness, centroid → hue, genre → visual style
  - `creative_modifiers`: 7 styles (Funny, Horror, Emotional, Bassy, Electrifying, Spiritual, Experimental)
  - `quality_validation`: thresholds for output validation
- `docker-compose.yml` — multi-container template: backend (8000), redis (6379), frontend (3000)
- `backend/app/main.py` — FastAPI scaffold: CORS, `/health`, `/api/analyze-image`, `/api/analyze-audio`, `/api/mappings`
- `backend/requirements.txt` — pinned production dependencies
- `backend/Dockerfile` — Python backend container
- `frontend/app/page.tsx` — mode selector (Classic/Creative) + 7 creative style pills + dual UploadZone layout
- `frontend/app/layout.tsx` — Next.js root layout with metadata
- `frontend/app/globals.css` — Tailwind base + Inter font + dark background
- `frontend/components/UploadZone.tsx` — drag-drop file upload with preview, size validation, framer-motion animations
- `frontend/package.json` — Next.js 14, React 18, framer-motion, three.js, @react-three/fiber
- `frontend/tailwind.config.ts` — Tailwind configuration
- `frontend/tsconfig.json` — TypeScript configuration
- `backend/app/backend_audio_analyzer.py` — `AudioAnalyzer` class: BPM, pitch, spectral centroid, bass/treble energy, MFCC, genre, vibe, complexity
- `backend/app/backend_vision_analyzer.py` — `VisionAnalyzer` class: brightness, color temp, dominant colors, texture density, scene type, mood, composition
- `backend/app/backend_semantic_mapper.py` — `SemanticMapper` class: maps features → audio/visual parameters via `semantic_mappings.json`
- `backend/app/backend_dsp_synthesizer.py` — `DSPSynthesizer` class: waveform synthesis from semantic parameters
- `backend/app/backend_image_to_audio_pipeline.py` — `ImageToAudioPipeline` class: end-to-end image → audio
- `backend/app/backend_audio_to_visual_pipeline.py` — `AudioToVisualPipeline` class: end-to-end audio → visual config
- `docs/SPRINT_1_COMPLETE.md` — sprint status report
- `docs/BUILD_MANIFEST.md` — session deliverables manifest
- `docs/BUILD_STATUS.md`, `docs/BUILD_PROGRESS.md` — build tracking
- `.python-version` — pins Python 3.13 for pyenv / editor integrations
- `.github/workflows/ci.yml` — CI workflow

### Notes

- Sprint 1 was primarily a planning + scaffold session; service classes were generated but not wired into `main.py`
- All generate endpoints (`/api/generate/image-to-audio`, `/api/generate/audio-to-visual`) are Sprint 2 stubs
- WebAudio API and Three.js integrations are Sprint 2 deliverables

---

## Upcoming

### Sprint 2 — Local DSP & WebAudio *(planned)*

- WebAudio FFT/STFT real-time spectrogram visualizer in browser
- Wire `ImageToAudioPipeline` into `/api/generate/image-to-audio` (librosa + DSP)
- Wire `AudioToVisualPipeline` into `/api/generate/audio-to-visual`
- Three.js `<Canvas>` particle system reading `visual_config` output
- `useAudioPlayback` hook: decode PCM float array → `AudioContext` → play
- Lock file committed (`package-lock.json`)

### Sprint 3 — Azure Vision API *(planned)*

- Azure Computer Vision integration in `VisionAnalyzer`
- Azure Blob Storage for generated audio/visual output
- Job queue via Redis (async generation with polling)
