# Sprint 3 Plan — Spectrogram Inversion: See a Conversation, Hear It Back

**Re-assessed**: 2026-06-06  
**Status**: 📋 PLANNED — ready to build after Sprint 2 verified  
**Duration**: 2 weeks  
**Depends on**: Sprint 2 ✅

---

## Sprint Goal

> User uploads a **spectrogram image** — a screenshot, export, or photo of any mel/linear/STFT
> spectrogram — and hears the **reconstructed speech or audio** from it with crystal clarity.
> This closes the loop: SpectraVerse can now both *create* spectrograms from audio AND
> *invert* spectrograms back into audio.

---

## The Core Idea — Why This Is Powerful

A spectrogram is not just a visualisation. It is a **lossless (or near-lossless) encoding
of sound** — every frequency, every moment, every harmonic is right there in the image.
A conversation recorded as a spectrogram can be reconstructed back into speech.

**Real-world use cases:**
- Forensic audio — a spectrogram screenshot from a video is all you need
- Accessibility — convert spectrogram diagrams from papers into audible audio
- Music production — reconstruct a melody from a handwritten or photographed score spectrogram
- Competition demo highlight — "upload ANY spectrogram image and hear what it sounds like"

---

## Chain-of-Thought: How Spectrogram Inversion Works

```
Step 1 — Detect
  Is the uploaded image a spectrogram? (frequency axis, time axis, colour gradient)
  vs a regular photo?
  → Classifier: aspect ratio + colour distribution + horizontal banding heuristic

Step 2 — Pre-process
  Crop axes/labels, normalise pixel intensities to dB scale
  Resize to standard time×frequency bins (e.g. 128 mel bins × N time frames)
  Invert colour map (viridis/magma → linear magnitude)

Step 3 — Invert
  Option A (no AI): Griffin-Lim algorithm
    - librosa.griffinlim() estimates missing phase from magnitude
    - 32-64 iterations for good quality
    - Works on any spectrogram, no model needed

  Option B (AI quality): Neural vocoder
    - HiFi-GAN or Vocos pre-trained model
    - Near phone-quality reconstruction for speech
    - Requires ~100MB model download (one-time)

Step 4 — Post-process
  Bandpass filter (remove artefacts outside 50Hz–16kHz)
  Loudness normalise to -14 LUFS
  Return as WAV

Step 5 — Display
  Side-by-side: original spectrogram image + re-generated spectrogram of the output
  "Before" vs "After" shows how faithfully the inversion worked
  Audio player with the reconstructed speech/audio
```

---

## Tasks

### Backend

#### s3-01 · Spectrogram detector — is this image a spectrogram? `[MUST · 1d]`
**Why**: The existing `/api/analyze-image` treats all images as photos. We need to route
spectrogram images to the inversion pipeline, not the vision analyser.  
**Done when**: `POST /api/detect-spectrogram` returns `{"is_spectrogram": true/false, "confidence": 0.0-1.0, "type": "mel|linear|stft|unknown"}`. Correctly identifies a viridis mel-spectrogram as `true` and a sunset photo as `false` in manual testing.  
**How**: Heuristics — aspect ratio > 2:1, dominant colour gradient (not natural colours), horizontal banding pattern detected via row-variance analysis.  
**Files**: `backend/app/backend_spectrogram_detector.py` (new), `backend/app/main.py`

---

#### s3-02 · Spectrogram pre-processor — pixel → magnitude array `[MUST · 1.5d]`
**Why**: Griffin-Lim needs a numpy magnitude array, not a PNG. Raw pixel values encode
colour map (viridis, magma, etc.) not raw dB values — must invert the colour map first.  
**Done when**: `SpectrogramPreprocessor.extract_magnitude(image_bytes)` returns a numpy
`float32` array of shape `(n_mels, n_frames)` with values in range `[0, 1]`. Unit test
confirms round-trip: synthesise audio → generate spectrogram → extract magnitude →
the resulting shape matches the expected mel bins.  
**Handles**: auto-detect colour map (viridis/magma/inferno/plasma), auto-crop axis labels
(detect and remove left/bottom margins), normalise to 0–1.  
**Files**: `backend/app/backend_spectrogram_preprocessor.py` (new)

---

#### s3-03 · Griffin-Lim inversion engine `[MUST · 1d]`
**Why**: The primary reconstruction algorithm. No model download needed — `librosa.griffinlim()`
is already installed.  
**Done when**: `SpectrogramInverter.invert_griffin_lim(magnitude, sr=22050)` returns a
`float32` numpy waveform. For a mel-spectrogram generated from a 440 Hz sine wave, the
reconstructed audio has a dominant frequency within ±50 Hz of 440 Hz (verified via FFT peak).  
**Parameters**: 64 iterations (quality/speed tradeoff), hop_length=512, n_fft=2048.  
**Files**: `backend/app/backend_spectrogram_inverter.py` (new)

---

#### s3-04 · Wire `/api/invert-spectrogram` endpoint `[MUST · 1d]`
**Why**: The endpoint that ties detection → preprocessing → inversion → safety → WAV encoding.  
**Done when**: `POST /api/invert-spectrogram` with a mel-spectrogram PNG returns:
```json
{
  "status": "success",
  "audio_b64": "<base64 WAV>",
  "sample_rate": 22050,
  "duration": 3.2,
  "reconstruction_method": "griffin_lim",
  "confidence": 0.87,
  "spectrogram_type": "mel",
  "comparison_spectrogram": "<base64 PNG of re-synthesised spectrogram>"
}
```
`audio_b64` decodes to a RIFF WAV. If the image is not a spectrogram, returns HTTP 422
with `{"detail": "Image does not appear to be a spectrogram (confidence: 0.23)"}`.  
**Files**: `backend/app/main.py`

---

#### s3-05 · Neural vocoder (HiFi-GAN) — optional high-quality path `[SHOULD · 2d]`
**Why**: Griffin-Lim produces phase artefacts (metallic/echo-y sound). For speech spectrograms,
HiFi-GAN (pre-trained on LJSpeech) produces near-phone-quality reconstruction.  
**Done when**: When `HIFIGAN_AVAILABLE=true` (model downloaded), the endpoint uses HiFi-GAN
by default. Falls back to Griffin-Lim if model absent. Response includes
`"reconstruction_method": "hifigan"`.  
**Model**: `speechbrain/tts-hifigan-ljspeech` (~50MB) via HuggingFace `transformers`.  
**New dep**: `transformers>=4.35.0`, `torch>=2.0.0` (already in `requirements-extras.txt`).  
**Files**: `backend/app/backend_spectrogram_inverter.py`, `backend/requirements-extras.txt`

---

#### s3-06 · Integration tests for inversion endpoint `[MUST · 0.5d]`
**Done when**: 3 tests pass — (1) POST a mel-spectrogram PNG generated by the backend itself
→ `audio_b64` starts with RIFF; (2) POST a sunset photo → HTTP 422; (3) POST a corrupt PNG →
HTTP 400.  
**Files**: `backend/tests/test_api.py`

---

### Frontend

#### s3-07 · `SpectrogramUploadZone` component — detect & route `[MUST · 1d]`
**Why**: The existing UploadZone treats all images as photos. The spectrogram path needs a
distinct UI: show the original spectrogram image, call `/api/invert-spectrogram`, display
side-by-side comparison.  
**Done when**: A third upload zone labelled "Spectrogram → Audio" appears on the page.
After upload, calls `/api/detect-spectrogram` and shows a confidence badge. If confirmed,
shows a "Reconstruct Audio" button. After generation, shows a two-column view:
original spectrogram image on the left, re-synthesised spectrogram on the right, with
the audio player between them.  
**Files**: `frontend/components/SpectrogramUploadZone.tsx` (new)

---

#### s3-08 · `InversionOutputPanel` — before/after comparison `[MUST · 1d]`
**Why**: The "wow moment" for this feature is seeing the original spectrogram and the
reconstructed one side by side, proving the algorithm faithfully recovered the audio.  
**Done when**: Component renders: (1) "Original" spectrogram image at full width; (2) audio
player with reconstructed audio; (3) "Re-synthesised" spectrogram from the backend response;
(4) a `confidence` badge (green ≥ 0.8, yellow ≥ 0.5, red < 0.5); (5) reconstruction method
badge (Griffin-Lim / HiFi-GAN).  
**Files**: `frontend/components/InversionOutputPanel.tsx` (new)

---

#### s3-09 · Add inversion API functions to `lib/api.ts` `[MUST · 0.5d]`
**Done when**: `detectSpectrogram(file)` and `invertSpectrogram(file)` exported from `lib/api.ts`
with full TypeScript types. `InversionResult` type includes `audio_b64`, `confidence`,
`spectrogram_type`, `comparison_spectrogram`, `reconstruction_method`.  
**Files**: `frontend/lib/api.ts`

---

#### s3-10 · Add "Spectrogram → Audio" section to `page.tsx` `[MUST · 0.5d]`
**Done when**: Page has three sections: Image→Audio | Audio→Visual | Spectrogram→Audio.
The third section has a distinct teal/cyan colour theme to visually separate it.  
**Files**: `frontend/app/page.tsx`

---

## Technical Deep Dive: Griffin-Lim for Speech

```
Conversation spectrogram (image)
         │
         ▼ SpectrogramPreprocessor
  Crop axis labels (margin detection)
  Detect colour map (viridis/magma/hot)
  Invert colour map → linear magnitude [0, 1]
  Convert to dB scale → S_db
  Convert to power → S_power = librosa.db_to_power(S_db)
  Convert to mel magnitude → S_mel (shape: 128 × T)
         │
         ▼ SpectrogramInverter.invert_griffin_lim()
  librosa.feature.inverse.mel_to_audio(
      S_mel,
      sr=22050,
      n_fft=2048,
      hop_length=512,
      n_iter=64        ← more iterations = better phase estimation
  )
  # This internally runs Griffin-Lim on the mel-inverted STFT
         │
         ▼ Post-processing
  scipy.signal.butter bandpass (80Hz–16kHz)
  pyloudnorm LUFS normalisation to -14 LUFS
  scipy.io.wavfile.write → float32 WAV
         │
         ▼ Response
  base64 WAV + re-synthesised spectrogram PNG
```

**Expected quality on speech:**
- Clear enough to understand words at normal speaking pace
- Some metallic/phase artefacts (Griffin-Lim limitation)
- HiFi-GAN upgrade removes these entirely for speech

---

## What Makes This Demo-Ready

For the competition a judge can:
1. Screenshot a spectrogram from **any YouTube video** using browser DevTools (Spectral Analyzer)
2. Upload that screenshot to SpectraVerse
3. Hear the audio reconstructed from it

Or more dramatically:
1. Take a photo of a **printed spectrogram** (from a paper or textbook)
2. Upload the photo
3. Hear the audio it encodes

---

## Risks

| Severity | Risk | Mitigation |
|---|---|---|
| 🔴 HIGH | Colour map inversion accuracy — wrong colour map → wrong magnitudes → unrecognisable audio | Auto-detect top-5 colour maps, try each, pick best reconstruction by spectral entropy |
| 🔴 HIGH | Axis label cropping — labels included in magnitude array add noise | Conservative margin crop (remove bottom 8% and left 6% of pixels by default) |
| 🟡 MEDIUM | Griffin-Lim quality on noisy spectrograms (hand-drawn, photographed) | Increase iterations to 128 for photographed inputs; add denoising pre-pass |
| 🟡 MEDIUM | HiFi-GAN model download (~50MB) may be slow on first use | Cache to `~/.cache/spectraverse/` after first download; fallback to Griffin-Lim if absent |
| 🟡 MEDIUM | Non-mel spectrograms (linear, STFT, CQT) need different inversion paths | Detect type via aspect ratio + frequency scale; implement linear path as Sprint 3B if needed |

---

## Success Metrics

1. Griffin-Lim reconstructs a 440 Hz sine tone with dominant FFT peak within ±50 Hz
2. Speech spectrogram (any English TTS output) reconstructs with >70% word intelligibility (manual listening test)
3. Sunset photo correctly classified as non-spectrogram (confidence < 0.4)
4. End-to-end latency (upload → audio) < 8 seconds on warm server
5. Side-by-side spectrogram comparison visually shows structural similarity

---

## Effort Summary

| Task | Priority | Effort |
|---|---|---|
| s3-01 Spectrogram detector | MUST | 1.0d |
| s3-02 Pre-processor (pixel → magnitude) | MUST | 1.5d |
| s3-03 Griffin-Lim inverter | MUST | 1.0d |
| s3-04 `/api/invert-spectrogram` endpoint | MUST | 1.0d |
| s3-05 HiFi-GAN neural vocoder | SHOULD | 2.0d |
| s3-06 Integration tests | MUST | 0.5d |
| s3-07 SpectrogramUploadZone component | MUST | 1.0d |
| s3-08 InversionOutputPanel (before/after) | MUST | 1.0d |
| s3-09 API client functions | MUST | 0.5d |
| s3-10 page.tsx third section | MUST | 0.5d |
| **Total MUST** | | **8.0d** |
| **Total with SHOULD** | | **10.0d** |

Fits comfortably in a 2-week sprint.

---

**Updated**: 2026-06-06  
**Replaces**: Fake planning-session `SPRINT_3_COMPLETE.md` (2026-05-29, never built)
