# Sprint 3 Plan — Foundry IQ + Spectrogram Inversion

**Re-assessed**: 2026-06-06
**Status**: 🚧 IN PROGRESS — backend agent + UI shipped, Azure provisioning pending
**Duration**: 2 weeks
**Depends on**: Sprint 2 ✅

---

## Sprint Goal

> Make SpectraVerse **agentic and explainable**. Image-to-audio generation runs through
> a 3-stage Microsoft Foundry pipeline (GPT-4o vision → Foundry IQ knowledge base →
> GPT-4o-mini parameter mapping) and returns audio **plus citations** showing exactly
> which music-theory sources informed every decision. The user can also reconstruct
> audio from a spectrogram screenshot using research-backed presets.

---

## What's Built So Far

### Backend (`backend/app/`)

| File | Purpose |
|---|---|
| `backend_foundry_agent.py` | 3-stage pipeline: `describe_image` → `query_knowledge` → `extract_params`. Each stage degrades to a deterministic mock when Azure env vars are missing — meaning the app runs end-to-end with zero Azure setup |
| `backend_spectrogram_detector.py` | 5-signal heuristic: banding, colormap match, aspect ratio, saturation, edge direction |
| `backend_spectrogram_preprocessor.py` | Entropy-based axis crop + LUT colormap inversion (viridis/magma/plasma/inferno/hot/jet) |
| `backend_spectrogram_inverter.py` | Griffin-Lim inversion with **3 presets** extracted from real source code: `librosa_mel`, `chrome_music_lab`, `wikipedia_speech` |
| `main.py` | New endpoint `/api/generate/image-to-audio-foundry` returns audio + citations + reasoning chain |

### Frontend (`frontend/`)

| File | Purpose |
|---|---|
| `lib/api.ts` | `generateImageToAudioFoundry()` + `FoundryGenerationResult` / `FoundryCitation` / `FoundryReasoningStep` types |
| `components/FoundryReasoningPanel.tsx` | Renders the 3-stage chain-of-thought with vision description, reasoning steps colour-coded by stage, and footnoted citations |
| `components/UploadZone.tsx` | Foundry IQ on/off toggle (image flow only). Toggle ON → grounds generation in cited music theory. Toggle OFF → uses local heuristics |
| `components/SpectrogramUploadZone.tsx` | Preset picker (librosa_mel / Chrome Music Lab / Speech) + colormap selector + quality slider |
| `components/VisualOutputPanel.tsx` | **8 distinct render modes** (orbits / flow_field / lightning / horror / aurora / bass_pulse / mandala / glitch) — completely different visuals per creative style |

### Knowledge base (`data/knowledge_base/`)

Four reference documents, ready to index in Foundry IQ:

1. `01_music_theory_keys.md` — major/minor key emotional associations, modal scales, image→key mapping rules
2. `02_music_theory_intervals.md` — consonance/dissonance, style-specific intervals
3. `03_synesthesia_research.md` — Scriabin/Messiaen/Rimsky-Korsakov mappings, cross-modal correspondence research
4. `04_film_score_techniques.md` — practical sound design for all 7 creative styles

---

## How the Foundry Pipeline Works

```
User uploads image + clicks "Generate with Foundry IQ" toggle
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  Stage 1 — VISION                                      │
│  GPT-4o sees the image                                 │
│  Returns: "A stormy sea at twilight, dark blues and    │
│            violets, conveying turbulence and isolation"│
└────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  Stage 2 — RETRIEVAL (Foundry IQ)                      │
│  Knowledge base agentic retrieval                      │
│  Decomposes query into sub-queries:                    │
│   - "musical key for turbulent isolation?"             │
│   - "stormy emotional film scoring?"                   │
│   - "blue-violet colour synesthesia mapping?"          │
│  Returns 3 citations from indexed docs                 │
└────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  Stage 3 — MAPPING                                     │
│  GPT-4o-mini reads description + citations             │
│  Returns JSON: { key: "D minor", bpm: 65,              │
│                  instruments: [cello, organ],          │
│                  reverb: 0.8,                          │
│                  rationale: "Citation [0] indicates    │
│                  D minor for tragic seascapes" }       │
└────────────────────────────────────────────────────────┘
         │
         ▼
DSPSynthesizer.synthesize(params)  →  WAV audio
         │
         ▼
Frontend displays:
  • Audio player
  • Vision quote ("What the AI saw")
  • Chain of thought (3 colour-coded steps)
  • Citations panel with footnotes [0] [1] [2]
```

---

## Graceful Degradation Modes

The app runs end-to-end through 4 levels of Azure setup:

| Level | What's set | What happens |
|---|---|---|
| **Zero Azure** | Nothing | Mock vision description + canned citations + style-map params. UI shows "⚠ mock fallback" badge |
| **AOAI only** | `AZURE_OPENAI_*` | Real GPT-4o vision + GPT-4o-mini mapping, mock citations |
| **Search only** | `AZURE_SEARCH_*` | Mock vision, real Foundry IQ retrieval, heuristic mapping |
| **Full live** | All Azure vars | True end-to-end. UI shows "🔮 Foundry live" badge |

This is intentional — judges can run the demo locally without ever seeing an Azure error, then toggle to live mode for the wow moment.

---

## To Go Live

### 1. Azure provisioning (~15 min, free tier)

1. Sign in to https://ai.azure.com
2. Create a **Foundry resource** (free)
3. Create a **project** within it
4. Deploy two models: `gpt-4o` and `gpt-4o-mini`
5. Create an **Azure AI Search** resource (free tier — 50 MB storage)
6. Connect the search service to your Foundry project

### 2. Index the knowledge base

In Foundry portal → Build → Knowledge tab:
1. Create knowledge base named `spectraverse-music-theory-kb`
2. Add a knowledge source pointing to `data/knowledge_base/`
3. Foundry handles chunking + embedding automatically

### 3. Set env vars

Copy `.env.example` → `backend/.env` and fill in:
```
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_GPT4O_DEPLOYMENT=gpt-4o
AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT=gpt-4o-mini
AZURE_SEARCH_ENDPOINT=https://your-search-svc.search.windows.net
AZURE_SEARCH_API_KEY=...
FOUNDRY_KB_NAME=spectraverse-music-theory-kb
FOUNDRY_KS_NAME=music-theory-ks
```

### 4. Install Azure SDKs

```bash
pip install --pre "azure-search-documents>=11.7.0b2" "azure-identity>=1.17.0" "openai>=1.55.0"
```

### 5. Restart the backend

```bash
uvicorn app.main:app --reload --port 8000
```

`GET /health` will now report `foundry.is_fully_live: true`.

---

## Cost Estimate

| Item | Free tier | Beyond free |
|---|---|---|
| Foundry resource | Free | Free |
| Azure AI Search | 50 MB / 3 indexes | $0 covers our 4-doc KB |
| GPT-4o vision | $200 free credit covers ~30,000 calls | ~$0.001 per image |
| GPT-4o-mini mapping | $200 covers ~150,000 calls | ~$0.0002 per call |
| Foundry IQ retrieval | Free tier covers thousands of queries | Pennies |
| **Total demo** | **$0** | **<$5 for the entire competition season** |

---

## Demo Script (90 seconds)

1. **(0:00–0:10)** Open the app. Upload a stormy ocean photo.
2. **(0:10–0:20)** Toggle **🧠 Foundry IQ · ON**. Click **Generate with Foundry IQ**.
3. **(0:20–0:35)** Three stages animate in:
   - "What the AI saw" quote — GPT-4o description
   - Chain of thought — vision (blue) → retrieval (purple) → mapping (green)
4. **(0:35–0:45)** Citations panel appears. Click [0] — sees "D minor for tragic seascapes" from `01_music_theory_keys.md`. Click [2] — sees Scriabin synesthesia mapping for blue-violet.
5. **(0:45–1:00)** Audio plays — D minor cello + organ + heavy reverb.
6. **(1:00–1:15)** Toggle **OFF**. Regenerate. Same image, but now uses local heuristics — different output, no citations. Side-by-side comparison shows the value.
7. **(1:15–1:30)** Switch to spectrogram inversion section. Pick **Wikipedia spectrogram** preset. Upload the famous "nineteenth century" PNG. Audio plays back — voice-like reconstruction.

---

## What's Deferred to Sprint 4

- **Vocos neural vocoder** — would lift speech intelligibility from ~30% to ~75% on real spectrograms (requires `pip install vocos`, ~17 MB model download)
- **Foundry Agent Service** — turn the 3-stage pipeline into a deployed agent (currently runs in-process)
- **Multi-agent orchestration** — separate vision agent, theory agent, composer agent
- **Knowledge base auto-refresh** — schedule indexer to pick up new docs in `data/knowledge_base/`
- **Caching layer** — Redis cache for repeated images / descriptions

---

**Updated**: 2026-06-06 — Foundry agent integration shipped with mock fallback
**Next**: Provision Azure resources to flip from mock to live
