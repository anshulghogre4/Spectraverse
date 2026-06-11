---
title: Audacity Spectrogram Viewer
domains: spectrogram
tags: audacity, spectrogram, audio-editor, hanning, linear-frequency, log-frequency
---

# Audacity Spectrogram Viewer

## Overview

Audacity is a free, open-source audio editor that includes a built-in spectrogram view for audio tracks. Its spectrogram display is commonly encountered in educational contexts, tutorials, and user-submitted audio analysis screenshots.

## Default Parameters

- **Sample Rate**: 44100 Hz (CD-quality standard; adapts to file sample rate)
- **Window Function**: Hanning (default); Hamming, Blackman, and rectangular also available
- **Window Size (n_fft)**: 256 to 8192 samples; default is typically 1024 or 2048
- **Hop Length**: Determined by window size and overlap; default overlap is approximately 50%
- **Frequency Range**: 0 Hz to Nyquist (22050 Hz at 44100 sr)
- **Frequency Scale**: Linear by default; logarithmic available in newer versions
- **dB Range**: -80 dB to 0 dB (configurable between 20 dB and 120 dB dynamic range)

## Colormap and Visual Style

- **Default Colormap**: Grayscale (dark = silence, bright = loud)
- **Alternative Colormaps**: "Color" scheme available — maps amplitude to a gradient from black through blue, purple, red, to yellow/white for highest intensities
- **Axis Conventions**: Time on horizontal axis (left to right), frequency on vertical axis (low at bottom, high at top)

## Distinguishing Visual Features

- Spectrograms appear embedded within the track waveform panel, toggled via track dropdown menu
- Narrow vertical resolution compared to dedicated analysis tools
- Color intensity directly maps to amplitude in dB
- Often shows clear harmonic series for tonal audio due to the moderate default FFT size
- Audacity screenshots typically include the gray toolbar and timeline ruler, making them identifiable in uploaded images
