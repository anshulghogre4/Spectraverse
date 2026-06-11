---
title: Wikipedia Spectrogram Images
domains: spectrogram
tags: wikipedia, spectrogram, educational, speech, narrow-band, reference-images
---

# Wikipedia Spectrogram Images

## Overview

Wikipedia hosts numerous spectrogram images used as educational illustrations across articles on acoustics, phonetics, signal processing, and music. These images are contributed by various authors and represent a mix of tools and conventions, but several common patterns emerge. They serve as canonical reference examples that many users encounter first when learning about spectrograms.

## Typical Parameters

- **Sample Rate**: Often 16000 Hz (speech-focused) or 22050-44100 Hz (music/general audio)
- **Window Size (n_fft)**: Typically 1024 samples for speech (narrow-band analysis showing harmonics)
- **Window Function**: Varies; Hanning and rectangular common
- **Hop Length**: Not standardized; depends on contributing author's tool
- **Frequency Scale**: Linear FFT (most common in Wikipedia images); occasionally log scale for music
- **Frequency Range**: 0-8000 Hz typical for speech; full range for general audio
- **dB Range**: Varies; typically normalized to show 40-80 dB dynamic range

## Colormap and Visual Style

- **Common Colormaps**: viridis, hot (black-red-yellow-white), jet (rainbow), and grayscale
- **Background**: Varies by contributor; both dark and light backgrounds appear
- **Axis Conventions**: Time on horizontal axis, frequency on vertical axis; axis labels present but styling varies

## Distinguishing Visual Features

- Often depict human speech — vowels, consonants, and sentences with visible formant tracks
- Narrow-band spectrograms showing individual harmonics as horizontal striations are very common
- Typically include clearly labeled axes with units (Hz, seconds, kHz)
- Image resolution varies widely (from low-res legacy uploads to high-quality SVG/PNG)
- May include annotations: arrows, labels pointing to formants, harmonics, or noise regions
- Often have a clean, textbook-style appearance without software interface chrome
- Some images use the "hot" colormap (black-red-yellow-white gradient) which is distinctive
- Commonly show the word "spectrogram" in the figure caption or embedded title
- Educational focus means they prioritize clarity over aesthetic appeal
