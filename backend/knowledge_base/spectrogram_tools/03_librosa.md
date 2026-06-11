---
title: librosa/matplotlib Spectrograms
domains: spectrogram
tags: librosa, matplotlib, python, mel-spectrogram, viridis, stft, machine-learning
---

# librosa/matplotlib Spectrograms

## Overview

librosa is the dominant Python library for music and audio analysis. Its spectrograms, rendered via matplotlib, are ubiquitous in machine learning papers, Jupyter notebooks, and audio research. They are the most common programmatically-generated spectrograms encountered online.

## Default Parameters

- **Sample Rate**: 22050 Hz (librosa default; auto-resamples on load)
- **n_fft**: 2048 samples (window size for STFT)
- **Hop Length**: 512 samples (giving ~75% overlap at n_fft=2048)
- **Mel Bins**: 128 (for mel spectrograms via `librosa.feature.melspectrogram`)
- **Frequency Scale**: Mel scale (perceptual) for mel spectrograms; linear Hz for STFT
- **Power-to-dB Conversion**: `librosa.power_to_db(S, ref=np.max)` — normalizes to 0 dB at maximum
- **dB Range**: -80 dB to 0 dB (with `vmin=-80, vmax=0` typical in `specshow`)
- **Frequency Range**: 0 to sr/2 (11025 Hz at default sr)

## Colormap and Visual Style

- **Default Colormap**: `viridis` (perceptually uniform — dark purple for low energy, yellow for high energy)
- **Common Alternatives**: `magma`, `inferno`, `plasma` (all perceptually uniform matplotlib colormaps)
- **Axis Conventions**: Time on x-axis (seconds), frequency on y-axis (Hz or mel); uses `librosa.display.specshow` for proper axis formatting

## Distinguishing Visual Features

- Matplotlib figure frame with labeled axes and colorbar on the right side
- Viridis colormap is highly recognizable (purple-to-yellow gradient)
- Y-axis often shows mel-scale with non-linear spacing (compressed high frequencies)
- Clean, anti-aliased rendering without interface chrome
- Often appears in grid layouts (subplots) comparing multiple representations
- Colorbar labeled "dB" is a strong identifier
- Resolution determined by n_fft and hop_length parameters, producing characteristic time-frequency trade-off
