---
title: Sonic Visualiser Spectrograms
domains: spectrogram
tags: sonic-visualiser, spectrogram, music-analysis, log-frequency, vamp-plugins
---

# Sonic Visualiser Spectrograms

## Overview

Sonic Visualiser is an open-source application developed at Queen Mary University of London for viewing and analysing music audio files. It is widely used in musicology, music information retrieval (MIR) research, and computational music analysis. It supports VAMP plugins for extensible audio feature extraction.

## Default Parameters

- **Sample Rate**: 44100 Hz (adapts to file; designed for music at CD quality)
- **Window Size (n_fft)**: Configurable from 1024 to 4096 samples; default is typically 1024 or 2048
- **Window Function**: Hanning (default); Blackman, Hamming, and others available
- **Hop Length**: Window size / 2 (50% overlap by default)
- **Frequency Scale**: Logarithmic by default (distinguishing feature — better for musical pitch analysis)
- **Frequency Range**: Full range up to Nyquist; zoom adjustable
- **dB Range**: Configurable; typically shows 60-80 dB dynamic range

## Colormap and Visual Style

- **Default Colormap**: Multiple built-in schemes including "Green" (black-to-green gradient), "Sunset" (dark red to yellow), "White on Black", and "Black on White"
- **Notable Colormap**: The "Green" colormap (black background, green intensity) is a signature visual identifier
- **Axis Conventions**: Time on horizontal axis, frequency on vertical axis (log-scaled by default, meaning equal musical intervals have equal visual spacing)

## Distinguishing Visual Features

- Logarithmic frequency axis by default makes octaves equally spaced visually
- Layer-based interface allows overlaying multiple analysis views (spectrogram + pitch + notes)
- Pane system with multiple synchronized time-aligned views
- Often shows instantaneous frequency estimation for cleaner partial tracking
- Green-on-black colormap is highly distinctive and recognizable
- Time ruler at top with beat/bar markers when tempo is detected
- Annotation layers can overlay rectangles, points, and text on the spectrogram
