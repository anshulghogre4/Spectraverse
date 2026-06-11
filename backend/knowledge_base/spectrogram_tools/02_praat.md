---
title: Praat Spectrograms
domains: spectrogram
tags: praat, spectrogram, speech-analysis, gaussian-window, narrowband, wideband
---

# Praat Spectrograms

## Overview

Praat is a scientific phonetics and speech analysis tool developed at the University of Amsterdam. It is the dominant tool in linguistics research for acoustic analysis. Praat spectrograms are most commonly encountered in speech and phonetics contexts, showing formant structures of human voice.

## Default Parameters

- **Sample Rate**: Varies by recording; Praat supports any sample rate but speech recordings are typically 16000 Hz, 22050 Hz, or 44100 Hz
- **Window Function**: Gaussian window (distinguishing feature — most other tools default to Hanning)
- **Window Length**: 5 ms (wideband) or 30 ms (narrowband); default view uses wideband for speech
- **Frequency Range**: 0 to 5000 Hz by default (optimized for speech formant visibility)
- **Dynamic Range**: 50 to 70 dB (default is 50 dB in standard view; adjustable in spectrogram settings)
- **Frequency Step**: Adaptive based on window length

## Colormap and Visual Style

- **Default Colormap**: Grayscale — dark background with energy shown as darker regions (inverted from many tools); high energy appears as dark markings on lighter background in print mode
- **Axis Conventions**: Time on horizontal axis, frequency on vertical axis (bottom = 0 Hz, top = 5000 Hz default)

## Distinguishing Visual Features

- Typically displays only the 0-5 kHz range, focusing on speech formants (F1-F4)
- Formant tracks (red dots) are often overlaid on the spectrogram
- Pitch contour (blue line) may also be overlaid
- The Gaussian window produces slightly smoother spectral estimates than Hanning
- Praat screenshots have a distinctive light-gray interface frame with the spectrogram in a white-bordered panel
- Very commonly paired with a TextGrid annotation tier below the spectrogram
