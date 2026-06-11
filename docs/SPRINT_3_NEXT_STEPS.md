# Sprint 3 — What's Left to Ship

## Where we are now (done)

- **S3-01 STYLE_MAP shortcircuit removed** — the keyword fast-path that bypassed Foundry IQ for words like "happy" or "dark" is gone. The agent now reasons over every prompt against the indexed KB, so the cited reasoning panel reflects what actually drove the audio. Demo impact: the "why this sound" story is honest end-to-end.
- **S3-02 Citations show clean titles + clickable source links** — no more `blob://` noise or raw chunk ids in the FoundryReasoningPanel. Each citation renders as a real title with an outbound link. Demo impact: judges can click through and verify provenance live.
- **S3-03 Foundry IQ default-on for image to audio** — the AI assist toggle now defaults to true on the image upload path. Demo impact: first-run users see the cited reasoning flow without hunting for a switch.
- **S3-06 Real chord progression from the LLM's chosen key** — replaced the static C-major loop with a key-aware progression generated from the agent's extracted key/mode. Demo impact: minor-key prompts actually sound minor.
- **S3-07 Real kick + hi-hat at chosen BPM** — the rhythm bus now uses synthesized kick and hi-hat samples scheduled at the agent's BPM, not a click track. Demo impact: clips feel like music, not metronome.
- **S3-22 Real instrument timbres for 9 instruments** — pad, lead, bass, pluck, bell, organ, brass, choir, fm-keys all have distinct synth voices instead of one shared sine. Demo impact: vibe shifts are audible across prompts in the same sitting.
- **S3-04 Audio to Visual renderer driven by audio features** — the visual canvas now reads vibe/genre/key/BPM from the audio analysis pipeline and maps them to render mode, palette, and motion. Demo impact: closes the loop — image to audio to visual all share one feature vocabulary.
- **S3-09 Foundry IQ for audio to visual** — `/api/generate/audio-to-visual-foundry` endpoint live with cited reasoning. LLM picks render_mode + palette from KB retrieval. FoundryReasoningPanel renders below the visual canvas. Demo impact: completes the "trifecta of cited modalities."
- **S3-05 Auto-bind preset to detector.type** — `_auto_select_preset()` maps detected type (mel/linear/log_linear) to correct inversion preset when confidence > 55%. Response includes `preset_auto_selected` flag. Demo impact: users don't pick wrong presets.
- **S3-08 GPT-4o vision pass on spectrogram** — `describe_spectrogram()` on FoundryAgent + `ai_mode` param wired into `/api/invert-spectrogram`. Vision LLM infers colormap, scale, dB range from the image. Demo impact: second cited modality for spectrogram flow.
- **S3-16 Strip colour-bar columns before entropy crop** — Spearman correlation detects monotonic-gradient columns on the right edge and strips them before cropping. Demo impact: cleaner inversions from Audacity/Sonic Visualiser screenshots.
- **S3-11 Live WebAudio FFT reactivity** — `useAudioAnalyser` hook streams bass/mid/treble/onset from `<audio>` element via Web Audio API. ALL 8 renderers (orbits, flow_field, lightning, horror, aurora, bass_pulse, mandala, glitch) now respond to live audio — not just BPM timers. Demo impact: visuals genuinely listen to the music.
- **S3-26 Audio features as headline chips** — Vibe (color-coded), Genre, Key, BPM shown as primary chips on VisualOutputPanel. Vibe has per-mood color styling (dark_heavy→indigo, bright_energetic→amber, etc.). Demo impact: agent's decisions visible at a glance.
- **S3-13 Narration slot in FoundryReasoningPanel** — optional `narration` prop renders the agent's cited summary between reasoning steps and citations. Demo impact: the "why" is human-readable, not just raw steps.
- **S3-28 Foundry render_mode respected by frontend** — `pickMode()` now checks `visual_config.render_mode` first (Foundry's AI choice), then style, then audio features. Mode source badge shows origin ("AI: mandala" / "style: horror" / "auto from audio"). Demo impact: Foundry's decisions actually render.
- **S3-29 Audio → Spectrogram endpoint + UI** — `POST /api/audio-to-spectrogram` generates mel spectrogram PNG from audio. SpectrogramUploadZone has two tabs: "Spectrogram → Audio" (inversion) and "Audio → Spectrogram" (generation). Demo impact: completes the bidirectional spectrogram story.
- **S3-20 Honest UI labelling for wikipedia_speech preset** — renamed to "Speech / narrow-band (demo)" with hint: "Griffin-Lim recovers timbre, not words." Demo impact: prevents "why doesn't it say words" questions.

## Bug fixes (this session)

- **Spectrogram OOM on non-spectrogram images** — raised confidence gate from 0.3 → 0.55, added `MAX_PIXELS = 1024×512` cap in preprocessor `_load()`, added `MemoryError` catch in endpoint. Comic images now get a clean rejection instead of 8 GiB crash.
- **Audio-to-Visual "analyst_failed"** — endpoint was passing raw bytes to `_audio_analyzer.analyze(path)`. Fixed to write temp file first (matching `analyze-audio` endpoint pattern).
- **Missing response fields in audio-to-visual-foundry** — added `visual_params`, `safety_flags`, `cache_hit` to match frontend `VisualGenerationResult` type.

## What's left (remaining items)

### S3-17 Index per-tool spectrogram convention KB — M effort, high demo impact
**Why now:** S3-08 needs grounded tool conventions to cite. Indexing them once unlocks both vision-pass accuracy and the cited reasoning panel on the spectrogram side.

**Files involved:**
- `backend/knowledge_base/spectrogram_tools/` — 7 new markdown docs (Audacity, Praat, librosa, Sonic Visualiser, Chrome Music Lab, Adobe Audition, Wikipedia)
- Azure Search indexer config

**Concrete steps:**
1. Author each doc with default sample rate, n_fft, hop length, colormap, dB range, axis conventions
2. Tag every chunk with `domains=['spectrogram']`
3. Re-run the indexer and verify retrieval against a hand-built test set

### S3-19 Unified KB with domains tags + cross-modal canon — M effort, high demo impact
Index Wallace 2014, Scriabin's clavier à lumières, and Kandinsky's color theory writings once, tag chunks with both `image_to_audio` and `audio_to_visual` so the same canon grounds both directions and citations stop drifting.

**Files involved:** `backend/knowledge_base/cross_modal/`, indexer config

### S3-12 Unified live / heuristic / mock pill — S effort, medium demo impact
Replicate the FoundryReasoningPanel status pill on the audio panel and spectrogram panel so all three modalities show their mode badge identically.

**Files involved:** `frontend/components/StatusPill.tsx`, `VisualOutputPanel.tsx`, `SpectrogramUploadZone.tsx`

### S3-30 AI assist toggle on spectrogram inversion tab — S effort, medium demo impact
Add the AI assist toggle (mirrors image flow) to SpectrogramUploadZone InvertTab, wiring `ai_mode=true` to the existing backend endpoint parameter.

### S3-31 LiveSpectrogramStrip below visual canvas — S effort, medium demo impact
Render a 64×40 pixel mini spectrogram strip from the same `useAudioAnalyser` hook to visually prove the visual is listening to the audio.

## Recommended order for next session

1. **S3-17 (per-tool KB)** — feeds S3-08 with cited tool conventions and unlocks cited reasoning panel for spectrogram inversion.
2. **S3-19 (cross-modal KB)** — unified canon for both directions; stronger citations across all flows.
3. **S3-30 (AI assist toggle on spectrogram)** — quick wire-up for the frontend toggle, backend already supports it.
4. **S3-12 (unified status pill)** — small visual consistency win across all panels.
5. **S3-31 (live spectrogram strip)** — cherry on top, proves the audio-visual link is real-time.

## What we are NOT doing (and why)

- **S3-25 Vocos neural vocoder** — pulls in a torch dependency that bloats the deploy and pushes us off the current Python runtime budget. Defer post-hackathon.
- **S3-15 UploadZone shell refactor** — cosmetic consolidation; the current duplication is annoying but not visible to judges. Defer.
- **S3-21 Type drift cleanup** — surfaced only in devtools, no runtime impact, no demo signal. Defer.
- **Genre fine-tuning** — DEFERRED per user request. Horror/violin timbre quality to be improved post-sprint.
