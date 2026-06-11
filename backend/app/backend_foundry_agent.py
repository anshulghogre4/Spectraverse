"""
FoundryAgent — Azure Foundry IQ + multi-provider LLM integration for SpectraVerse.

Three-stage pipeline:
1. describe_image()    → vision model returns rich semantic description
2. query_knowledge()   → Foundry IQ knowledge base returns grounded music theory + citations
3. extract_params()    → mapping model produces DSP parameters with citations

Provider chain (vision + mapping stages) — first available wins:
1. Azure OpenAI       — AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY        (Microsoft Foundry, headline integration)
2. OpenAI direct      — OPENAI_API_KEY                                       (gpt-4o family)
3. Google Gemini      — GEMINI_API_KEY                                       (1500 req/day free, vision-capable)
4. Groq               — GROQ_API_KEY                                         (Llama 4 Maverick — fast, OpenAI-compatible)
5. Mock               — none of the above                                    (canned responses for offline demo)

Foundry IQ knowledge base is independent — works with any LLM provider above.

This means the /api/generate/image-to-audio-foundry endpoint always returns
a valid response shape. Provider used is reported in the response so the
UI can show which AI actually answered.
"""

from __future__ import annotations
import os
import json
import base64
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# ── Optional SDK imports (fall back to mock when missing) ────────────────────
try:
    from openai import AzureOpenAI, OpenAI
    OPENAI_SDK = True
except ImportError:
    OPENAI_SDK = False
    AzureOpenAI = None  # type: ignore
    OpenAI = None  # type: ignore

# Google Gemini and Groq are accessed via OpenAI-compatible endpoints,
# so no extra SDK needed — we just point the OpenAI client at their base URLs.

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
    from azure.search.documents.knowledgebases.models import (
        KnowledgeBaseMessage,
        KnowledgeBaseMessageTextContent,
        KnowledgeBaseRetrievalRequest,
        SearchIndexKnowledgeSourceParams,
    )
    # Intent-based retrieval (required when reasoning_effort=minimal)
    try:
        from azure.search.documents.knowledgebases.models import KnowledgeRetrievalSemanticIntent
    except ImportError:
        KnowledgeRetrievalSemanticIntent = None  # type: ignore
    # Azure Blob Storage knowledge source uses a different params class.
    # Some SDK versions name it differently — try both common shapes.
    try:
        from azure.search.documents.knowledgebases.models import AzureBlobKnowledgeSourceParams
    except ImportError:
        try:
            from azure.search.documents.knowledgebases.models import BlobKnowledgeSourceParams as AzureBlobKnowledgeSourceParams
        except ImportError:
            AzureBlobKnowledgeSourceParams = None  # type: ignore
    AZURE_SEARCH_SDK = True
except ImportError:
    AZURE_SEARCH_SDK = False
    AzureBlobKnowledgeSourceParams = None  # type: ignore
    KnowledgeRetrievalSemanticIntent = None  # type: ignore


@dataclass
class Citation:
    """A citation from Foundry IQ knowledge base — what the agent quoted."""
    ref_id: str
    doc_key: str
    title: str
    content_snippet: str
    activity_source: int = 0
    source_url: str = ""   # original blob URL or null when synthetic


@dataclass
class ReasoningStep:
    """One step in the agent's chain of thought — for the 'show your work' panel."""
    stage: str            # 'vision' | 'retrieval' | 'mapping'
    description: str      # human-readable summary
    duration_ms: int = 0
    tokens_used: int = 0
    is_mock: bool = False  # honest flag — true means no real Azure call happened


# ── Mock data: used when Azure isn't configured ──────────────────────────────

_MOCK_IMAGE_DESCRIPTIONS = {
    # Hashed prefixes of common image features → mock descriptions
    "default": (
        "A scene with mixed warm and cool tones, moderate brightness, and "
        "balanced texture. The mood is contemplative and evocative."
    ),
}

_MOCK_KB_RESPONSE = [
    {
        "ref_id": "0",
        "doc_key": "01_music_theory_keys.md",
        "title": "Music Theory: Keys and Emotional Associations",
        "content": (
            "D minor is associated with tragic, dark, serious emotions — "
            "Mozart Requiem, Bach Toccata & Fugue. For warm-bright images, "
            "C major or D major work well. For dark cool imagery, "
            "C minor or F minor convey despair and depth."
        ),
    },
    {
        "ref_id": "1",
        "doc_key": "03_synesthesia_research.md",
        "title": "Synesthesia and Sound-to-Colour Mappings",
        "content": (
            "Documented composer synesthesia (Scriabin): C=red, D=yellow, "
            "E=sky blue, F=green, G=orange-pink, A=green, B=blue. "
            "Higher pitch correlates with brighter saturated colours."
        ),
    },
    {
        "ref_id": "2",
        "doc_key": "02_music_theory_intervals.md",
        "title": "Music Theory: Intervals and Consonance",
        "content": (
            "Tritone is the most dissonant interval — used in horror sound design. "
            "Perfect 5th feels heroic and open. Minor 3rd is sad and gentle. "
            "For spiritual sound, drone notes and open 5ths feel ancient and monastic."
        ),
    },
]


# ── Style → musical character (deterministic mapping for mock + override) ────

STYLE_MAP: Dict[str, Dict[str, Any]] = {
    "horror": {
        "key": "C minor", "key_name": "C minor", "bpm": 60, "pitch": 196,
        "instruments": ["organ", "cello"], "intervals": ["tritone", "minor_2nd"],
        "effects": ["distortion"], "reverb": 0.85, "intensity": 0.9, "complexity": 0.4,
        "rationale": "Tritone intervals + low organ + heavy reverb evoke unease (Music Theory Intervals)",
    },
    "emotional": {
        "key": "A minor", "key_name": "A minor", "bpm": 70, "pitch": 220,
        "instruments": ["piano", "cello"], "intervals": ["minor_3rd", "minor_7th"],
        "effects": ["reverb"], "reverb": 0.7, "intensity": 0.5, "complexity": 0.5,
        "rationale": "Minor 3rd intervals on piano with cello sustain create yearning melancholy",
    },
    "funny": {
        "key": "C major", "key_name": "C major", "bpm": 130, "pitch": 330,
        "instruments": ["piano", "vibraphone", "guitar"], "intervals": ["major_3rd", "perfect_5th"],
        "effects": [], "reverb": 0.2, "intensity": 0.7, "complexity": 0.7,
        "rationale": "Major triads + cartoon-fast tempo + bright vibraphone for playful energy",
    },
    "bassy": {
        "key": "F minor", "key_name": "F minor", "bpm": 95, "pitch": 175,
        "instruments": ["bass", "pad", "organ"], "intervals": ["octave", "perfect_5th"],
        "effects": ["compression", "distortion"], "reverb": 0.5, "intensity": 1.0, "complexity": 0.3,
        "rationale": "Sub-octave pad + heavy compression for chest-thumping low frequencies",
    },
    "electrifying": {
        "key": "E major", "key_name": "E major", "bpm": 145, "pitch": 330,
        "instruments": ["electric_guitar", "synth_lead", "bass"], "intervals": ["major_3rd", "octave"],
        "effects": ["distortion", "delay"], "reverb": 0.4, "intensity": 0.95, "complexity": 0.8,
        "rationale": "Bright E major + driving tempo + delay creates high-arousal electric energy",
    },
    "spiritual": {
        "key": "Lydian", "key_name": "F Lydian mode", "bpm": 55, "pitch": 261,
        "instruments": ["organ", "pad", "bells"], "intervals": ["perfect_5th", "octave"],
        "effects": ["reverb"], "reverb": 0.95, "intensity": 0.5, "complexity": 0.3,
        "rationale": "Lydian mode + drone 5ths + cathedral reverb evoke sacred ancient sound",
    },
    "experimental": {
        "key": "atonal", "key_name": "Atonal / chromatic", "bpm": 110, "pitch": 293,
        "instruments": ["synth_lead", "electric_guitar", "vibraphone"], "intervals": ["minor_2nd", "tritone"],
        "effects": ["distortion", "delay"], "reverb": 0.6, "intensity": 0.7, "complexity": 0.9,
        "rationale": "Atonal clusters + dissonant intervals + glitchy effects for avant-garde feel",
    },
}


def _describe_audio_features_heuristic(af: Dict[str, Any]) -> str:
    """Rule-based audio description — used when no LLM is available."""
    bpm = af.get("bpm", 90)
    genre = af.get("genre", "unknown")
    vibe = af.get("vibe", "")
    bass = float(af.get("bass_energy", 0))
    treble = float(af.get("treble_energy", 0))
    complexity = float(af.get("complexity", 0.5))
    pitch = af.get("pitch") or {}
    note = pitch.get("note", "") if isinstance(pitch, dict) else ""
    hz = pitch.get("hz", 0) if isinstance(pitch, dict) else 0
    centroid = float(af.get("spectral_centroid", 0))

    tempo_feel = "slow" if bpm < 70 else "moderate" if bpm < 110 else "fast" if bpm < 145 else "driving"
    bass_desc = "heavy bass" if bass > 0.6 else "moderate bass" if bass > 0.3 else "light bass"
    treble_desc = "bright highs" if treble > 0.5 else "warm mids" if treble > 0.25 else "dark/muffled tone"
    complexity_desc = "complex, layered" if complexity > 0.65 else "moderately textured" if complexity > 0.35 else "sparse, minimal"
    note_desc = f", dominant pitch {note} ({int(hz)} Hz)" if note and hz else ""
    centroid_desc = f", spectral centroid {int(centroid)} Hz" if centroid > 0 else ""

    return (
        f"{genre.title()} track with a {vibe} mood — {tempo_feel} at {bpm} BPM. "
        f"{bass_desc.capitalize()}, {treble_desc}, {complexity_desc} arrangement"
        f"{note_desc}{centroid_desc}."
    )


def _heuristic_visual_from_audio(
    audio_features: Dict[str, Any], style: str = ""
) -> tuple:
    """Fallback: pick render_mode + palette from audio features heuristically."""
    STYLE_TO_MODE = {
        "horror": ("horror", ["#1a0a0a", "#3d0000", "#7f0000", "#cc0000", "#ff4444"]),
        "funny":  ("flow_field", ["#ffd700", "#ff69b4", "#00ced1", "#ff8c00", "#7fff00"]),
        "emotional": ("aurora", ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe"]),
        "bassy":  ("bass_pulse", ["#0a0a2e", "#1a1a6e", "#4444cc", "#6666ff", "#aaaaff"]),
        "electrifying": ("lightning", ["#00ffff", "#ff00ff", "#ffff00", "#00ff88", "#ff4400"]),
        "spiritual": ("mandala", ["#fffacd", "#e6d5b8", "#c9b99a", "#b8a285", "#a08060"]),
        "experimental": ("glitch", ["#ff0088", "#00ffcc", "#ffee00", "#8800ff", "#ff4400"]),
    }
    if style and style.lower() in STYLE_TO_MODE:
        return STYLE_TO_MODE[style.lower()]
    vibe = str(audio_features.get("vibe", "")).lower()
    if "dark" in vibe or "heavy" in vibe:
        return ("bass_pulse", ["#0a0a2e", "#1a1a6e", "#4444cc", "#6666ff", "#aaaaff"])
    if "bright" in vibe:
        return ("lightning", ["#00ffff", "#ff00ff", "#ffff00", "#00ff88", "#ff4400"])
    if "warm" in vibe:
        return ("aurora", ["#ff6b35", "#f7c59f", "#fffffc", "#4ecdc4", "#1a535c"])
    return ("orbits", ["#7c3aed", "#2563eb", "#06b6d4", "#10b981", "#f59e0b"])


def _heuristic_key_from_features(features: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based fallback: map image features → musical params (no LLM needed).
    Uses a large pool of configs and hashes image features for variety."""
    import hashlib
    brightness = float(features.get("brightness", 0.5))
    color_temp = features.get("color_temperature", "neutral")
    edge_density = float(features.get("texture_edge_density", 0.1))
    avg_color = features.get("avg_color", {})
    r_val = int(avg_color.get("r", 128))
    g_val = int(avg_color.get("g", 128))
    b_val = int(avg_color.get("b", 128))

    # Hash image features for deterministic-but-varied selection
    feat_hash = int(hashlib.md5(f"{brightness:.3f}:{color_temp}:{edge_density:.3f}:{r_val}:{g_val}:{b_val}".encode()).hexdigest(), 16)

    KEYS_MAJOR = ["C major", "D major", "E major", "F major", "G major", "A major", "Bb major", "Eb major"]
    KEYS_MINOR = ["A minor", "D minor", "E minor", "C minor", "F# minor", "G minor", "B minor", "Eb minor"]
    ALL_INSTRUMENTS = [
        ["pad", "piano"], ["piano", "vibraphone"], ["cello", "organ"], ["harp", "flute", "bells"],
        ["brass", "marimba", "bass"], ["guitar", "piano", "vibraphone"], ["synth_lead", "pad", "bass"],
        ["violin", "cello", "piano"], ["flute", "harp"], ["electric_guitar", "bass", "organ"],
        ["organ", "pad", "cello"], ["bells", "vibraphone", "flute"], ["marimba", "guitar", "flute"],
        ["brass", "piano", "cello"], ["synth_lead", "electric_guitar", "bass"],
    ]
    ALL_INTERVALS = [
        ["minor_3rd", "perfect_5th"], ["major_3rd", "octave"], ["tritone", "minor_2nd"],
        ["perfect_4th", "minor_7th"], ["major_6th", "perfect_5th"], ["minor_6th", "tritone"],
        ["major_7th", "perfect_4th"], ["octave", "minor_3rd"], [],
    ]
    ALL_EFFECTS = [[], ["reverb"], ["delay"], ["distortion"], ["reverb", "delay"], ["compression"]]

    is_minor = brightness < 0.45 or color_temp == "cool"
    keys = KEYS_MINOR if is_minor else KEYS_MAJOR
    key = keys[feat_hash % len(keys)]

    # BPM: brighter/edgier → faster
    base_bpm = 55 + int(brightness * 80) + int(edge_density * 40)
    bpm = max(45, min(170, base_bpm + (feat_hash % 30) - 15))

    instruments = ALL_INSTRUMENTS[(feat_hash >> 4) % len(ALL_INSTRUMENTS)]
    intervals = ALL_INTERVALS[(feat_hash >> 8) % len(ALL_INTERVALS)]
    effects = ALL_EFFECTS[(feat_hash >> 12) % len(ALL_EFFECTS)]
    pitch = 150 + (feat_hash % 400)  # 150-550 Hz range

    intensity = max(0.3, min(0.95, 0.4 + brightness * 0.3 + edge_density * 0.2))
    reverb = max(0.1, min(0.9, 0.3 + (1 - brightness) * 0.4))

    params = {
        "key": key, "key_name": key, "bpm": bpm, "pitch": pitch,
        "instruments": instruments, "intervals": intervals,
        "intensity": intensity, "reverb": reverb, "effects": effects,
        "complexity": float(min(0.95, 0.3 + edge_density * 2)),
        "rationale": (
            f"Heuristic: brightness={brightness:.2f}, color_temp={color_temp}, "
            f"edges={edge_density:.3f}, rgb=({r_val},{g_val},{b_val}) → {key} at {bpm} BPM"
        ),
    }
    return params


# ── FoundryAgent — main class ────────────────────────────────────────────────

class FoundryAgent:
    """Orchestrates GPT-4o vision + Foundry IQ + GPT-4o-mini for image→audio."""

    def __init__(self) -> None:
        # ── Azure OpenAI (priority 1) ───────────────────────────────────
        self.aoai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.aoai_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.gpt4o_deployment = os.getenv("AZURE_OPENAI_GPT4O_DEPLOYMENT", "gpt-4o")
        self.gpt4o_mini_deployment = os.getenv("AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT", "gpt-4o-mini")
        self.aoai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")

        # ── OpenAI direct (priority 2) ──────────────────────────────────
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        # Per user instruction: use gpt-4o for both stages — mini quality is insufficient
        self.openai_vision_model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
        self.openai_mapping_model = os.getenv("OPENAI_MAPPING_MODEL", "gpt-4o")

        # ── Google Gemini (priority 3, free tier) ───────────────────────
        # Get a key at https://aistudio.google.com/apikey — 1500 req/day free
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        # ── Groq (priority 4, free tier) ────────────────────────────────
        # Get a key at https://console.groq.com/keys — 500 RPD on Llama 4 Maverick
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        self.groq_model = os.getenv("GROQ_MODEL", "meta-llama/llama-4-maverick-17b-128e-instruct")

        # ── Foundry IQ knowledge base (independent of LLM provider) ─────
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
        self.search_key = os.getenv("AZURE_SEARCH_API_KEY", "")
        self.kb_name = os.getenv("FOUNDRY_KB_NAME", "spectraverse-music-theory-kb")
        self.ks_name = os.getenv("FOUNDRY_KS_NAME", "music-theory-ks")

        # ── Resolve active providers (in priority order) ────────────────
        self.azure_live = bool(self.aoai_endpoint and self.aoai_key and OPENAI_SDK)
        self.openai_live = bool(self.openai_key and OPENAI_SDK)
        self.gemini_live = bool(self.gemini_key and OPENAI_SDK)
        self.groq_live = bool(self.groq_key and OPENAI_SDK)

        # Provider chain — tried in this order, first success wins per call
        self._provider_chain: List[str] = []
        if self.azure_live:
            self._provider_chain.append("azure")
        if self.openai_live:
            self._provider_chain.append("openai")
        if self.gemini_live:
            self._provider_chain.append("gemini")
        if self.groq_live:
            self._provider_chain.append("groq")

        # Primary provider — what gets reported when no failover is needed
        self.provider = self._provider_chain[0] if self._provider_chain else "mock"

        self.vision_live = self.provider != "mock"
        self.mapping_live = self.vision_live

        self.foundry_live = bool(
            self.search_endpoint and self.search_key and AZURE_SEARCH_SDK
        )

        # Lazy-initialised clients (one per provider)
        self._llm_clients: Dict[str, Any] = {}
        self._kb_client: Optional[Any] = None

        logger.info(
            "FoundryAgent initialised — chain=%s, foundry=%s",
            self._provider_chain, self.foundry_live,
        )

    # ── Capability summary (for /health and frontend toggle) ─────────────

    def capabilities(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,            # "azure" | "openai" | "gemini" | "groq" | "mock"
            "provider_chain": list(self._provider_chain),
            "providers_available": {
                "azure": self.azure_live,
                "openai": self.openai_live,
                "gemini": self.gemini_live,
                "groq": self.groq_live,
            },
            "vision_live": self.vision_live,
            "foundry_live": self.foundry_live,
            "mapping_live": self.mapping_live,
            "is_fully_live": self.vision_live and self.foundry_live,
        }

    # ── Stage 1: Vision description ──────────────────────────────────────

    def describe_image(self, image_bytes: bytes, style: str = "") -> tuple[str, ReasoningStep]:
        """Returns (rich_description, reasoning_step). Cascades through provider chain on failure."""
        if not self.vision_live:
            desc = _MOCK_IMAGE_DESCRIPTIONS["default"]
            if style:
                desc += f" Style request: {style.title()}."
            return desc, ReasoningStep(
                stage="vision",
                description=f"Mock vision: {desc[:80]}…",
                is_mock=True,
            )

        b64 = base64.b64encode(image_bytes).decode()
        style_hint = (
            f" The user has chosen a '{style}' creative style." if style else ""
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert visual analyst describing images to a music composer. "
                    "Describe the image in 2-3 sentences focusing on: dominant colours, "
                    "emotional mood, energy level, scene type, and any narrative implied. "
                    "Be specific and evocative." + style_hint
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image for music composition."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            },
        ]

        attempts: List[str] = []
        for provider in self._provider_chain:
            try:
                client = self._get_llm_client(provider)
                response = client.chat.completions.create(
                    model=self._vision_model_id(provider),
                    messages=messages,
                    max_tokens=200,
                    temperature=0.7,
                )
                description = response.choices[0].message.content or ""
                tokens = response.usage.total_tokens if response.usage else 0
                attempts.append(provider)

                attempt_note = (
                    f" (after {', '.join(a + ' failed' for a in attempts[:-1])})"
                    if len(attempts) > 1 else ""
                )
                return description, ReasoningStep(
                    stage="vision",
                    description=f"[{provider}/{self._vision_model_id(provider)}{attempt_note}] {description}",
                    tokens_used=tokens,
                    is_mock=False,
                )
            except Exception as e:
                logger.warning("Vision: %s failed (%s) — trying next", provider, e)
                attempts.append(provider)
                continue

        # All providers exhausted — fall back to mock
        logger.error("All providers in chain failed for vision: %s", attempts)
        return _MOCK_IMAGE_DESCRIPTIONS["default"], ReasoningStep(
            stage="vision",
            description=f"All providers failed ({', '.join(attempts)}); using mock",
            is_mock=True,
        )

    # ── Stage 2: Foundry IQ knowledge retrieval ──────────────────────────

    def query_knowledge(
        self, description: str, style: str = ""
    ) -> tuple[List[Citation], ReasoningStep]:
        """Returns (citations, reasoning_step)."""
        if not self.foundry_live:
            citations = [
                Citation(
                    ref_id=item["ref_id"],
                    doc_key=item["doc_key"],
                    title=item["title"],
                    content_snippet=item["content"],
                )
                for item in _MOCK_KB_RESPONSE
            ]
            return citations, ReasoningStep(
                stage="retrieval",
                description=(
                    f"Mock KB: returned {len(citations)} canned music-theory citations "
                    "(Foundry IQ not configured)"
                ),
                is_mock=True,
            )

        try:
            kb_client = self._get_kb_client()

            user_query = (
                f"For an image described as: '{description}'. "
                f"What musical key, BPM, instruments, intervals, and effects best represent it? "
                f"Style preference: {style or 'classic'}. Cite music theory and synesthesia research."
            )

            # Foundry IQ retrieval API supports two input shapes:
            #   - messages: requires reasoning_effort >= 'low' (needs LLM-backed planning)
            #   - intents:  works with reasoning_effort=minimal (pure semantic retrieval)
            # Our KB is configured with Minimal effort, so we use intents.
            if KnowledgeRetrievalSemanticIntent is not None:
                request = KnowledgeBaseRetrievalRequest(
                    intents=[KnowledgeRetrievalSemanticIntent(search=user_query)],
                    knowledge_source_params=[self._build_ks_params()],
                )
            else:
                # Older SDK fallback — raw dict shape that the REST API accepts
                request = KnowledgeBaseRetrievalRequest(
                    intents=[{"type": "semantic", "search": user_query}],
                    knowledge_source_params=[self._build_ks_params()],
                )

            result = kb_client.retrieve(request)
            citations = self._parse_citations(result)
            tokens = self._estimate_tokens_from_activity(result)

            return citations, ReasoningStep(
                stage="retrieval",
                description=(
                    f"Foundry IQ retrieved {len(citations)} citations from "
                    f"knowledge base '{self.kb_name}'"
                ),
                tokens_used=tokens,
                is_mock=False,
            )
        except Exception as e:
            logger.exception("Foundry IQ retrieve failed — falling back to mock")
            return [
                Citation(
                    ref_id=item["ref_id"], doc_key=item["doc_key"],
                    title=item["title"], content_snippet=item["content"],
                )
                for item in _MOCK_KB_RESPONSE
            ], ReasoningStep(
                stage="retrieval",
                description=f"Foundry IQ error ({e}); using mock",
                is_mock=True,
            )

    # ── Stage 3: Param extraction ────────────────────────────────────────

    def extract_params(
        self,
        description: str,
        citations: List[Citation],
        style: str,
        image_features: Optional[Dict[str, Any]] = None,
    ) -> tuple[Dict[str, Any], ReasoningStep]:
        """Returns (audio_params_dict, reasoning_step)."""
        '''
        STYLE_MAP semantics (post-S3-01 fix):
        - When LLM is live: STYLE_MAP becomes a "prior" passed to the LLM mapping prompt.
          The LLM may stay close to it or override based on retrieved citations.
        - When LLM is not live: STYLE_MAP IS the params, but is_mock=True so the panel
          is honest.
        - There is NO early-return shortcircuit. The reasoning panel never lies.
        '''
        style_prior = STYLE_MAP.get(style.lower()) if style else None

        if not self.mapping_live:
            if style_prior:
                params = dict(style_prior)
                return params, ReasoningStep(
                    stage="mapping",
                    description=(
                        f"STYLE_MAP fallback (no LLM): style '{style}' → "
                        f"{params['key_name']} at {params['bpm']} BPM"
                    ),
                    is_mock=True,
                )
            params = _heuristic_key_from_features(image_features or {})
            return params, ReasoningStep(
                stage="mapping",
                description=(
                    f"Heuristic mapping → {params.get('key_name')} at {params['bpm']} BPM"
                ),
                is_mock=True,
            )

        citations_text = "\n\n".join(
            f"[{c.ref_id}] {c.title}: {c.content_snippet}" for c in citations[:5]
        )
        style_prior_block = ""
        if style_prior:
            style_prior_block = (
                f"\n\nCREATIVE STYLE PRIOR: The user requested style='{style}'. "
                f"Treat these as strong hints unless citations contradict them: "
                f"key={style_prior['key_name']}, bpm={style_prior['bpm']}, "
                f"instruments={style_prior['instruments']}, "
                f"intervals={style_prior['intervals']}, "
                f"effects={style_prior['effects']}. "
                f"Use these as inspiration but feel free to explore contrasting or complementary choices based on the cited sources."
            )
        import random as _rng
        diversity_seed = _rng.randint(1, 999)
        diversity_hint = (
            f"\n\nDIVERSITY SEED: {diversity_seed}. Use this seed as creative inspiration — "
            f"pick a key and instruments you haven't chosen recently. "
            f"Odd seed → prefer sharp keys (E, B, F#, C#). Even seed → prefer flat keys (Eb, Bb, Ab, Db). "
            f"Seed mod 5 == 0 → use brass or marimba. Seed mod 3 == 0 → use bells or harp. "
            f"Avoid piano+pad as default combo — there are 17 instruments available."
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a music theory mapper. Given an image description and "
                    "cited music theory sources, return ONLY a valid JSON object with these exact keys: "
                    '{"key_name": str (e.g. "C minor", "F# major"), "bpm": int (40-180), '
                    '"pitch": int (Hz, root note frequency 100-800), '
                    '"instruments": [str array, pick 2-3 from: pad, piano, vibraphone, guitar, electric_guitar, cello, organ, flute, brass, marimba, synth_lead, bass, bells, harp, violin], '
                    '"intervals": [str array from: minor_second, major_second, minor_third, major_third, '
                    'perfect_fourth, tritone, perfect_fifth, minor_sixth, major_sixth, minor_seventh, major_seventh], '
                    '"complexity": float (0-1), "reverb": float (0-1), "intensity": float (0-1), '
                    '"effects": [str array from: reverb, delay, distortion, compression, or empty], '
                    '"rationale": str (one sentence with citation refs like [0])}. '
                    "CRITICAL: Maximize variety. Every image MUST get a unique combination of key, BPM, instruments, and intervals. "
                    "Avoid defaulting to C major/A minor or piano/pad combos. "
                    "Bright warm → consider D major, brass+marimba, fast BPM. Dark moody → try Eb minor, cello+synth_lead, slow BPM. "
                    "Nature → harp+flute+bells, moderate BPM. Urban → electric_guitar+bass+organ, high BPM. "
                    "Abstract → vibraphone+synth_lead+pad with tritone/minor_seventh intervals. "
                    "Always vary: don't repeat the same mapping for similar images. "
                    "Do not wrap the JSON in markdown code fences. Output the JSON object only."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"IMAGE DESCRIPTION:\n{description}\n\n"
                    f"CITED SOURCES:\n{citations_text}\n\n"
                    f"STYLE PREFERENCE: {style or 'classic'}"
                    f"{style_prior_block}"
                    f"{diversity_hint}\n\n"
                    "Return JSON only."
                ),
            },
        ]

        attempts: List[str] = []
        for provider in self._provider_chain:
            try:
                client = self._get_llm_client(provider)
                kwargs: Dict[str, Any] = dict(
                    model=self._mapping_model_id(provider),
                    messages=messages,
                    max_tokens=400,
                    temperature=0.7,
                )
                # response_format only on Azure/OpenAI; Gemini/Groq parse loosely
                if provider in ("azure", "openai"):
                    kwargs["response_format"] = {"type": "json_object"}

                response = client.chat.completions.create(**kwargs)
                params_raw = response.choices[0].message.content or "{}"
                params = self._parse_json_loose(params_raw)
                params = self._validate_params(params)
                tokens = response.usage.total_tokens if response.usage else 0
                attempts.append(provider)

                attempt_note = (
                    f" (after {', '.join(a + ' failed' for a in attempts[:-1])})"
                    if len(attempts) > 1 else ""
                )
                style_note = f" (style prior: {style})" if style_prior else ""

                # Build cited narration
                rationale = params.get("rationale", "")
                narration_parts = []
                if rationale:
                    narration_parts.append(rationale)
                for c in citations[:2]:
                    snippet = c.content_snippet[:80].rstrip()
                    if snippet and c.ref_id:
                        narration_parts.append(f"[{c.ref_id}] {snippet}…")
                params["narration"] = " ".join(narration_parts)

                mapping_description = (
                    f"[{provider}/{self._mapping_model_id(provider)}{attempt_note}] "
                    f"→ {params.get('key_name')} at {params['bpm']} BPM. "
                    f"Rationale: {params.get('rationale', '')[:120]}{style_note}"
                )
                narration_suffix = params["narration"][:200]
                if narration_suffix and narration_suffix not in mapping_description:
                    mapping_description += f" | {narration_suffix}"

                return params, ReasoningStep(
                    stage="mapping",
                    description=mapping_description,
                    tokens_used=tokens,
                    is_mock=False,
                )
            except Exception as e:
                logger.warning("Mapping: %s failed (%s) — trying next", provider, e)
                attempts.append(provider)
                continue

        # All providers exhausted — heuristic fallback
        logger.error("All providers in chain failed for mapping: %s", attempts)
        params = _heuristic_key_from_features(image_features or {})
        return params, ReasoningStep(
            stage="mapping",
            description=f"All providers failed ({', '.join(attempts)}); used heuristic → {params.get('key_name')}",
            is_mock=True,
        )

    # ── Stage 1b: Audio description ─────────────────────────────────────

    def describe_audio(self, audio_features: Dict[str, Any]) -> tuple[str, ReasoningStep]:
        """
        Ask the LLM to write a rich musical description from extracted audio features.
        Falls back to the heuristic string when no LLM is available.
        Returns (description, reasoning_step).
        """
        pitch = audio_features.get("pitch") or {}
        note = pitch.get("note", "") if isinstance(pitch, dict) else ""
        hz = pitch.get("hz", 0) if isinstance(pitch, dict) else 0

        features_block = (
            f"BPM: {audio_features.get('bpm', 90)}\n"
            f"Genre: {audio_features.get('genre', 'unknown')}\n"
            f"Vibe: {audio_features.get('vibe', 'unknown')}\n"
            f"Bass energy: {round(float(audio_features.get('bass_energy', 0)), 3)}\n"
            f"Treble energy: {round(float(audio_features.get('treble_energy', 0)), 3)}\n"
            f"Complexity: {round(float(audio_features.get('complexity', 0.5)), 3)}\n"
            f"Spectral centroid: {int(float(audio_features.get('spectral_centroid', 0)))} Hz\n"
            + (f"Dominant pitch: {note} ({int(hz)} Hz)\n" if note and hz else "")
        )

        if not self.vision_live:
            desc = _describe_audio_features_heuristic(audio_features)
            return desc, ReasoningStep(
                stage="vision",
                description=f"Heuristic audio description (no LLM): {desc[:120]}",
                is_mock=True,
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a music journalist describing a piece of audio to an artist "
                    "who will create visuals for it. Given extracted audio features, write "
                    "2-3 vivid sentences covering: the emotional mood and energy, the sonic "
                    "texture (bass heaviness, brightness, complexity), the tempo feel, and "
                    "any implied genre or scene. Be evocative and specific — avoid generic phrases."
                ),
            },
            {
                "role": "user",
                "content": f"Describe this audio for visual composition:\n\n{features_block}",
            },
        ]

        attempts: List[str] = []
        for provider in self._provider_chain:
            try:
                client = self._get_llm_client(provider)
                response = client.chat.completions.create(
                    model=self._mapping_model_id(provider),
                    messages=messages,
                    max_tokens=180,
                    temperature=0.7,
                )
                description = response.choices[0].message.content or ""
                tokens = response.usage.total_tokens if response.usage else 0
                attempts.append(provider)
                attempt_note = (
                    f" (after {', '.join(a + ' failed' for a in attempts[:-1])})"
                    if len(attempts) > 1 else ""
                )
                return description, ReasoningStep(
                    stage="vision",
                    description=f"[{provider}/{self._mapping_model_id(provider)}{attempt_note}] {description[:120]}",
                    tokens_used=tokens,
                    is_mock=False,
                )
            except Exception as e:
                logger.warning("describe_audio: %s failed (%s) — trying next", provider, e)
                attempts.append(provider)
                continue

        desc = _describe_audio_features_heuristic(audio_features)
        return desc, ReasoningStep(
            stage="vision",
            description=f"All providers failed ({', '.join(attempts)}); using heuristic",
            is_mock=True,
        )

    # ── Audio → Visual pipeline ──────────────────────────────────────────

    def audio_to_visual(
        self,
        audio_features: Dict[str, Any],
        style: str = "",
    ) -> Dict[str, Any]:
        """
        2-stage pipeline for audio→visual Foundry IQ grounding.
        Stage 1: retrieve visual aesthetic citations for the audio's genre/vibe.
        Stage 2: LLM maps to render_mode + palette + rationale.
        Returns dict with: render_mode, palette, reasoning_steps, citations, is_mock.
        """
        # Stage 1: retrieval
        vibe = audio_features.get("vibe", "balanced")
        genre = audio_features.get("genre", "mixed")
        bpm = audio_features.get("bpm", 90)
        pitch_note = audio_features.get("pitch_note", "")

        query = (
            f"Audio has vibe='{vibe}', genre='{genre}', BPM={bpm}. "
            f"What visual aesthetic, colour palette, motion style, and particle "
            f"behaviour best represents this music? Cite synesthesia or film score "
            f"research. Style preference: {style or 'classic'}."
        )

        citations, retrieval_step = self.query_knowledge(query, style)

        # Stage 2: mapping
        if not self.mapping_live:
            # Fallback: heuristic palette from vibe
            render_mode, palette = _heuristic_visual_from_audio(audio_features, style)
            return {
                "render_mode": render_mode,
                "palette": palette,
                "reasoning_steps": [asdict(retrieval_step)],
                "citations": [asdict(c) for c in citations],
                "is_mock": True,
                "provider": self.provider,
            }

        citations_text = "\n\n".join(
            f"[{c.ref_id}] {c.title}: {c.content_snippet}" for c in citations[:5]
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a visual artist mapping music to visuals. "
                    "Given audio features and cited aesthetic research, return ONLY a JSON object: "
                    '{"render_mode": str, "palette": [5 hex color strings], "rationale": str (1 sentence citing [ref_id])}. '
                    "render_mode must be one of: orbits, flow_field, lightning, horror, aurora, bass_pulse, mandala, glitch, "
                    "waveform, spectrum_bars, fireworks, rain, vortex, matrix, plasma, nebula, starfield, rings, dna_helix, kaleidoscope, "
                    "terrain, tunnel, galaxy, ripple, lissajous, spirograph, metaballs, fractal_tree, circular_spectrum, wave_terrain, "
                    "interference, pixel_sort, neon_grid, pendulum, bubbles, constellation, cube_field, frequency_spiral, smoke_trails, "
                    "bouncing_bars, wave_mesh, comet_trails, heartbeat, radar, vinyl, equalizer_circle, neon_tunnel, particle_fountain, wormhole, laser_show. "
                    "Pick vivid, saturated colors. Vary your choice — don't default to the same mode. "
                    "Do not wrap in markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"AUDIO FEATURES: vibe={vibe}, genre={genre}, BPM={bpm}, note={pitch_note}\n\n"
                    f"CITED SOURCES:\n{citations_text}\n\n"
                    f"STYLE PREFERENCE: {style or 'classic'}\n\nReturn JSON only."
                ),
            },
        ]

        attempts: List[str] = []
        for provider in self._provider_chain:
            try:
                client = self._get_llm_client(provider)
                kwargs: Dict[str, Any] = dict(
                    model=self._mapping_model_id(provider),
                    messages=messages,
                    max_tokens=200,
                    temperature=0.7,
                )
                if provider in ("azure", "openai"):
                    kwargs["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(**kwargs)
                raw = response.choices[0].message.content or "{}"
                parsed = self._parse_json_loose(raw)
                render_mode = parsed.get("render_mode", "orbits")
                palette = parsed.get("palette") or []
                if not isinstance(palette, list) or len(palette) < 3:
                    palette = _heuristic_visual_from_audio(audio_features, style)[1]
                rationale = parsed.get("rationale", "")
                tokens = response.usage.total_tokens if response.usage else 0
                attempts.append(provider)
                attempt_note = (
                    f" (after {', '.join(a + ' failed' for a in attempts[:-1])})"
                    if len(attempts) > 1 else ""
                )
                mapping_step = ReasoningStep(
                    stage="mapping",
                    description=f"[{provider}/{self._mapping_model_id(provider)}{attempt_note}] → {render_mode}. {rationale[:120]}",
                    tokens_used=tokens,
                    is_mock=False,
                )
                return {
                    "render_mode": render_mode,
                    "palette": palette,
                    "reasoning_steps": [asdict(retrieval_step), asdict(mapping_step)],
                    "citations": [asdict(c) for c in citations],
                    "is_mock": retrieval_step.is_mock,
                    "provider": provider,
                }
            except Exception as e:
                logger.warning("audio_to_visual mapping: %s failed (%s)", provider, e)
                attempts.append(provider)
                continue

        render_mode, palette = _heuristic_visual_from_audio(audio_features, style)
        return {
            "render_mode": render_mode,
            "palette": palette,
            "reasoning_steps": [asdict(retrieval_step)],
            "citations": [asdict(c) for c in citations],
            "is_mock": True,
            "provider": "mock",
        }

    # ── Spectrogram vision description ──────────────────────────────────

    def describe_spectrogram(
        self, image_bytes: bytes
    ) -> Dict[str, Any]:
        """
        Use vision LLM to infer spectrogram parameters from a screenshot.
        Returns: {colormap, scale, sample_rate_hz, db_min, db_max, source_tool,
                  reasoning_step, is_mock}
        """
        if not self.vision_live:
            return {
                "colormap": "viridis",
                "scale": "mel",
                "sample_rate_hz": 22050,
                "db_min": -80,
                "db_max": 0,
                "source_tool": "librosa",
                "reasoning_step": asdict(ReasoningStep(
                    stage="vision",
                    description="Mock spectrogram vision (no LLM configured)",
                    is_mock=True,
                )),
                "is_mock": True,
            }

        b64 = base64.b64encode(image_bytes).decode()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert at reading scientific spectrograms. "
                    "Analyse the provided spectrogram image and return ONLY a JSON object "
                    "with these exact keys (no markdown, no extra text): "
                    '{"colormap": str (viridis|magma|plasma|inferno|hot|jet|coolwarm|greyscale|other), '
                    '"scale": str (mel|linear|log_linear), '
                    '"sample_rate_hz": int (8000|16000|22050|44100|48000), '
                    '"db_min": int (typical -120 to -60), '
                    '"db_max": int (typical -20 to 0), '
                    '"source_tool": str (librosa|audacity|praat|chrome_music_lab|sonic_visualiser|adobe_audition|unknown), '
                    '"confidence_notes": str (one sentence on what visual cues led to these estimates)}'
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyse this spectrogram image and return the JSON parameters."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            },
        ]

        attempts: List[str] = []
        for provider in self._provider_chain:
            try:
                client = self._get_llm_client(provider)
                response = client.chat.completions.create(
                    model=self._vision_model_id(provider),
                    messages=messages,
                    max_tokens=250,
                    temperature=0.1,
                )
                raw = response.choices[0].message.content or "{}"
                parsed = self._parse_json_loose(raw)
                tokens = response.usage.total_tokens if response.usage else 0
                attempts.append(provider)
                attempt_note = (
                    f" (after {', '.join(a + ' failed' for a in attempts[:-1])})"
                    if len(attempts) > 1 else ""
                )
                return {
                    "colormap": str(parsed.get("colormap", "viridis")),
                    "scale": str(parsed.get("scale", "mel")),
                    "sample_rate_hz": int(parsed.get("sample_rate_hz", 22050)),
                    "db_min": int(parsed.get("db_min", -80)),
                    "db_max": int(parsed.get("db_max", 0)),
                    "source_tool": str(parsed.get("source_tool", "unknown")),
                    "confidence_notes": str(parsed.get("confidence_notes", "")),
                    "reasoning_step": asdict(ReasoningStep(
                        stage="vision",
                        description=(
                            f"[{provider}/{self._vision_model_id(provider)}{attempt_note}] "
                            f"Detected: {parsed.get('scale','mel')} scale, "
                            f"{parsed.get('colormap','viridis')} colormap, "
                            f"sr={parsed.get('sample_rate_hz',22050)}, "
                            f"tool={parsed.get('source_tool','unknown')}. "
                            f"{parsed.get('confidence_notes','')}"
                        ),
                        tokens_used=tokens,
                        is_mock=False,
                    )),
                    "is_mock": False,
                }
            except Exception as e:
                logger.warning("describe_spectrogram: %s failed (%s)", provider, e)
                attempts.append(provider)
                continue

        return {
            "colormap": "viridis", "scale": "mel", "sample_rate_hz": 22050,
            "db_min": -80, "db_max": 0, "source_tool": "unknown",
            "confidence_notes": f"All providers failed: {', '.join(attempts)}",
            "reasoning_step": asdict(ReasoningStep(
                stage="vision",
                description=f"All providers failed ({', '.join(attempts)}); using heuristic fallback",
                is_mock=True,
            )),
            "is_mock": True,
        }

    # ── Internal helpers ─────────────────────────────────────────────────

    def _get_llm_client(self, provider: str) -> Any:
        """Return an OpenAI-compatible client for the given provider (cached)."""
        if provider in self._llm_clients:
            return self._llm_clients[provider]

        if provider == "azure":
            client = AzureOpenAI(
                azure_endpoint=self.aoai_endpoint,
                api_key=self.aoai_key,
                api_version=self.aoai_api_version,
            )
        elif provider == "openai":
            client = OpenAI(api_key=self.openai_key)
        elif provider == "gemini":
            # Google Gemini exposes an OpenAI-compatible endpoint
            client = OpenAI(
                api_key=self.gemini_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
        elif provider == "groq":
            client = OpenAI(
                api_key=self.groq_key,
                base_url="https://api.groq.com/openai/v1",
            )
        else:
            raise RuntimeError(f"Unknown provider: {provider}")

        self._llm_clients[provider] = client
        return client

    def _vision_model_id(self, provider: str) -> str:
        """Model id for vision call — varies by provider."""
        if provider == "azure":
            return self.gpt4o_deployment
        if provider == "openai":
            return self.openai_vision_model
        if provider == "gemini":
            return self.gemini_model
        if provider == "groq":
            return self.groq_model
        return ""

    def _mapping_model_id(self, provider: str) -> str:
        """Model id for mapping call — varies by provider."""
        if provider == "azure":
            return self.gpt4o_deployment  # gpt-4o for both stages per user request
        if provider == "openai":
            return self.openai_mapping_model
        if provider == "gemini":
            return self.gemini_model
        if provider == "groq":
            return self.groq_model
        return ""

    def _get_kb_client(self) -> Any:
        if self._kb_client is None:
            self._kb_client = KnowledgeBaseRetrievalClient(
                endpoint=self.search_endpoint,
                knowledge_base_name=self.kb_name,
                credential=AzureKeyCredential(self.search_key),
            )
        return self._kb_client

    def _build_ks_params(self) -> Any:
        """
        Build knowledge_source_params matching the kind registered in Foundry.
        Our portal-created source is kind=azureBlob, so we must send blob params,
        not the searchIndex variant. Falls through provider class names that
        differ between Azure Search SDK versions.
        """
        # Preferred: explicit Azure Blob class
        if AzureBlobKnowledgeSourceParams is not None:
            return AzureBlobKnowledgeSourceParams(
                knowledge_source_name=self.ks_name,
                include_references=True,
                include_reference_source_data=True,
            )
        # Last-resort: build a raw dict that the REST API accepts.
        # 'kind' must match the registered source's kind exactly.
        return {
            "kind": "azureBlob",
            "knowledgeSourceName": self.ks_name,
            "includeReferences": True,
            "includeReferenceSourceData": True,
        }

    def _clean_doc_key(self, raw: str) -> tuple[str, str]:
        """Returns (clean_title, proxy_url). Rewrites private blob URLs to local proxy."""
        if not raw:
            return ("unknown source", "")
        s = str(raw)
        import re
        if s.startswith("http://") or s.startswith("https://") or "blob.core.windows.net" in s:
            # Extract path segments: .../knowledge-base/category/filename.md
            basename = s.rsplit("/", 1)[-1].split("?", 1)[0]
            # Try to extract category from the path (e.g., cross_modal, spectrogram_tools)
            parts = s.split("?", 1)[0].rsplit("/", 2)
            if len(parts) >= 3:
                category = parts[-2]
                filename = parts[-1]
                proxy_url = f"/api/knowledge-base/{category}/{filename}"
            else:
                proxy_url = ""
            # Clean basename for display
            display = basename
            for ext in (".md", ".txt", ".markdown"):
                if display.lower().endswith(ext):
                    display = display[: -len(ext)]
                    break
            display = re.sub(r"^\d+[_\-]\s*", "", display)
            display = display.replace("_", " ").replace("-", " ")
            return (display.strip().title() or "Indexed document", proxy_url)
        return (s, "")

    def _parse_citations(self, result: Any) -> List[Citation]:
        """Parse the KB retrieve response into Citation objects."""
        citations: List[Citation] = []
        try:
            content_text = result.response[0].content[0].text
            chunks = json.loads(content_text)
            references = getattr(result, "references", []) or []
            ref_lookup = {
                str(getattr(r, "id", "")): r for r in references
            }
            for chunk in chunks[:5]:
                ref_id = str(chunk.get("ref_id", ""))
                ref = ref_lookup.get(ref_id)

                # Reference attribute names differ between source kinds.
                # Blob refs have `blob_url`, `source_data`, etc. Index refs use `doc_key`.
                # Try them in order — first non-empty wins.
                raw_value = (
                    chunk.get("title")
                    or (getattr(ref, "doc_key", None) if ref else None)
                    or (getattr(ref, "blob_url", None) if ref else None)
                    or (getattr(ref, "source_data", None) if ref else None)
                    or (getattr(ref, "id", None) if ref else None)
                    or "unknown source"
                )
                clean_title, source_url = self._clean_doc_key(str(raw_value))
                citations.append(
                    Citation(
                        ref_id=ref_id,
                        doc_key=clean_title[:200],
                        title=str(chunk.get("title", "")),
                        content_snippet=str(chunk.get("content", ""))[:500],
                        activity_source=int(
                            getattr(ref, "activity_source", 0) or 0
                        ) if ref else 0,
                        source_url=source_url,
                    )
                )
        except Exception as e:
            logger.warning("Could not parse KB response: %s", e)
        return citations

    def _estimate_tokens_from_activity(self, result: Any) -> int:
        try:
            total = 0
            for act in getattr(result, "activity", []) or []:
                total += int(getattr(act, "input_tokens", 0) or 0)
                total += int(getattr(act, "output_tokens", 0) or 0)
                total += int(getattr(act, "reasoning_tokens", 0) or 0)
            return total
        except Exception:
            return 0

    def _validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Clamp + sanitise params from the LLM into safe ranges."""
        out = {
            "key_name": str(params.get("key_name", "C major"))[:40],
            "bpm": int(max(40, min(180, params.get("bpm", 90)))),
            "pitch": int(max(80, min(1000, params.get("pitch", 220)))),
            "instruments": [str(x)[:20] for x in (params.get("instruments") or ["pad"])][:4],
            "intervals": [str(x)[:20] for x in (params.get("intervals") or [])][:6],
            "complexity": float(max(0.0, min(1.0, params.get("complexity", 0.5)))),
            "reverb": float(max(0.0, min(1.0, params.get("reverb", 0.4)))),
            "intensity": float(max(0.0, min(1.0, params.get("intensity", 0.6)))),
            "effects": [str(x)[:20] for x in (params.get("effects") or [])][:4],
            "rationale": str(params.get("rationale", ""))[:300],
        }
        out["key"] = out["key_name"]  # alias for downstream code
        return out

    def _parse_json_loose(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON tolerantly. Some providers (Gemini, Groq) wrap JSON
        in markdown code fences or add chatter. Try strict, then fall back
        to extracting the first {...} block.
        """
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("```", 2)[1] if "```" in text[3:] else text[3:]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0].strip()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        # Last resort: regex-extract the outermost JSON object
        import re
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        logger.warning("Could not parse JSON from LLM response: %r", text[:120])
        return {}


# ── Convenience wrapper ──────────────────────────────────────────────────────

def build_foundry_pipeline_response(
    agent: FoundryAgent,
    image_bytes: bytes,
    style: str = "",
    image_features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the full 3-stage Foundry pipeline; return a flat response dict."""
    description, vision_step = agent.describe_image(image_bytes, style)
    citations, retrieval_step = agent.query_knowledge(description, style)
    params, mapping_step = agent.extract_params(
        description, citations, style, image_features
    )

    caps = agent.capabilities()
    return {
        "image_description": description,
        "audio_params": params,
        "citations": [asdict(c) for c in citations],
        "reasoning_steps": [asdict(s) for s in (vision_step, retrieval_step, mapping_step)],
        "provider": caps["provider"],
        "providers_available": caps["providers_available"],
        "is_fully_live": caps["is_fully_live"],
        "is_mock": vision_step.is_mock or retrieval_step.is_mock,
        "narration": params.get("narration", ""),
    }
