# Sprint 2 Plan — Live Generation: Hear Images, Visualize Sound

**Re-assessed**: 2026-06-03 (7-agent brainstorm grounded in real Sprint 1 codebase)  
**Status**: 📋 PLANNED — ready to build  
**Duration**: 2 weeks  
**Depends on**: Sprint 1 ✅

---

## Sprint Goal

> Close the end-to-end transformation loop in both directions: user uploads an image and
> **hears synthesised audio within 5 seconds**, or uploads audio and **sees an animated
> visual canvas** — replacing all stub placeholders with live pipeline calls.

---

## Chain-of-Thought: Why This Scope

The brainstorm ran 5 specialist agents (UX, backend, frontend/WebAudio, architecture/risk,
product/competition) against the **real Sprint 1 ground truth**:

| Area | Sprint 1 reality |
|---|---|
| `/api/generate/image-to-audio` | Stub — returns hardcoded `"queued"` |
| `/api/generate/audio-to-visual` | Stub — returns hardcoded `"queued"` |
| `DSPSynthesizer.synthesize()` | **BUILT** — produces numpy waveform |
| `ImageToAudioPipeline.generate()` | Imported but **never called** |
| `AudioToVisualPipeline.generate()` | Imported but **never called** |
| WebAudio / Three.js / Spectrogram | **NOT EXISTS** in frontend |
| Redis caching | Connected but **never passed to pipelines** |
| SemanticMapper during generation | Imported but **never instantiated** |

**Scope decision**: Both directions (image→audio AND audio→visual) are in Sprint 2.
The backend wiring for both shares the same fix pattern; presenting a bidirectional system
to competition judges is qualitatively different. Three.js is **deferred to Sprint 3**
(Canvas 2D particle field delivers the visual moment with zero SSR/WebGL risk).
Audio duration is **capped at 15 seconds** server-side (base64 WAV ~1.2MB vs ~2.5MB for 30s).
Redis cache for audio **disabled this sprint** (cache-hit path returns no audio — deferred).

---

## Tasks — Critical Path

```
s2-01 ──► s2-03 ──► s2-05
s2-02 ──► s2-04 ──► s2-05
               ↓
s2-06 ──► s2-07 ──┐
      ──► s2-08 ──┤──► s2-10 ──► s2-11
s2-09 ────────────┘
s2-12 (parallel, any time after s2-01)
s2-13 (parallel, any time after s2-03)
```

---

## Task Breakdown

### Backend

#### s2-01 · Instantiate SemanticMapper + DSPSynthesizer in main.py `[MUST · 0.5d]`
**Why**: `main.py` stores `SemanticMapper` as a class reference and never imports
`DSPSynthesizer`. Both pipeline constructors require actual instances — removing the stubs
without this causes `NameError`/`TypeError` on first request.  
**Done when**: `GET /health` returns `semantic_mapper_available: true` and
`dsp_synthesizer_available: true`. Server starts without import errors.  
**Files**: `backend/app/main.py`

---

#### s2-02 · Add `AudioAnalyzer.analyze_bytes()` wrapper `[MUST · 0.5d]`
**Why**: `AudioToVisualPipeline.generate()` calls `self.analyzer.analyze_bytes(bytes)` but
`AudioAnalyzer` only has `analyze(path: str)`. Guaranteed `AttributeError` on first request.  
**Done when**: `AudioAnalyzer.analyze_bytes(wav_bytes)` returns the same dict shape as
`analyze(path)`, verified by a unit test using an in-memory WAV.  
**Files**: `backend/app/backend_audio_analyzer.py`

---

#### s2-03 · Wire `/api/generate/image-to-audio` to `ImageToAudioPipeline` + WAV encoder `[MUST · 1.5d]`
**Why**: The primary Sprint 2 deliverable. The pipeline is fully implemented but the endpoint
returns a placeholder stub. Also adds `_encode_wav_b64()` (float64 ndarray → base64 WAV via
`scipy.io.wavfile`).  
**Done when**: `POST /api/generate/image-to-audio` with a JPEG returns HTTP 200 with a
non-empty `audio_b64` string whose first 4 decoded bytes are `RIFF`, `sample_rate: 22050`,
`status: "success"`. Response within 5s on warm server.  
**Files**: `backend/app/main.py`  
**⚠️ Risk**: Pass `SEMANTIC_MAPPINGS_PATH` explicitly to `SemanticMapper` (relative path
default breaks in non-root CWD). Pass `use_cache=False` (cache-hit returns no audio).
Wrap in `run_in_executor` to avoid blocking the async event loop (matplotlib takes ~400ms).

---

#### s2-04 · Wire `/api/generate/audio-to-visual` to `AudioToVisualPipeline` `[MUST · 1d]`
**Why**: Pipeline is fully implemented but endpoint returns stub.  
**Done when**: `POST /api/generate/audio-to-visual` with a WAV returns `visual_config.type`,
a non-empty `color_palette`, and `particle_count > 0`.  
**Files**: `backend/app/main.py`  
**Depends on**: s2-01, s2-02

---

#### s2-05 · Integration tests for both generate endpoints `[MUST · 1d]`
**Why**: Sprint 1 required 18 blocker fixes only found in audit. Generate endpoints have
zero test coverage.  
**Done when**: 3 new pytest tests pass: (1) POST 32×32 white JPEG → `audio_b64` starts with
`RIFF`; (2) POST 1-second silent WAV → `visual_config.particles.count > 0`;
(3) POST a text file → HTTP 400.  
**Files**: `backend/tests/test_api.py`  
**Depends on**: s2-03, s2-04

---

#### s2-12 · Warm up VisionAnalyzer at startup `[SHOULD · 0.25d]`
**Why**: `scipy.ndimage` lazy import causes 1–3s cold-start on first real request.  
**Done when**: First request after cold start completes within 3s (down from 5–6s).  
**Files**: `backend/app/main.py`  
**Depends on**: s2-01

---

#### s2-13 · Add `duration` query param (1–15s cap) to image-to-audio endpoint `[SHOULD · 0.25d]`
**Why**: 30s clip = ~2.5MB base64 payload. 15s = ~1.2MB, halves synthesis time. Without this
demo localhost response is visibly slow.  
**Done when**: `?duration=10` returns ~10s audio. No param → defaults to 15s. `?duration=90`
→ HTTP 422.  
**Files**: `backend/app/main.py`  
**Depends on**: s2-03

---

### Frontend

#### s2-06 · Add `generateImageToAudio()` + `generateAudioToVisual()` to `lib/api.ts` `[MUST · 0.5d]`
**Why**: No call path to either generate endpoint exists in the frontend. All downstream
components depend on these typed fetch wrappers.  
**Done when**: TypeScript accepts imports of both functions. `GenerationResult` type includes
`audio_b64`, `sample_rate`, `spectrogram`, `audio_params`, `image_features`.
`VisualGenerationResult` includes `visual_config`, `audio_features`, `visual_params`.
Both throw typed errors on non-2xx responses.  
**Files**: `frontend/lib/api.ts`

---

#### s2-07 · Create `AudioOutputPanel` component `[MUST · 1d]`
**Why**: The generate endpoint returns audio but nothing in the UI plays it.  
**Done when**: Component renders an HTML `<audio controls>` element (data URI from `audio_b64`)
that plays when the user presses play. Spectrogram PNG renders in `<img>`. Semantic caption
reads naturally (e.g. *"Warm bright image → E4 330 Hz pad at 80 BPM with reverb"*). Empty
spectrogram shows a skeleton placeholder. No console errors.  
**Files**: `frontend/components/AudioOutputPanel.tsx` (new)  
**⚠️ Risk**: Use HTML `<audio>` element, NOT `AudioContext.resume()` — browsers block
autoplay without user gesture. Must include `'use client'` directive.  
**Depends on**: s2-06

---

#### s2-08 · Create `VisualOutputPanel` component (Canvas 2D particle field) `[MUST · 1.5d]`
**Why**: `AudioToVisualPipeline` returns `visual_config` but nothing renders it.
Canvas 2D chosen over Three.js to eliminate SSR/WebGL risk in Sprint 2.  
**Done when**: Component renders animated colored particles matching `visual_config` count,
speed, and color palette. Pause/Resume button works. Cleans up `requestAnimationFrame` on
unmount. Particle count capped at 500 (hardware protection).  
**Files**: `frontend/components/VisualOutputPanel.tsx` (new)  
**⚠️ Risk**: Must include `'use client'` directive. Cleanup on unmount is mandatory (memory
leak from orphaned animation loops is the #1 Canvas bug).  
**Depends on**: s2-06

---

#### s2-09 · Create `GenerationProgress` component `[SHOULD · 0.5d]`
**Why**: Generation takes 2–5s. A bare spinner gives no confidence, leading to duplicate
submissions. Named stages demonstrate the AI pipeline is real — a judge-facing proof point.  
**Done when**: While request is in-flight, shows 4 checkable stages: *Analysing file →
Mapping parameters → Synthesising output → Finalising*. Stages advance on time estimate,
stall at 90% until response arrives, disappear on completion.  
**Files**: `frontend/components/GenerationProgress.tsx` (new)

---

#### s2-10 · Extend `UploadZone` with two-step Generate flow `[MUST · 1.5d]`
**Why**: This is the integration task — all new components are built but unreachable without
the Generate button and result routing wired into the existing UploadZone.  
**Done when**: User can (1) upload image → see analysis tiles → click **Generate Audio** →
see GenerationProgress → hear audio from AudioOutputPanel; (2) upload audio → click
**Generate Visual** → see GenerationProgress → see VisualOutputPanel animation; (3) click
Reset to return to upload state with all blob URLs revoked. Mode and style are forwarded to
generate API calls. Feature tile grid collapses into a *Show Details* accordion.  
**Files**: `frontend/components/UploadZone.tsx`  
**Depends on**: s2-06, s2-07, s2-08, s2-09

---

#### s2-11 · Verify Creative Mode styles flow end-to-end `[SHOULD · 0.5d]`
**Why**: 7 style pills exist in the UI but the `style` value was never forwarded to the
generate endpoints. For the competition demo, a judge switching Classic→Horror and hearing
a different result is the key differentiator.  
**Done when**: Horror style on the same image produces measurably lower pitch and higher
reverb than Classic. Electrifying style produces higher particle count and neon palette.
3 styles (Classic, Horror, Electrifying) manually verified. Style badge shown in output panels.  
**Files**: `AudioOutputPanel.tsx`, `VisualOutputPanel.tsx`, `UploadZone.tsx`  
**Depends on**: s2-07, s2-08, s2-10

---

## Critical Risks

| Severity | Risk | Mitigation |
|---|---|---|
| 🔴 CRITICAL | Web Audio autoplay policy — browsers silently block `AudioContext.resume()` without user gesture | Use HTML `<audio controls src="data:...">` — play button IS the user gesture |
| 🔴 HIGH | JSON payload size — 15s WAV = ~1.2MB base64 in JSON; 30s = ~2.5MB (may hit nginx 1MB default) | s2-13 caps at 15s; set `client_max_body_size 10m` in nginx config |
| 🔴 HIGH | `SemanticMapper` relative path default (`'../semantic_mappings.json'`) fails when CWD ≠ repo root | Pass resolved `SEMANTIC_MAPPINGS_PATH` absolute path to constructor in s2-01 |
| 🔴 HIGH | Cache-hit returns no audio — `_set_cache()` explicitly excludes `audio_array`; cache hit → `KeyError` → HTTP 500 | Pass `use_cache=False` to `ImageToAudioPipeline.generate()` in s2-03 |
| 🟡 MEDIUM | `matplotlib.pyplot.savefig()` blocks async event loop for ~400ms per request | Wrap `pipeline.generate()` in `asyncio.run_in_executor(None, ...)` |
| 🟡 MEDIUM | `DSPSynthesizer` instance duplication — pipeline may construct a new instance internally, discarding config | Verify call path in `backend_image_to_audio_pipeline.py` line ~70 |
| 🟡 MEDIUM | Canvas 2D memory leak — old `requestAnimationFrame` loops orphaned on component unmount | `useEffect` cleanup with `cancelAnimationFrame(rafId.current)` |
| 🟡 MEDIUM | `AudioAnalyzer.analyze_bytes()` signature mismatch causes immediate `AttributeError` | Fixed by s2-02 |

---

## Deferred to Sprint 3

- **Three.js / @react-three/fiber 3D renderer** — Canvas 2D satisfies Sprint 2; full
  Three.js scene (IcosahedronGeometry, ShaderMaterial, bloom) needs `next.config.js`
  `transpilePackages` + `dynamic()` SSR bypass
- **Real-time beat-reactive audio-visual sync** — requires `WebAudio AnalyserNode` feeding
  frame-by-frame canvas updates; `AudioContext` lifecycle deferred to Sprint 3
- **Redis caching architecture** — needs Azure Blob Storage for WAV bytes + pre-signed URL
  pattern; safe to skip for Sprint 2 demo
- **Azure Vision API integration** — local Pillow analyzer is sufficient; Azure adds quality
  but requires API key management scope
- **LUFS loudness normalisation** — current peak normalisation is safe for demo; `pyloudnorm`
  is Sprint 3 audio quality enhancement
- **Download / export buttons** — useful but irrelevant to 2-minute live demo
- **Mobile layout** — desktop-first is adequate for projector presentation
- **All 7 style variants verified** — only Classic, Horror, Electrifying manually verified
  in Sprint 2

---

## Success Metrics

1. End-to-end latency: image → playable audio within **5s** on warm server (8s cold)
2. Audio is audibly non-silent, peak amplitude > 0.01, plays without distortion in Chrome + Safari
3. VisualOutputPanel renders ≥100 moving particles with color matching spectral centroid hue
4. Classic vs Horror on the same image: pitch differs by ≥20%
5. pytest passes all tests including 3 new generate endpoint integration tests, zero failures
6. All Sprint 1 endpoints remain functional (no regressions)
7. Full 2-minute demo script can be run **3 consecutive times** without restart or HTTP 500

---

## Effort Summary

| Task | Priority | Effort |
|---|---|---|
| s2-01 SemanticMapper + DSPSynthesizer instantiation | MUST | 0.5d |
| s2-02 AudioAnalyzer.analyze_bytes() | MUST | 0.5d |
| s2-03 Wire image-to-audio generate endpoint | MUST | 1.5d |
| s2-04 Wire audio-to-visual generate endpoint | MUST | 1.0d |
| s2-05 Integration tests | MUST | 1.0d |
| s2-06 API client generate functions | MUST | 0.5d |
| s2-07 AudioOutputPanel | MUST | 1.0d |
| s2-08 VisualOutputPanel (Canvas 2D) | MUST | 1.5d |
| s2-09 GenerationProgress | SHOULD | 0.5d |
| s2-10 UploadZone two-step Generate flow | MUST | 1.5d |
| s2-11 Creative Mode styles end-to-end | SHOULD | 0.5d |
| s2-12 VisionAnalyzer warm-up at startup | SHOULD | 0.25d |
| s2-13 Duration query param (15s cap) | SHOULD | 0.25d |
| **Total** | | **~10.5 days** |

MUST tasks: ~8.5 days. Well within 2-week sprint at 5 days/week.

---

## 2-Minute Demo Script (after Sprint 2)

1. **(0:00–0:15)** Drag a golden-hour landscape photo onto Image-to-Audio. Click **Generate
   Audio**. Four-stage progress appears: Analysing → Mapping → Synthesising → Done.
2. **(0:15–0:35)** AudioOutputPanel slides in. Press play — warm pad tones at ~330 Hz with
   reverb. Point to the spectrogram PNG and the semantic caption:
   *"Brightness 0.73 → E4 330 Hz. Warm colour temperature → pad + cello. 80 BPM."*
3. **(0:35–0:50)** Switch Creative Mode pill to **Horror**. Click Generate Audio again.
   Same image, now low dark ominous tones. Style badge updates. *"Same image, different
   semantic lens — fully explainable."*
4. **(0:50–1:10)** Switch to Audio-to-Visual. Drag a drum-heavy track. Click **Generate
   Visual**. VisualOutputPanel: Canvas 2D particle field, speed tied to BPM, colour to
   spectral centroid.
5. **(1:10–1:25)** Switch to **Electrifying**. Regenerate. Higher particle count, neon
   palette. *"Same audio, different visual interpretation."*
6. **(1:25–1:45)** Open Network tab. Show the single JSON response:
   `audio_b64`, `spectrogram`, `image_features`, `audio_params`, `cache_hit`.
   *"Fully local — no external AI, zero latency surprises, auditable."*
7. **(1:45–2:00)** *"Sprint 3 adds Three.js 3D scenes and beat-reactive animation."*

---

**Built by**: 7-agent brainstorm — UX, Backend, Frontend/WebAudio, Architecture/Risk,
Product/Competition lenses + Ground Truth audit + Synthesis  
**Replaces**: Fake planning-session `SPRINT_2_COMPLETE.md` (2026-05-29, never built)
