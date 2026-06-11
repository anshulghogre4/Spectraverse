---
title: Adobe Audition Spectral Frequency Display
domains: spectrogram
tags: adobe-audition, spectrogram, spectral-editing, professional-audio, daw
---

# Adobe Audition Spectral Frequency Display

## Overview

Adobe Audition is a professional digital audio workstation (DAW) that features an advanced spectral frequency display used for both visualization and direct spectral editing. Its spectrogram view is uniquely integrated with editing tools — users can paint, select, and delete frequency content directly on the spectrogram. This makes it a production tool, not just an analysis tool.

## Default Parameters

- **Sample Rate**: 44100 Hz or 48000 Hz (adapts to session/file settings; 48kHz common for video work)
- **Window Function**: Hanning (default); Blackman-Harris available for reduced spectral leakage; Hamming and Gaussian also supported
- **Window Size (n_fft)**: Configurable; default typically 2048 or 4096 for detailed frequency resolution
- **Hop Length**: Adaptive based on zoom level and window size
- **Frequency Scale**: Logarithmic by default (matches musical perception); linear available
- **Frequency Range**: Full range to Nyquist; adjustable via zoom
- **dB Range**: Fully configurable; default shows approximately 80-96 dB dynamic range; user can adjust floor and ceiling

## Colormap and Visual Style

- **Default Colormap**: Custom multi-colour gradient — typically dark blue/black (silence) through purple, red, orange, to yellow/white (loudest)
- **Custom Colormaps**: Users can define custom colour gradients in preferences
- **Axis Conventions**: Time on horizontal axis, frequency on vertical axis (logarithmic default)

## Distinguishing Visual Features

- Spectral editing brush tools leave visible painted regions (rectangular selections, lasso selections)
- Very high resolution rendering with smooth interpolation
- Integrated with waveform view — often shown split-screen (waveform top, spectrogram bottom) or blended
- Dark UI theme with the spectrogram panel having a characteristic dark-blue-to-yellow energy gradient
- Selection tools create highlighted rectangular or freeform regions on the spectrogram
- Frequency and time readouts displayed in the status bar
- Professional polish with anti-aliased rendering and configurable transparency
