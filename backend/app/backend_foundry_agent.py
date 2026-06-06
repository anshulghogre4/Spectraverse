"""
FoundryAgent — Azure Foundry IQ + GPT-4o vision integration for SpectraVerse.

Three-stage pipeline:
1. describe_image()    → GPT-4o vision returns rich semantic description
2. query_knowledge()   → Foundry IQ knowledge base returns grounded music theory + citations
3. extract_params()    → GPT-4o-mini maps grounded data to DSP parameters

Each stage degrades gracefully:
- Missing AZURE_OPENAI_* env vars        → describe/extract use rule-based mock
- Missing AZURE_SEARCH_*    env vars     → query returns canned music theory
- All env vars set                       → live Foundry IQ + GPT-4o pipeline

This means the /api/generate/image-to-audio-foundry endpoint always returns
a valid response shape, even with zero Azure setup.
"""

from __future__ import annotations
import os
import json
import base64
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# ── Optional Azure SDK imports (fall back to mock when missing) ──────────────
try:
    from openai import AzureOpenAI
    AZURE_OPENAI_SDK = True
except ImportError:
    AZURE_OPENAI_SDK = False
    AzureOpenAI = None  # type: ignore

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
    from azure.search.documents.knowledgebases.models import (
        KnowledgeBaseMessage,
        KnowledgeBaseMessageTextContent,
        KnowledgeBaseRetrievalRequest,
        SearchIndexKnowledgeSourceParams,
    )
    AZURE_SEARCH_SDK = True
except ImportError:
    AZURE_SEARCH_SDK = False


@dataclass
class Citation:
    """A citation from Foundry IQ knowledge base — what the agent quoted."""
    ref_id: str
    doc_key: str
    title: str
    content_snippet: str
    activity_source: int = 0


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
        "key": "C minor", "key_name": "C minor", "bpm": 60,
        "instruments": ["organ", "cello"], "intervals": ["tritone", "minor_2nd"],
        "effects": ["distortion"], "reverb": 0.85, "intensity": 0.9, "complexity": 0.4,
        "rationale": "Tritone intervals + low organ + heavy reverb evoke unease (Music Theory Intervals)",
    },
    "emotional": {
        "key": "A minor", "key_name": "A minor", "bpm": 70,
        "instruments": ["piano", "cello"], "intervals": ["minor_3rd", "minor_7th"],
        "effects": ["reverb"], "reverb": 0.7, "intensity": 0.5, "complexity": 0.5,
        "rationale": "Minor 3rd intervals on piano with cello sustain create yearning melancholy",
    },
    "funny": {
        "key": "C major", "key_name": "C major", "bpm": 130,
        "instruments": ["piano", "vibraphone", "guitar"], "intervals": ["major_3rd", "perfect_5th"],
        "effects": [], "reverb": 0.2, "intensity": 0.7, "complexity": 0.7,
        "rationale": "Major triads + cartoon-fast tempo + bright vibraphone for playful energy",
    },
    "bassy": {
        "key": "F minor", "key_name": "F minor", "bpm": 95,
        "instruments": ["pad", "organ"], "intervals": ["octave", "perfect_5th"],
        "effects": ["compression", "distortion"], "reverb": 0.5, "intensity": 1.0, "complexity": 0.3,
        "rationale": "Sub-octave pad + heavy compression for chest-thumping low frequencies",
    },
    "electrifying": {
        "key": "E major", "key_name": "E major", "bpm": 145,
        "instruments": ["guitar", "piano", "vibraphone"], "intervals": ["major_3rd", "octave"],
        "effects": ["distortion", "delay"], "reverb": 0.4, "intensity": 0.95, "complexity": 0.8,
        "rationale": "Bright E major + driving tempo + delay creates high-arousal electric energy",
    },
    "spiritual": {
        "key": "Lydian", "key_name": "F Lydian mode", "bpm": 55,
        "instruments": ["organ", "pad", "cello"], "intervals": ["perfect_5th", "octave"],
        "effects": ["reverb"], "reverb": 0.95, "intensity": 0.5, "complexity": 0.3,
        "rationale": "Lydian mode + drone 5ths + cathedral reverb evoke sacred ancient sound",
    },
    "experimental": {
        "key": "atonal", "key_name": "Atonal / chromatic", "bpm": 110,
        "instruments": ["pad", "guitar", "vibraphone"], "intervals": ["minor_2nd", "tritone"],
        "effects": ["distortion", "delay"], "reverb": 0.6, "intensity": 0.7, "complexity": 0.9,
        "rationale": "Atonal clusters + dissonant intervals + glitchy effects for avant-garde feel",
    },
}


def _heuristic_key_from_features(features: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based fallback: map image features → musical params (no LLM needed)."""
    brightness = float(features.get("brightness", 0.5))
    color_temp = features.get("color_temperature", "neutral")
    edge_density = float(features.get("texture_edge_density", 0.1))

    # Bright + warm → major key, faster
    # Dark + cool → minor key, slower
    if brightness > 0.6 and color_temp == "warm":
        params = {"key": "D major", "key_name": "D major", "bpm": 110,
                  "instruments": ["pad", "piano"], "intensity": 0.7}
    elif brightness > 0.6 and color_temp == "cool":
        params = {"key": "A major", "key_name": "A major", "bpm": 95,
                  "instruments": ["piano", "vibraphone"], "intensity": 0.6}
    elif brightness < 0.4 and color_temp == "warm":
        params = {"key": "D minor", "key_name": "D minor", "bpm": 70,
                  "instruments": ["cello", "organ"], "intensity": 0.6}
    elif brightness < 0.4 and color_temp == "cool":
        params = {"key": "C minor", "key_name": "C minor", "bpm": 65,
                  "instruments": ["pad", "organ"], "intensity": 0.55}
    else:
        params = {"key": "F major", "key_name": "F major", "bpm": 85,
                  "instruments": ["pad", "piano"], "intensity": 0.6}

    # Edge density → complexity / harmonics
    params["complexity"] = float(min(0.95, 0.3 + edge_density * 2))
    params["reverb"] = 0.4 + (1 - brightness) * 0.3
    params["effects"] = ["reverb"] if params["reverb"] > 0.5 else []
    params["rationale"] = (
        f"Heuristic: brightness={brightness:.2f}, color_temp={color_temp}, "
        f"edges={edge_density:.3f} → {params['key_name']} at {params['bpm']} BPM"
    )
    return params


# ── FoundryAgent — main class ────────────────────────────────────────────────

class FoundryAgent:
    """Orchestrates GPT-4o vision + Foundry IQ + GPT-4o-mini for image→audio."""

    def __init__(self) -> None:
        # Azure OpenAI config (vision + mapping)
        self.aoai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.aoai_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.gpt4o_deployment = os.getenv("AZURE_OPENAI_GPT4O_DEPLOYMENT", "gpt-4o")
        self.gpt4o_mini_deployment = os.getenv("AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT", "gpt-4o-mini")
        self.aoai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")

        # Azure AI Search / Foundry IQ config
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
        self.search_key = os.getenv("AZURE_SEARCH_API_KEY", "")
        self.kb_name = os.getenv("FOUNDRY_KB_NAME", "spectraverse-music-theory-kb")
        self.ks_name = os.getenv("FOUNDRY_KS_NAME", "music-theory-ks")

        # Feature flags
        self.vision_live = bool(self.aoai_endpoint and self.aoai_key and AZURE_OPENAI_SDK)
        self.foundry_live = bool(
            self.search_endpoint and self.search_key and AZURE_SEARCH_SDK
        )
        self.mapping_live = self.vision_live  # Same SDK, same endpoint

        # Lazy-initialised clients
        self._aoai_client: Optional[Any] = None
        self._kb_client: Optional[Any] = None

        logger.info(
            "FoundryAgent initialised — vision=%s, foundry=%s, mapping=%s",
            self.vision_live, self.foundry_live, self.mapping_live,
        )

    # ── Capability summary (for /health and frontend toggle) ─────────────

    def capabilities(self) -> Dict[str, bool]:
        return {
            "vision_live": self.vision_live,
            "foundry_live": self.foundry_live,
            "mapping_live": self.mapping_live,
            "is_fully_live": self.vision_live and self.foundry_live,
        }

    # ── Stage 1: Vision description ──────────────────────────────────────

    def describe_image(self, image_bytes: bytes, style: str = "") -> tuple[str, ReasoningStep]:
        """Returns (rich_description, reasoning_step)."""
        if not self.vision_live:
            desc = _MOCK_IMAGE_DESCRIPTIONS["default"]
            if style:
                desc += f" Style request: {style.title()}."
            return desc, ReasoningStep(
                stage="vision",
                description=f"Mock vision: {desc[:80]}…",
                is_mock=True,
            )

        try:
            client = self._get_aoai_client()
            b64 = base64.b64encode(image_bytes).decode()

            style_hint = (
                f" The user has chosen a '{style}' creative style." if style else ""
            )
            response = client.chat.completions.create(
                model=self.gpt4o_deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert visual analyst describing images to a music composer. "
                            "Describe the image in 2-3 sentences focusing on: dominant colours, "
                            "emotional mood, energy level, scene type, and any narrative implied. "
                            "Be specific and evocative."
                            + style_hint
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
                ],
                max_tokens=200,
                temperature=0.7,
            )
            description = response.choices[0].message.content or ""
            tokens = (
                response.usage.total_tokens if response.usage else 0
            )

            return description, ReasoningStep(
                stage="vision",
                description=description,
                tokens_used=tokens,
                is_mock=False,
            )
        except Exception as e:
            logger.exception("GPT-4o vision call failed — falling back to mock")
            return _MOCK_IMAGE_DESCRIPTIONS["default"], ReasoningStep(
                stage="vision",
                description=f"Vision error ({e}); using mock",
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

            request = KnowledgeBaseRetrievalRequest(
                messages=[
                    KnowledgeBaseMessage(
                        role="assistant",
                        content=[
                            KnowledgeBaseMessageTextContent(
                                text=(
                                    "You are a music theory expert. Answer with specific "
                                    "musical recommendations grounded in cited sources. "
                                    "Each citation has a ref_id."
                                )
                            )
                        ],
                    ),
                    KnowledgeBaseMessage(
                        role="user",
                        content=[KnowledgeBaseMessageTextContent(text=user_query)],
                    ),
                ],
                knowledge_source_params=[
                    SearchIndexKnowledgeSourceParams(
                        knowledge_source_name=self.ks_name,
                        include_references=True,
                        include_reference_source_data=True,
                    )
                ],
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
        # Style overrides take precedence
        if style and style.lower() in STYLE_MAP:
            params = dict(STYLE_MAP[style.lower()])
            return params, ReasoningStep(
                stage="mapping",
                description=f"Style '{style}' → {params['key_name']} at {params['bpm']} BPM",
                is_mock=False,
            )

        if not self.mapping_live:
            params = _heuristic_key_from_features(image_features or {})
            return params, ReasoningStep(
                stage="mapping",
                description=(
                    f"Heuristic mapping → {params.get('key_name')} at {params['bpm']} BPM"
                ),
                is_mock=True,
            )

        try:
            client = self._get_aoai_client()
            citations_text = "\n\n".join(
                f"[{c.ref_id}] {c.title}: {c.content_snippet}" for c in citations[:5]
            )
            response = client.chat.completions.create(
                model=self.gpt4o_mini_deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a music theory mapper. Given an image description and "
                            "cited music theory sources, return a JSON object with these exact keys: "
                            '{"key_name": str, "bpm": int (40-180), "instruments": [str array], '
                            '"complexity": float (0-1), "reverb": float (0-1), "intensity": float (0-1), '
                            '"effects": [str array, can be empty], "rationale": str (one sentence with citation refs like [0])}'
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"IMAGE DESCRIPTION:\n{description}\n\n"
                            f"CITED SOURCES:\n{citations_text}\n\n"
                            f"STYLE PREFERENCE: {style or 'classic'}\n\n"
                            "Return JSON only."
                        ),
                    },
                ],
                max_tokens=400,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            params_raw = response.choices[0].message.content or "{}"
            params = json.loads(params_raw)
            params = self._validate_params(params)
            tokens = response.usage.total_tokens if response.usage else 0

            return params, ReasoningStep(
                stage="mapping",
                description=(
                    f"GPT-4o-mini → {params.get('key_name')} at {params['bpm']} BPM. "
                    f"Rationale: {params.get('rationale', '')[:120]}"
                ),
                tokens_used=tokens,
                is_mock=False,
            )
        except Exception as e:
            logger.exception("Mapping LLM call failed — falling back to heuristic")
            params = _heuristic_key_from_features(image_features or {})
            return params, ReasoningStep(
                stage="mapping",
                description=f"Mapping error ({e}); used heuristic → {params.get('key_name')}",
                is_mock=True,
            )

    # ── Internal helpers ─────────────────────────────────────────────────

    def _get_aoai_client(self) -> Any:
        if self._aoai_client is None:
            self._aoai_client = AzureOpenAI(
                azure_endpoint=self.aoai_endpoint,
                api_key=self.aoai_key,
                api_version=self.aoai_api_version,
            )
        return self._aoai_client

    def _get_kb_client(self) -> Any:
        if self._kb_client is None:
            self._kb_client = KnowledgeBaseRetrievalClient(
                endpoint=self.search_endpoint,
                knowledge_base_name=self.kb_name,
                credential=AzureKeyCredential(self.search_key),
            )
        return self._kb_client

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
                doc_key = (
                    getattr(ref, "doc_key", None) if ref else chunk.get("title", "")
                )
                citations.append(
                    Citation(
                        ref_id=ref_id,
                        doc_key=str(doc_key or chunk.get("title", "")),
                        title=str(chunk.get("title", "")),
                        content_snippet=str(chunk.get("content", ""))[:500],
                        activity_source=int(getattr(ref, "activity_source", 0) or 0),
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
            "instruments": [str(x)[:20] for x in (params.get("instruments") or ["pad"])][:4],
            "complexity": float(max(0.0, min(1.0, params.get("complexity", 0.5)))),
            "reverb": float(max(0.0, min(1.0, params.get("reverb", 0.4)))),
            "intensity": float(max(0.0, min(1.0, params.get("intensity", 0.6)))),
            "effects": [str(x)[:20] for x in (params.get("effects") or [])][:4],
            "rationale": str(params.get("rationale", ""))[:300],
        }
        out["key"] = out["key_name"]  # alias for downstream code
        return out


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

    return {
        "image_description": description,
        "audio_params": params,
        "citations": [asdict(c) for c in citations],
        "reasoning_steps": [asdict(s) for s in (vision_step, retrieval_step, mapping_step)],
        "is_fully_live": agent.capabilities()["is_fully_live"],
        "is_mock": vision_step.is_mock or retrieval_step.is_mock,
    }
