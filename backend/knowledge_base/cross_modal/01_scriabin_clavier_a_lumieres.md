---
title: "Scriabin's Clavier a Lumieres — Colour-Tone Associations"
domains: image_to_audio, audio_to_visual
tags: scriabin, synesthesia, colour-tone, prometheus, clavier-a-lumieres, key-colour-mapping
---

# Scriabin's Clavier a Lumieres — Colour-Tone Associations

## Historical Background

Alexander Scriabin (1872-1915) was a Russian composer and pianist who developed a systematic mapping between musical keys and colours. While not a true synesthete in the clinical sense, Scriabin created a deliberate aesthetic system linking tonality to the visible spectrum. His most famous application of this system was in "Prometheus: The Poem of Fire" (1910), scored for orchestra, piano, chorus, and the *clavier a lumieres* (keyboard of lights) — a colour organ that projected coloured light into the concert hall synchronized with the music.

## Scriabin's Colour-Tone Mapping

| Musical Key | Colour          |
|-------------|-----------------|
| C           | Red             |
| D           | Yellow          |
| E           | Sky blue (pearly white-blue) |
| F           | Deep green      |
| G           | Orange-pink (rosy) |
| A           | Green           |
| B           | Blue (pearl-blue) |
| F#          | Bright blue / violet |
| Db          | Violet          |
| Ab          | Purple-violet   |
| Eb          | Steel / metallic |
| Bb          | Steel / rose    |

Scriabin's system was rooted in his mystic philosophy — he arranged colours around the circle of fifths, creating a chromatic wheel that paralleled the colour wheel. The "warm" keys (C, G, D) map to warm colours (red, orange, yellow), while "cool" keys (E, B, F#) map to blues and violets.

## Theoretical Basis

Scriabin's mapping follows the circle of fifths rather than the chromatic scale. Moving by fifths (C-G-D-A-E-B-F#) traces a spectral progression from red through orange, yellow, green, to blue and violet. This creates a perceptually smooth transition where harmonically related keys have adjacent colours.

## Application in SpectraVerse

SpectraVerse uses Scriabin's colour-tone associations as a **colour anchor system** in the audio-to-visual pipeline:

1. **Key Detection**: The audio analyzer extracts the detected musical key from the input audio
2. **Colour Anchor Selection**: The detected key is mapped to Scriabin's corresponding colour, which becomes the dominant colour anchor for the visual output
3. **Palette Generation**: The colour anchor seeds a broader palette — harmonically related keys (fourths, fifths) contribute adjacent colours, creating cohesive visual palettes that reflect the harmonic content
4. **Modulation Tracking**: When the audio modulates to a new key, the visual palette shifts correspondingly, maintaining the Scriabin mapping as a structural backbone

This provides a historically grounded, aesthetically coherent system for translating tonal information into colour, giving the visual output a perceptual logic that viewers intuitively recognize even without knowing the underlying theory.
