"""
DSP Audio Synthesis Service
Generates audio from semantic parameters using torchaudio & librosa.
Process:
1. Generate base waveform (sine wave with pitch)
2. Add harmonics (brightness)
3. Add percussion (sharpness)
4. Add ambience/reverb (texture)
5. Normalize & limit (safety)
"""

import numpy as np
from typing import Dict, Any, List
import json
from scipy.signal import iirpeak, lfilter

# Vibrato rates per instrument (Hz)
VIBRATO_RATES = {
    'violin': 5.5,
    'cello':  4.0,
    'flute':  4.5,
}
# Formant peak frequencies per instrument (Hz) — biquad bandpass centres
FORMANT_FREQS = {
    'violin':  [1000, 2200, 3500],
    'cello':   [400,   800, 1600],
    'electric_guitar': [400, 1700, 3000],
}

# Pitch class → MIDI note number (octave 4 reference)
KEY_TO_HZ = {
    "C": 261.63, "C#": 277.18, "Db": 277.18,
    "D": 293.66, "D#": 311.13, "Eb": 311.13,
    "E": 329.63,
    "F": 349.23, "F#": 369.99, "Gb": 369.99,
    "G": 392.00, "G#": 415.30, "Ab": 415.30,
    "A": 440.00, "A#": 466.16, "Bb": 466.16,
    "B": 493.88,
}

# Semitone offsets for scale degrees in major vs minor
MAJOR_SCALE_SEMITONES = [0, 2, 4, 5, 7, 9, 11]   # I ii iii IV V vi vii
MINOR_SCALE_SEMITONES = [0, 2, 3, 5, 7, 8, 10]   # i ii III iv v VI VII

# Chord progressions: pools of 4-chord patterns as scale-degree indices (0-based)
PROG_MAJOR_POOL = [
    [0, 4, 5, 3],   # I-V-vi-IV   (pop)
    [0, 5, 3, 4],   # I-vi-IV-V   (doo-wop)
    [0, 3, 5, 4],   # I-IV-vi-V
    [0, 2, 3, 4],   # I-iii-IV-V
    [5, 3, 0, 4],   # vi-IV-I-V   (Axis)
    [0, 3, 4, 3],   # I-IV-V-IV   (rock)
    [1, 4, 0, 5],   # ii-V-I-vi   (jazz)
    [0, 6, 3, 0],   # I-bVII-IV-I (rock modal)
    [0, 4, 2, 3],   # I-V-iii-IV
    [3, 0, 4, 5],   # IV-I-V-vi
]
PROG_MINOR_POOL = [
    [0, 5, 2, 6],   # i-VI-III-VII (cinematic)
    [0, 3, 6, 2],   # i-iv-VII-III
    [0, 6, 5, 6],   # i-VII-VI-VII
    [0, 3, 4, 0],   # i-iv-v-i     (classical)
    [0, 5, 3, 4],   # i-VI-iv-V    (flamenco)
    [0, 2, 6, 5],   # i-III-VII-VI
    [0, 4, 5, 3],   # i-v-VI-IV
    [0, 3, 5, 4],   # i-iv-VI-V
    [5, 0, 6, 3],   # VI-i-VII-iv
    [0, 6, 4, 5],   # i-VII-v-VI
]

# Rhythm patterns: (beat_in_bar, instrument) for various feels
RHYTHM_PATTERNS = [
    # 0: Standard 4/4
    {0: 'kick', 1: 'hat', 2: 'kick', 3: 'hat'},
    # 1: Syncopated
    {0: 'kick', 1: 'hat', 2.5: 'kick', 3: 'hat'},
    # 2: Half-time
    {0: 'kick', 2: 'hat'},
    # 3: Double-time
    {0: 'kick', 0.5: 'hat', 1: 'kick', 1.5: 'hat', 2: 'kick', 2.5: 'hat', 3: 'kick', 3.5: 'hat'},
    # 4: Sparse ambient
    {0: 'kick', 3: 'hat'},
    # 5: Shuffle
    {0: 'kick', 0.67: 'hat', 2: 'kick', 2.67: 'hat'},
    # 6: Breakbeat
    {0: 'kick', 1.5: 'kick', 2: 'hat', 3: 'kick', 3.5: 'hat'},
    # 7: Waltz feel (3/4)
    {0: 'kick', 1: 'hat', 2: 'hat'},
]

# Map "intervals" hints from STYLE_MAP to semitone offsets (for dyad/triad voicings)
INTERVAL_SEMITONES = {
    "unison": 0, "minor_2nd": 1, "major_2nd": 2,
    "minor_3rd": 3, "major_3rd": 4,
    "perfect_4th": 5, "tritone": 6, "perfect_5th": 7,
    "minor_6th": 8, "major_6th": 9,
    "minor_7th": 10, "major_7th": 11, "octave": 12,
}


def _parse_key(key_name: str):
    '''Parse "D minor", "F# major", "C Lydian" → (root_hz, is_minor).'''
    if not key_name:
        return (KEY_TO_HZ["C"], False)
    parts = key_name.strip().split()
    root = parts[0] if parts else "C"
    root = root[0].upper() + (root[1:] if len(root) > 1 else "")
    root_hz = KEY_TO_HZ.get(root, KEY_TO_HZ["C"])
    mode = (parts[1].lower() if len(parts) > 1 else "major")
    is_minor = "minor" in mode or "phrygian" in mode or "dorian" in mode or "aeolian" in mode
    return (root_hz, is_minor)


def _degree_to_hz(root_hz: float, semitones: int) -> float:
    '''Move a frequency by N semitones.'''
    return root_hz * (2.0 ** (semitones / 12.0))


def _envelope(num_samples: int, attack_frac: float = 0.02,
              decay_frac: float = 0.20, sustain: float = 0.7,
              release_frac: float = 0.15) -> np.ndarray:
    """ADSR envelope normalized [0,1] across num_samples."""
    n = num_samples
    a = max(2, int(n * attack_frac))
    d = max(2, int(n * decay_frac))
    r = max(2, int(n * release_frac))
    s = max(0, n - a - d - r)
    env = np.concatenate([
        np.linspace(0, 1, a, dtype=np.float32),
        np.linspace(1, sustain, d, dtype=np.float32),
        np.full(s, sustain, dtype=np.float32),
        np.linspace(sustain, 0, r, dtype=np.float32),
    ])
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)))
    return env[:n].astype(np.float32)


def _bandpass_iir(x: np.ndarray, sr: int, f0: float, q: float = 4.0) -> np.ndarray:
    """Simple biquad bandpass (RBJ cookbook) — adds formant resonance."""
    w0 = max(0.001, min(0.999, f0 / (sr / 2)))
    b, a = iirpeak(w0, q)
    return lfilter(b, a, x).astype(np.float32)


def _saw(t: np.ndarray, hz: float) -> np.ndarray:
    """Anti-aliased sawtooth-ish using band-limited approximation."""
    # Sum of harmonics up to Nyquist/2
    return ((2.0 / np.pi) * np.arctan(np.tan(np.pi * hz * t))).astype(np.float32)


def _square(t: np.ndarray, hz: float) -> np.ndarray:
    return np.sign(np.sin(2 * np.pi * hz * t)).astype(np.float32)


class DSPSynthesizer:
    """Synthesize audio using DSP techniques."""
    
    def __init__(self, sr: int = 22050, duration: float = 30.0):
        self.sr = sr
        self.duration = min(duration, 60.0)  # Max 60 seconds
        self.num_samples = int(sr * self.duration)
    
    def synthesize(self, params: Dict[str, Any]) -> np.ndarray:
        """
        Synthesize audio from parameters.
        """
        waveform = np.zeros(self.num_samples)

        pitch        = float(params.get("pitch", 220))
        bpm          = float(params.get("bpm", 90))
        instruments  = params.get("instruments", ["pad"])
        reverb_amount= float(params.get("reverb", 0.3))
        intensity    = float(params.get("intensity", 0.5))
        complexity   = float(params.get("complexity", 0.5))
        effects      = params.get("effects", []) or []
        intervals    = params.get("intervals", []) or []
        key_name     = params.get("key_name") or params.get("key") or ""

        # Parse key + pick progression from pool (deterministic per-param-set)
        root_hz, is_minor = _parse_key(key_name)
        scale = MINOR_SCALE_SEMITONES if is_minor else MAJOR_SCALE_SEMITONES
        pool = PROG_MINOR_POOL if is_minor else PROG_MAJOR_POOL
        prog_seed = hash(f"{key_name}:{bpm}:{','.join(instruments)}") % len(pool)
        prog = pool[prog_seed]

        # Pick rhythm pattern from pool
        rhythm_seed = hash(f"{bpm}:{intensity}:{','.join(instruments)}") % len(RHYTHM_PATTERNS)
        rhythm = RHYTHM_PATTERNS[rhythm_seed]

        # Bar / chord timing — 4 chords across the clip
        beats_per_bar = 4
        seconds_per_beat = 60.0 / max(40.0, min(240.0, bpm))
        bar_seconds = seconds_per_beat * beats_per_bar
        chord_duration = max(0.5, self.duration / len(prog))
        chord_samples = int(self.sr * chord_duration)

        # For each chord in the progression: lay down a triad with envelope
        t_chord = np.linspace(0, chord_duration, chord_samples, endpoint=False)
        for chord_idx, degree in enumerate(prog):
            start = chord_idx * chord_samples
            end = min(start + chord_samples, self.num_samples)
            length = end - start
            if length <= 0:
                continue

            chord_root_hz = _degree_to_hz(root_hz, scale[degree % len(scale)])

            third_semi = 3 if is_minor else 4
            fifth_semi = 7
            chord_freqs = [
                chord_root_hz,
                _degree_to_hz(chord_root_hz, third_semi),
                _degree_to_hz(chord_root_hz, fifth_semi),
            ]

            for iv_name in intervals[:3]:
                semi = INTERVAL_SEMITONES.get(iv_name)
                if semi is not None and semi not in (0, 7):
                    chord_freqs.append(_degree_to_hz(chord_root_hz, semi))

            chord_t = t_chord[:length]
            per_inst_amp = 0.5 / max(1, len(instruments) ** 0.5)
            # Vary attack/release slightly per chord for natural feel
            atk_var = 0.03 + np.random.uniform(-0.01, 0.02)
            rel_var = 0.18 + np.random.uniform(-0.03, 0.05)
            chord_env = _envelope(length, attack_frac=atk_var, sustain=0.8, release_frac=rel_var)
            for instrument in instruments[:3]:
                inst_voice = np.zeros(length, dtype=np.float32)
                for f in chord_freqs:
                    # Micro-detuning: ±5 cents for natural ensemble feel
                    detune_cents = np.random.uniform(-5, 5)
                    f_detuned = f * (2.0 ** (detune_cents / 1200.0))
                    # Velocity variation: ±15%
                    velocity = 1.0 + np.random.uniform(-0.15, 0.15)
                    inst_voice += self._render_instrument(
                        instrument, chord_t, f_detuned, chord_env
                    ) * velocity
                waveform[start:end] += inst_voice * per_inst_amp * intensity

        # Drums — rhythm pattern driven, only when intensity warrants
        if intensity > 0.3:
            drum_bus = np.zeros(self.num_samples)
            bars_total = int(self.duration / bar_seconds) + 1
            beats_per = 4 if rhythm_seed != 7 else 3  # waltz = 3 beats
            for bar in range(bars_total):
                bar_start_sec = bar * bar_seconds
                for beat_offset, drum_type in rhythm.items():
                    t_start = bar_start_sec + float(beat_offset) * seconds_per_beat
                    s_start = int(t_start * self.sr)
                    if s_start >= self.num_samples:
                        continue
                    # Slight timing humanisation: ±5ms
                    s_start = max(0, s_start + int(np.random.uniform(-0.005, 0.005) * self.sr))
                    vel = intensity * (1.0 + np.random.uniform(-0.1, 0.1))
                    if drum_type == 'kick':
                        k = self._kick(seconds_per_beat * 0.4)
                        end = min(s_start + len(k), self.num_samples)
                        drum_bus[s_start:end] += k[:end - s_start] * 0.35 * vel
                    elif drum_type == 'hat':
                        h = self._hat(seconds_per_beat * 0.15)
                        end = min(s_start + len(h), self.num_samples)
                        drum_bus[s_start:end] += h[:end - s_start] * 0.20 * vel
            waveform += drum_bus

        # ── Effects ───────────────────────────────────────────────────────
        if "distortion" in effects:
            waveform = np.tanh(waveform * 3.0) * 0.7

        if "delay" in effects:
            delay_samples = int(0.3 * self.sr)
            if delay_samples < self.num_samples:
                delayed = np.zeros_like(waveform)
                delayed[delay_samples:] = waveform[:-delay_samples] * 0.45
                waveform = waveform + delayed

        if "compression" in effects:
            threshold = 0.4
            above = np.abs(waveform) > threshold
            waveform[above] = np.sign(waveform[above]) * (
                threshold + (np.abs(waveform[above]) - threshold) * 0.4
            )

        # ── Reverb (echo) ─────────────────────────────────────────────────
        if reverb_amount > 0:
            delay_samp = int(0.45 * self.sr)
            if delay_samp < self.num_samples:
                delayed = np.zeros_like(waveform)
                delayed[delay_samp:] = waveform[:-delay_samp]
                waveform = waveform + reverb_amount * delayed

        # ── Normalise + soft-limit ────────────────────────────────────────
        waveform = self._normalize(waveform)
        waveform = self._soft_limit(waveform)

        return waveform

    # ── Instrument synth methods ─────────────────────────────────────────
    def _synth_violin(self, t_arr, hz, env):
        # Saw with 5.5Hz vibrato (~0.15% pitch modulation), bandpass formants
        vib = 1.0 + 0.0015 * np.sin(2 * np.pi * 5.5 * t_arr)
        wave = _saw(t_arr * vib, hz)
        # Bright formants
        wave = _bandpass_iir(wave, self.sr, 1000, q=3.0) * 0.6 \
             + _bandpass_iir(wave, self.sr, 2200, q=2.5) * 0.4
        return (wave * env).astype(np.float32)

    def _synth_electric_guitar(self, t_arr, hz, env):
        # Power chord: root + 5th, square wave, tanh overdrive
        root = _square(t_arr, hz) * 0.5
        fifth = _square(t_arr, hz * (2 ** (7 / 12))) * 0.35
        mix = root + fifth
        # Overdrive
        driven = np.tanh(mix * 4.0) * 0.7
        # Mid-frequency body
        driven = _bandpass_iir(driven, self.sr, 1700, q=1.5)
        return (driven * env).astype(np.float32)

    def _synth_guitar(self, t_arr, hz, env):
        # Plucked saw with exponential decay
        wave = _saw(t_arr, hz)
        # Body resonance ~250Hz
        body = _bandpass_iir(wave, self.sr, 250, q=2.0) * 0.3
        # Pluck envelope = quick attack, exponential decay
        n = len(t_arr)
        pluck = np.exp(-np.linspace(0, 5, n)).astype(np.float32)
        return ((wave + body) * pluck * env * 0.4).astype(np.float32)

    def _synth_organ(self, t_arr, hz, env):
        # Hammond-like additive synthesis
        partials = [(1.0, 1.0), (2.0, 0.6), (3.0, 0.4), (4.0, 0.3), (5.0, 0.2)]
        wave = sum(amp * np.sin(2 * np.pi * hz * mult * t_arr)
                   for mult, amp in partials)
        return (wave * 0.25 * env).astype(np.float32)

    def _synth_cello(self, t_arr, hz, env):
        vib = 1.0 + 0.001 * np.sin(2 * np.pi * 4.0 * t_arr)
        wave = _saw(t_arr * vib, hz)
        # Lower formants than violin
        wave = _bandpass_iir(wave, self.sr, 400,  q=3.5) * 0.55 \
             + _bandpass_iir(wave, self.sr, 1100, q=2.8) * 0.35
        # Cello has slower attack
        slow_env = env.copy()
        attack = max(2, int(len(env) * 0.08))
        slow_env[:attack] *= np.linspace(0, 1, attack) ** 2
        return (wave * slow_env * 0.6).astype(np.float32)

    def _synth_piano(self, t_arr, hz, env):
        # Hammered: short noise burst + sine + slight detune at 1.005x for chorus
        n = len(t_arr)
        wave = (np.sin(2 * np.pi * hz * t_arr)
              + 0.4 * np.sin(2 * np.pi * hz * 1.005 * t_arr)
              + 0.2 * np.sin(2 * np.pi * hz * 2 * t_arr))
        # Strike noise: brief white noise on attack
        attack = min(n, int(self.sr * 0.005))
        if attack > 0:
            noise = np.random.uniform(-0.3, 0.3, attack).astype(np.float32)
            wave[:attack] += noise
        # Piano-shape envelope: very fast attack, exponential decay
        decay = np.exp(-np.linspace(0, 3, n)).astype(np.float32)
        return (wave * decay * env * 0.4).astype(np.float32)

    def _synth_pad(self, t_arr, hz, env):
        # Three detuned sines for chorus + slow attack
        wave = (np.sin(2 * np.pi * hz * t_arr)
              + np.sin(2 * np.pi * hz * 1.003 * t_arr)
              + np.sin(2 * np.pi * hz * 0.997 * t_arr)) / 3.0
        # Very slow attack
        n = len(t_arr)
        slow = np.minimum(np.linspace(0, 1, n) ** 0.7, 1.0).astype(np.float32)
        return (wave * env * slow * 0.5).astype(np.float32)

    def _synth_vibraphone(self, t_arr, hz, env):
        wave = np.sin(2 * np.pi * hz * t_arr)
        # 6Hz tremolo
        trem = 0.7 + 0.3 * np.sin(2 * np.pi * 6.0 * t_arr)
        # Bell-like fast decay
        n = len(t_arr)
        bell = np.exp(-np.linspace(0, 2.5, n)).astype(np.float32)
        return (wave * trem * bell * env * 0.35).astype(np.float32)

    def _synth_flute(self, t_arr, hz, env):
        wave = np.sin(2 * np.pi * hz * t_arr)
        # Breath noise — low-amp white noise
        n = len(t_arr)
        breath = np.random.uniform(-0.05, 0.05, n).astype(np.float32)
        # Slow attack
        attack = max(2, int(n * 0.05))
        slow = env.copy()
        slow[:attack] *= np.linspace(0, 1, attack) ** 1.5
        return ((wave + breath) * slow * 0.4).astype(np.float32)

    def _synth_brass(self, t_arr, hz, env):
        wave = _saw(t_arr, hz) * 0.6 + _square(t_arr, hz) * 0.3
        wave = _bandpass_iir(wave, self.sr, 800, q=2.0) * 0.5 \
             + _bandpass_iir(wave, self.sr, 2500, q=2.5) * 0.4
        n = len(t_arr)
        bright_env = np.minimum(np.linspace(0, 1, n) ** 0.5, 1.0).astype(np.float32)
        return (wave * env * bright_env * 0.45).astype(np.float32)

    def _synth_marimba(self, t_arr, hz, env):
        wave = np.sin(2 * np.pi * hz * t_arr)
        wave += 0.3 * np.sin(2 * np.pi * hz * 4.0 * t_arr)
        n = len(t_arr)
        decay = np.exp(-np.linspace(0, 4, n)).astype(np.float32)
        return (wave * decay * env * 0.35).astype(np.float32)

    def _synth_synth_lead(self, t_arr, hz, env):
        wave = _square(t_arr, hz) * 0.4
        wave += _square(t_arr, hz * 1.005) * 0.3
        wave += np.sin(2 * np.pi * hz * 0.5 * t_arr) * 0.2
        return (wave * env * 0.4).astype(np.float32)

    def _synth_bass(self, t_arr, hz, env):
        low_hz = hz * 0.5 if hz > 120 else hz
        wave = np.sin(2 * np.pi * low_hz * t_arr) * 0.7
        wave += np.sin(2 * np.pi * low_hz * 2 * t_arr) * 0.2
        wave = np.tanh(wave * 2.0) * 0.6
        return (wave * env * 0.5).astype(np.float32)

    def _synth_bells(self, t_arr, hz, env):
        ratios = [1.0, 2.76, 5.4, 8.93]
        wave = sum(np.sin(2 * np.pi * hz * r * t_arr) * (0.5 ** i)
                   for i, r in enumerate(ratios))
        n = len(t_arr)
        decay = np.exp(-np.linspace(0, 2.0, n)).astype(np.float32)
        return (wave * decay * env * 0.25).astype(np.float32)

    def _synth_harp(self, t_arr, hz, env):
        wave = np.sin(2 * np.pi * hz * t_arr)
        wave += 0.3 * np.sin(2 * np.pi * hz * 2 * t_arr)
        wave += 0.15 * np.sin(2 * np.pi * hz * 3 * t_arr)
        n = len(t_arr)
        pluck = np.exp(-np.linspace(0, 3.5, n)).astype(np.float32)
        return (wave * pluck * env * 0.35).astype(np.float32)

    def _synth_default(self, t_arr, hz, env):
        return (np.sin(2 * np.pi * hz * t_arr) * env * 0.4).astype(np.float32)

    @property
    def _instrument_synths(self):
        return {
            'violin':          self._synth_violin,
            'electric_guitar': self._synth_electric_guitar,
            'guitar':          self._synth_guitar,
            'organ':           self._synth_organ,
            'cello':           self._synth_cello,
            'piano':           self._synth_piano,
            'pad':             self._synth_pad,
            'synth_pad':       self._synth_pad,
            'strings':         self._synth_violin,
            'vibraphone':      self._synth_vibraphone,
            'flute':           self._synth_flute,
            'brass':           self._synth_brass,
            'marimba':         self._synth_marimba,
            'synth_lead':      self._synth_synth_lead,
            'bass':            self._synth_bass,
            'bells':           self._synth_bells,
            'harp':            self._synth_harp,
        }

    def _render_instrument(self, name: str, t_arr, hz, env):
        return self._instrument_synths.get(
            name.lower().replace(' ', '_'), self._synth_default
        )(t_arr, hz, env)

    def _kick(self, duration_sec: float) -> np.ndarray:
        '''Synthesise a kick drum: 60 Hz tone with steep pitch+amp decay.'''
        n = int(self.sr * duration_sec)
        t = np.linspace(0, duration_sec, n, endpoint=False)
        f_env = 50 + 70 * np.exp(-t * 25)
        phase = 2 * np.pi * np.cumsum(f_env) / self.sr
        amp_env = np.exp(-t * 10)
        return (np.sin(phase) * amp_env).astype(np.float32)

    def _hat(self, duration_sec: float) -> np.ndarray:
        '''Synthesise a hi-hat: high-pass-ish white noise with fast decay.'''
        n = int(self.sr * duration_sec)
        if n <= 1:
            return np.zeros(0, dtype=np.float32)
        noise = np.random.uniform(-1, 1, n).astype(np.float32)
        window = max(2, int(self.sr * 0.0006))
        if window < n:
            kernel = np.ones(window) / window
            smoothed = np.convolve(noise, kernel, mode="same")
            noise = noise - smoothed
        amp_env = np.exp(-np.linspace(0, 25, n))
        return noise * amp_env
    
    def _normalize(self, waveform: np.ndarray) -> np.ndarray:
        """Normalize to LUFS -14 (safe listening level)."""
        # Simple peak normalization to -0.99 + 0.99
        max_val = np.max(np.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val * 0.99
        return waveform
    
    def _soft_limit(self, waveform: np.ndarray, threshold: float = 0.7) -> np.ndarray:
        """Soft limiting to prevent clipping."""
        # Simple soft clipping using tanh
        return np.tanh(waveform / threshold) * 0.99
    
    def _high_pass_filter(self, waveform: np.ndarray, cutoff_hz: float = 20) -> np.ndarray:
        """Simple high-pass filter (remove subsonic)."""
        # Butterworth-like first-order filter (simplified)
        rc = 1 / (2 * np.pi * cutoff_hz)
        dt = 1 / self.sr
        alpha = dt / (rc + dt)
        
        filtered = np.zeros_like(waveform)
        filtered[0] = waveform[0]
        for i in range(1, len(waveform)):
            filtered[i] = alpha * (filtered[i - 1] + waveform[i] - waveform[i - 1])
        
        return filtered
    
    def _low_pass_filter(self, waveform: np.ndarray, cutoff_hz: float = 20000) -> np.ndarray:
        """Simple low-pass filter (remove ultrasonic)."""
        rc = 1 / (2 * np.pi * cutoff_hz)
        dt = 1 / self.sr
        alpha = dt / (rc + dt)
        
        filtered = np.zeros_like(waveform)
        filtered[0] = waveform[0]
        for i in range(1, len(waveform)):
            filtered[i] = filtered[i - 1] + alpha * (waveform[i] - filtered[i - 1])
        
        return filtered


# Example usage
if __name__ == "__main__":
    synthesizer = DSPSynthesizer(duration=10)
    
    params = {
        "pitch": 220,
        "bpm": 90,
        "instruments": ["pad", "piano"],
        "reverb": 0.4,
        "intensity": 0.7
    }
    
    audio = synthesizer.synthesize(params)
    print(f"Generated {len(audio)} samples ({len(audio) / 22050:.2f} seconds)")
    print(f"Peak: {np.max(np.abs(audio)):.4f}")
    print(f"RMS: {np.sqrt(np.mean(audio ** 2)):.4f}")
