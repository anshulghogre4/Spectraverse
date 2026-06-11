# SpectraVerse — Project Context

## What is this
SpectraVerse is a multimodal AI demo for the Microsoft Agents League competition. It transforms between modalities: images→audio, audio→visuals, audio↔spectrograms. All flows are grounded by Foundry IQ (Azure AI Search KB + multi-provider LLM chain with cited reasoning).

## Architecture

### Backend (`backend/app/`)
- **FastAPI** app in `main.py` — all endpoints
- **FoundryAgent** (`backend_foundry_agent.py`) — multi-provider LLM chain (Azure OpenAI → OpenAI → Gemini → Groq → mock fallback) + Azure AI Search retrieval via `AzureBlobKnowledgeSourceParams` + `KnowledgeRetrievalSemanticIntent`
- **DSP Synthesizer** (`backend_dsp_synthesizer.py`) — real instrument timbres, chord progressions, drum bus
- **Audio Analyzer** (`backend_audio_analyzer.py`) — `.analyze(path)` for file paths, `.analyze_bytes(bytes)` for raw bytes
- **Spectrogram Preprocessor** (`backend_spectrogram_preprocessor.py`) — colorbar strip, entropy crop, colormap inversion, dB→amplitude
- **Spectrogram Inverter** (`backend_spectrogram_inverter.py`) — Griffin-Lim with 3 presets (librosa_mel, chrome_music_lab, wikipedia_speech)
- **Audio-to-Visual Pipeline** (`backend_audio_to_visual_pipeline.py`) — uses `.analyze_bytes()` for raw bytes

### Frontend (`frontend/`)
- Next.js app, single page at `app/page.tsx`
- Components: `UploadZone`, `VisualOutputPanel`, `AudioOutputPanel`, `SpectrogramUploadZone`, `FoundryReasoningPanel`, `InversionOutputPanel`, `GenerationProgress`
- Hook: `hooks/useAudioAnalyser.ts` — Web Audio FFT with onset detection
- API client: `lib/api.ts`

### Key API Endpoints
- `POST /api/generate/image-to-audio-foundry` — image→audio with Foundry IQ citations
- `POST /api/generate/audio-to-visual-foundry` — audio→visual with Foundry IQ citations
- `POST /api/audio-to-spectrogram` — audio→spectrogram PNG
- `POST /api/invert-spectrogram` — spectrogram image→audio (Griffin-Lim)
- `POST /api/detect-spectrogram` — classify image as spectrogram

## Important patterns
- AudioAnalyzer.analyze() expects a FILE PATH, not raw bytes. Write to temp file first.
- AudioToVisualPipeline.generate() uses .analyze_bytes() for raw bytes.
- Spectrogram inversion rejects images with confidence < 55% to prevent OOM.
- Preprocessor caps images at MAX_PIXELS = 1024*512 before processing.
- VisualOutputPanel's `pickMode()` priority: visual_config.render_mode (Foundry) > style (user) > audio features (auto).
- All renderers respond to live audio (bassRef/onsetRef from useAudioAnalyser).

## Environment
- Run backend from `backend/` directory: `uvicorn app.main:app --reload --port 8000`
- Run frontend from `frontend/` directory: `npm run dev`
- Azure AI Search for KB (East US 2), LLM providers: OpenAI direct + Gemini + Groq (Azure GPT has 0 TPM quota)
- `.env` has: OPENAI_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, AZURE_SEARCH_INDEX

## Sprint 3 status
See `docs/SPRINT_3_NEXT_STEPS.md` for full details. Most items shipped. Remaining: S3-17 (per-tool KB), S3-19 (cross-modal KB), S3-30 (AI toggle on spectrogram), S3-12 (unified status pill), S3-31 (live spectrogram strip).

Genre fine-tuning is DEFERRED — don't spend time on timbre quality.
