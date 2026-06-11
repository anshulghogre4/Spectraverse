---
title: Chrome Music Lab Spectrogram
domains: spectrogram
tags: chrome-music-lab, spectrogram, web-audio, real-time, educational, rainbow, jet-colormap
---

# Chrome Music Lab Spectrogram

## Overview

Chrome Music Lab Spectrogram is a web-based, educational, real-time spectrogram tool created by Google as part of the Chrome Music Lab experiments. It is designed for accessibility and education, allowing users to visualize sound from their microphone or built-in audio sources directly in the browser. It is widely used in classroom settings and introductory acoustics education.

## Default Parameters

- **Sample Rate**: 44100 Hz (Web Audio API default)
- **Frequency Range**: 20 Hz to 20000 Hz (full audible range displayed)
- **Frequency Scale**: Switchable between linear and logarithmic; default presentation emphasizes the full audible spectrum
- **Window Size**: Determined by Web Audio API AnalyserNode; typically 2048 or 4096
- **Real-time Processing**: Continuous scrolling display with no offline/batch mode
- **dB Range**: Automatic gain; not explicitly configurable by the user

## Colormap and Visual Style

- **Default Colormap**: Rainbow/jet-style — maps frequency bands or amplitude to a full spectrum of colours (red, orange, yellow, green, blue, violet)
- **Background**: Black background with vibrant colour fills
- **Axis Conventions**: Time scrolls horizontally (right to left in real-time mode), frequency on vertical axis (low frequencies at bottom, high at top)

## Distinguishing Visual Features

- Bright, saturated rainbow colours on black background — highly distinctive and immediately recognizable
- Real-time scrolling waterfall display
- Simplified interface with no numerical axis labels or dB scale indicators
- Large, full-screen canvas designed for visual impact over scientific precision
- Often captures singing, whistling, or instrument demos in educational contexts
- Smooth, interpolated rendering without sharp pixel boundaries
- No colorbar, no grid lines — purely visual and experiential
- Often screenshot with the Chrome Music Lab UI header visible
