<p align="center">
  <img src="docs/assets/spectraverse-banner.png" alt="SpectraVerse Banner" width="800" />
</p>

<h1 align="center">SpectraVerse</h1>

<p align="center">
  <strong>See Sound. Hear Images. Decode Spectrograms.</strong><br/>
  A multimodal AI agent that transforms between sight and sound — with cited reasoning.
</p>

<p align="center">
  <a href="https://purple-glacier-02aebbb0f.7.azurestaticapps.net"><strong>Live Demo</strong></a> •
  <a href="#features">Features</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#running-locally">Running Locally</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#api-reference">API</a>
</p>

---

## Hosted

| Service | URL |
|---------|-----|
| **Frontend** (Azure Static Web Apps) | https://purple-glacier-02aebbb0f.7.azurestaticapps.net |
| **Backend API** (Azure Container Apps) | https://spectraverse-api.nicetree-700994e7.westus3.azurecontainerapps.io |
| **API health check** | https://spectraverse-api.nicetree-700994e7.westus3.azurecontainerapps.io/health |

> The backend uses scale-to-zero (free tier). The first request after a period of inactivity may take 5–10 seconds to cold-start.

---

## Demo

| Image → Audio | Audio → Visual | Spectrogram ↔ Audio |
|:---:|:---:|:---:|
| Upload any image. AI analyzes colors, mood & composition, then composes original music. | Upload audio. Watch one of 50 beat-synced generative visualizations come alive. | Convert audio to spectrograms, or invert spectrogram images back to playable audio. |

> Every transformation includes **Foundry IQ citations** — the AI explains *why* it made each creative decision, grounded in music theory, colour psychology, and cross-modal research.

---

## Features

**Three Modality Bridges**

- **Image → Audio** — Upload a photo, get original music. A sunset becomes a warm minor-key piano piece. A cityscape becomes driving synth with brass hits. 17 instruments, 20+ chord progressions, 8 rhythm patterns.
- **Audio → Visual** — Upload a track, get a living canvas. 50 unique renderers (particle storms, aurora, terrain, kaleidoscope, laser shows...) all driven by real-time FFT analysis — bass energy, onset detection, BPM sync.
- **Spectrogram ↔ Audio** — Two-way spectrogram bridge. Generate spectrograms from audio, or reconstruct audio from spectrogram images using Griffin-Lim inversion with presets for Librosa, Chrome Music Lab, and Wikipedia formats.

**AI Agent with Cited Reasoning**

Every response from the Foundry IQ agent includes citations from a curated knowledge base (Azure AI Search). Not just "here's music" — but *"I chose D minor because warm colour temperatures map to minor keys per Scriabin's clavier à lumières [1], and the low edge density suggests a slow 72 BPM [2]."*

**Real Audio Synthesis, Not Samples**

The DSP engine generates audio from scratch — real waveforms with chord progressions, humanized timing (±5ms), micro-detuning (±5 cents), velocity variation, and drum patterns. Every generation sounds different.

---

## How It Works

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Upload      │────▸│  Foundry IQ      │────▸│  DSP Synthesizer│────▸│  Audio/Visual│
│  Image/Audio │     │  Agent           │     │  or Visual      │     │  Output      │
│              │     │                  │     │  Renderer       │     │              │
│              │     │  • Multi-LLM     │     │                 │     │  • WAV audio │
│              │     │    chain         │     │  • 17 instruments│    │  • 50 visual │
│              │     │  • Azure AI      │     │  • 20+ chords   │     │    modes     │
│              │     │    Search KB     │     │  • 8 rhythms    │     │  • Citations │
│              │     │  • Cited output  │     │  • Humanized    │     │              │
└─────────────┘     └──────────────────┘     └─────────────────┘     └──────────────┘
```

### The Foundry IQ Agent

A multi-provider LLM chain with automatic failover:

```
Azure OpenAI → OpenAI → Gemini → Groq → Heuristic Fallback
```

Each provider attempts the mapping. If one fails or times out, the next picks up seamlessly. The agent retrieves relevant research from Azure AI Search (colour theory, Scriabin's synesthesia mappings, cross-modal perception studies) and includes inline citations in every response.

### The DSP Engine

No pre-recorded samples. Every note is synthesized in real-time:

- **17 instruments**: piano, strings, pad, organ, cello, flute, guitar, harp, brass, marimba, synth_lead, bass, bells, choir, kalimba, sitar, steel_drum
- **20+ chord progressions**: pop, jazz, classical, cinematic, rock — major and minor
- **8 rhythm patterns**: standard 4/4, syncopated, shuffle, half-time, breakbeat, waltz, sparse
- **Humanization**: stochastic detuning, velocity variation, timing jitter

### The Visual Engine

50 Canvas 2D renderers, each driven by Web Audio API analysis:

- `analyserRef` — full FFT frequency data (waveform, spectrum bars, equalizer modes)
- `bassRef` — low-frequency energy (drives pulsing, scaling, gravity)
- `onsetRef` — transient detection (triggers bursts, flashes, spawns)
- Audio-time sync — visuals track `audioEl.currentTime`, not wall clock. Pause the audio; visuals pause. Resume; they sync perfectly.

---

## Running Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- At least one **multimodal (vision-capable) LLM API key** (see below)

> **Important:** All three LLM stages send images to the model. You **must** use a vision-capable model. Every provider in the default chain is vision-capable: GPT-4o, Gemini 2.5 Flash, and Llama 4 Scout all support image inputs.

### 1. Clone & configure

```bash
git clone https://github.com/anshulghogre4/Spectraverse.git
cd Spectraverse
```

Copy the example environment file and add your keys:

```bash
cp .env.example backend/.env
```

Open `backend/.env` and fill in your keys:

| Variable | What it's for | Required? |
|----------|--------------|-----------|
| `OPENAI_API_KEY` | GPT-4o vision + mapping | Need at least one LLM |
| `GEMINI_API_KEY` | Gemini 2.5 Flash (free tier, 1500 req/day) | Need at least one LLM |
| `GROQ_API_KEY` | Llama 4 Scout (free tier, 500 RPD, fast) | Need at least one LLM |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI (Foundry native) | Optional |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI auth | With endpoint |
| `AZURE_SEARCH_ENDPOINT` | Foundry IQ knowledge base — Azure AI Search | For citations |
| `AZURE_SEARCH_API_KEY` | Azure AI Search auth | With search endpoint |
| `FOUNDRY_KB_NAME` | Knowledge base name in Azure AI Search | With search |
| `FOUNDRY_KS_NAME` | Knowledge source name | With search |

> **Minimum to run**: One LLM key (e.g. `GEMINI_API_KEY` — free, no card required). The app works without Azure AI Search but won't show cited reasoning.

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend available at http://localhost:8000. Docs at http://localhost:8000/docs.

### 3. Frontend

Create `frontend/.env.local` so the frontend points to your local backend:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then start the dev server:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

> **Why `.env.local`?** The production build uses relative `/api/*` paths that are proxied by Azure Static Web Apps. Setting `NEXT_PUBLIC_API_URL` locally overrides this so calls go directly to your running backend instead.

### 4. Run tests

```bash
# Backend
cd backend
pip install -r requirements-dev.txt
pytest -q tests/

# Frontend type-check
cd frontend
npm run build
```

### Setting Up Foundry IQ (Azure AI Search Knowledge Base)

To get **cited reasoning** (the agent explaining *why* it made each musical choice), you need Azure AI Search:

1. **Create Azure AI Search** — Azure Portal → Create resource → "Azure AI Search" → Free tier works
2. **Create a Knowledge Base** — In Azure AI Foundry portal → Knowledge tab → Connect your search service
3. **Upload knowledge documents** — The `backend/knowledge_base/` folder contains ready-to-upload documents:

```
backend/knowledge_base/
├── cross_modal/                          # Music-vision research
│   ├── 01_scriabin_clavier_a_lumieres.md # Scriabin's colour-to-key mappings
│   ├── 02_kandinsky_color_theory.md      # Kandinsky's colour-form associations
│   ├── 03_wallace_2014_crossmodal.md     # Cross-modal perception studies
│   └── 04_film_score_visual_language.md  # Film score visual language analysis
└── spectrogram_tools/                    # Spectrogram format guides
    ├── 01_audacity.md
    ├── 02_praat.md
    ├── 03_librosa.md
    ├── 04_sonic_visualiser.md
    ├── 05_chrome_music_lab.md
    ├── 06_adobe_audition.md
    └── 07_wikipedia.md
```

4. Set `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY`, `FOUNDRY_KB_NAME`, and `FOUNDRY_KS_NAME` in `backend/.env`
5. Restart the backend — the agent will now retrieve and cite from your knowledge base

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14, TypeScript, Canvas 2D, Web Audio API, Framer Motion |
| **Backend** | Python 3.11, FastAPI, NumPy, SciPy, Librosa |
| **AI Agent** | Azure AI Foundry, Azure AI Search, Multi-LLM Chain (OpenAI + Gemini + Groq) |
| **Audio** | Custom DSP synthesis engine — 17 instruments, real-time waveform generation |
| **Spectrogram** | Matplotlib (generation), OpenCV + Griffin-Lim (inversion) |
| **Hosting** | Azure Container Apps (backend) + Azure Static Web Apps Free (frontend) |
| **CI/CD** | GitHub Actions — backend image build to ghcr.io + SWA deploy |

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/generate/image-to-audio-foundry` | POST | Image → Audio with Foundry IQ citations |
| `/api/generate/audio-to-visual-foundry` | POST | Audio → Visual with Foundry IQ citations |
| `/api/audio-to-spectrogram` | POST | Audio → Spectrogram PNG |
| `/api/invert-spectrogram` | POST | Spectrogram image → Audio (Griffin-Lim) |
| `/api/detect-spectrogram` | POST | Classify image as spectrogram |
| `/api/generate/image-to-audio` | POST | Image → Audio (heuristic, no LLM) |
| `/api/generate/audio-to-visual` | POST | Audio → Visual (heuristic, no LLM) |

### Example

```bash
# Image to Audio with Foundry IQ
curl -X POST -F "file=@sunset.jpg" \
  "https://spectraverse-api.nicetree-700994e7.westus3.azurecontainerapps.io/api/generate/image-to-audio-foundry?duration=10"

# Response includes: audio_b64, citations, image_features, audio_params
```

---

## Project Structure

```
spectraverse/
├── backend/
│   ├── app/
│   │   ├── main.py                          # FastAPI endpoints
│   │   ├── backend_foundry_agent.py         # Multi-LLM chain + Azure AI Search
│   │   ├── backend_dsp_synthesizer.py       # Audio synthesis engine
│   │   ├── backend_audio_analyzer.py        # Librosa audio analysis
│   │   ├── backend_audio_to_visual_pipeline.py
│   │   ├── backend_spectrogram_inverter.py  # Griffin-Lim inversion
│   │   └── backend_spectrogram_preprocessor.py
│   ├── knowledge_base/                      # Azure AI Search documents
│   │   ├── cross_modal/                     # Scriabin, Kandinsky, research papers
│   │   └── spectrogram_tools/               # Audacity, Librosa, Praat guides
│   └── tests/
├── frontend/
│   ├── app/page.tsx                         # Main UI — 3-tab layout
│   ├── components/
│   │   ├── VisualOutputPanel.tsx            # 50 Canvas 2D renderers
│   │   ├── AudioOutputPanel.tsx             # Audio playback + waveform
│   │   ├── UploadZone.tsx                   # Drag-drop upload
│   │   ├── SpectrogramUploadZone.tsx        # Spectrogram Lab UI
│   │   ├── FoundryReasoningPanel.tsx        # Citations display
│   │   └── GenerationProgress.tsx          # Progress indicator
│   ├── hooks/
│   │   └── useAudioAnalyser.ts             # Web Audio FFT + onset detection
│   ├── lib/api.ts                           # Backend API client
│   └── public/
│       └── staticwebapp.config.json        # SWA routing rules (proxy /api/* to backend)
├── .github/workflows/
│   ├── azure-static-web-apps-*.yml         # SWA deploy on push to main
│   ├── build-backend.yml                   # Build + push backend image to ghcr.io
│   └── ci.yml                              # Tests
└── docs/
```

---

## Foundry IQ — How We Use It

SpectraVerse is built around **Azure AI Foundry** as the reasoning backbone. Here's exactly how Foundry IQ powers every transformation:

### Three-Stage Agent Pipeline

Every image-to-audio or audio-to-visual request flows through a three-stage agent pipeline:

```
Stage 1: DESCRIBE              Stage 2: RETRIEVE               Stage 3: MAP
┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐
│ Vision Model     │──────────▸│ Foundry IQ       │──────────▸│ Mapping Model    │
│                  │           │ Knowledge Base   │           │                  │
│ "Warm sunset     │           │                  │           │ key: "D minor"   │
│  over ocean,     │           │ Retrieves:       │           │ bpm: 72          │
│  soft gradients, │           │ • Scriabin's     │           │ instruments:     │
│  low contrast"   │           │   colour-to-key  │           │   [piano, cello] │
│                  │           │ • Kandinsky's    │           │ pitch: 220       │
│                  │           │   colour theory  │           │ reverb: 0.8      │
│                  │           │ • Cross-modal    │           │                  │
│                  │           │   perception     │           │ + inline         │
│                  │           │   research       │           │   citations [1-3]│
└──────────────────┘           └──────────────────┘           └──────────────────┘
```

### Multi-Provider Resilience

| Priority | Provider | Model | Why |
|----------|----------|-------|-----|
| 1 | Azure OpenAI | GPT-4o | Native Foundry integration — vision-capable |
| 2 | OpenAI Direct | GPT-4o | Reliable fallback — vision-capable |
| 3 | Google Gemini | Gemini 2.5 Flash | Free tier (1500 req/day) — vision-capable |
| 4 | Groq | Llama 4 Scout | Free tier (500 RPD) — vision-capable, fast |
| 5 | Heuristic | — | Deterministic fallback, always works |

If all LLMs fail, a hash-based heuristic produces varied parameters from image features alone. **The app never fails.**

---

## Why SpectraVerse?

Most AI tools work in a single modality. SpectraVerse demonstrates that **AI agents can reason across modalities** — not just transforming data, but explaining the creative decisions with cited research. The Foundry IQ agent doesn't just generate — it *teaches*. Every transformation is a lesson in how colour maps to pitch, how texture maps to timbre, and how the great synesthetes (Scriabin, Kandinsky, Messiaen) understood the bridge between what we see and what we hear.

---

<p align="center">
  Built for the <strong>Microsoft Agents League Hackathon</strong> · Powered by <strong>Azure AI Foundry</strong>
</p>
