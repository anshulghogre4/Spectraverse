# Foundry IQ — Authoritative Context for SpectraVerse

**Source**: Microsoft Learn docs (verified 2026-06-06)  
**Purpose**: Single reference for all Sprint 3 Foundry IQ implementation work

---

## What Foundry IQ Actually Is

Foundry IQ is a **managed knowledge layer** for Azure AI agents. It's NOT a model — it's a retrieval system built on **Azure AI Search** that:

- Connects agents to enterprise/web/file content via **knowledge sources**
- Groups them under a top-level **knowledge base**
- Performs **agentic retrieval**: an LLM decomposes a complex query into focused sub-queries, runs them in parallel against the knowledge sources, semantically reranks results, and returns answers with **citations**

Three IQ flavours exist (Foundry IQ is the one we want):
| Flavour | Domain |
|---|---|
| **Foundry IQ** | Generic enterprise / file / web knowledge — what we're using |
| Fabric IQ | Microsoft Fabric / Power BI analytics |
| Work IQ | Microsoft 365 collaboration signals |

---

## The Three Core Objects

```
   ┌─────────────────────────────────────┐
   │      KNOWLEDGE BASE                 │  ← Your agent talks to this
   │   "music-theory-kb"                 │
   │                                     │
   │   ▶ knowledge_sources [...]         │
   │   ▶ models [GPT-4o-mini for LLM]    │
   │   ▶ output_mode (extracted | synth) │
   │   ▶ retrieval_reasoning_effort      │
   └────────────┬────────────────────────┘
                │
   ┌────────────┴────────────────────────┐
   │      KNOWLEDGE SOURCE                │
   │   "music-theory-blob-ks"             │  ← One per source
   │                                      │
   │   ▶ kind: searchIndex | azureBlob   │
   │           | web | sharepoint | ...  │
   │   ▶ search_index_name (if index)    │
   │   ▶ container (if blob)             │
   └────────────┬─────────────────────────┘
                │
   ┌────────────┴────────────────────────┐
   │       SEARCH INDEX                  │  ← The actual data store
   │   "music-theory-index"              │
   │                                     │
   │   ▶ fields: id, content, embeddings │
   │   ▶ vector_search profile           │
   │   ▶ semantic_search config          │
   └─────────────────────────────────────┘
```

You create them in this order: **index → knowledge source → knowledge base**.

---

## Supported Knowledge Source Types

| Type | Indexed/Remote | Notes |
|---|---|---|
| `searchIndex` | Indexed | Wrap an existing Azure AI Search index |
| `azureBlob` | Indexed | Auto-generates indexer pipeline from a blob container |
| `file` | Indexed | Direct upload of files to Azure AI Search |
| `indexedOneLake` | Indexed | Pulls from Microsoft Fabric lakehouse |
| `indexedSql` (preview) | Indexed | Pulls from Azure SQL |
| `indexedSharePoint` (preview) | Indexed | Pulls from SharePoint |
| `remoteSharePoint` (preview) | Remote | Queries SharePoint at retrieval time |
| `web` | Remote | Real-time grounding from Microsoft Bing |
| `mcpServer` (preview) | Remote | Connect to external MCP server |

**For SpectraVerse → use `searchIndex`** — we'll create one search index from our markdown knowledge base files.

---

## API Versions

| Version | Status | What it gets you |
|---|---|---|
| `2026-04-01` | Generally available | Minimal extractive retrieval, no LLM features |
| `2026-05-01-preview` | Preview | Full features: query planning, answer synthesis, configurable reasoning effort |

**For SpectraVerse → use 2026-05-01-preview** — we want answer synthesis with citations.

---

## Required Azure Resources

1. **Azure AI Search** (Basic tier or higher recommended for managed identity; Free tier works for dev)
   - Region: must be in [agentic retrieval supported regions](https://learn.microsoft.com/en-us/azure/search/search-region-support)
   - Provides: search index + knowledge source + knowledge base + retrieve action

2. **Microsoft Foundry resource + project**
   - Provides: GPT-4o or GPT-4o-mini deployment for query planning and answer synthesis
   - Provides: text-embedding-3-large for vectorization (optional but recommended)

3. **Optional: Azure OpenAI resource** (older path) — Foundry already includes this

---

## Supported LLMs for Knowledge Base

For query planning and answer synthesis. Cost will scale with which one you pick:

| Model | Use case for SpectraVerse |
|---|---|
| `gpt-4o-mini` | **Recommended** — cheap, fast, good enough for our knowledge base |
| `gpt-4.1-mini` | Slightly newer, similar cost |
| `gpt-4o` | Use if accuracy demands it |
| `gpt-5-nano` | Cheapest of the GPT-5 family |
| `gpt-5-mini` | Mid-tier GPT-5 |

---

## Authentication Options

| Method | When to use |
|---|---|
| **Microsoft Entra ID (managed identity / RBAC)** | **Recommended for prod** — keyless, more secure |
| **API keys** | Quick start / local dev — admin key in `api-key` header |

Required RBAC roles:
| Role | Scope | Why |
|---|---|---|
| Search Service Contributor | Search service | Create index/source/base |
| Search Index Data Contributor | Search service | Load documents into index |
| Search Index Data Reader | Search service | Read at query time |
| Cognitive Services User | Foundry resource | Knowledge base calls the LLM |

For local dev with API keys: just grab the admin key from Azure portal. We'll start there and migrate to managed identity later.

---

## Python Package Versions

```
pip install --pre azure-search-documents      # Sprint 3 needs preview package for 2026-05-01-preview
pip install azure-identity                    # for DefaultAzureCredential
pip install azure-ai-projects==2.0.0b1        # optional, only if we use Foundry Agent Service
pip install openai                            # for direct Azure OpenAI calls
pip install python-dotenv
```

---

## Three Retrieval Reasoning Efforts

This controls how much LLM work happens during query planning. Tradeoff is **cost vs relevance**:

| Effort | What happens | Use when |
|---|---|---|
| `minimal` | NO LLM query planning. Single semantic search on each source. Cheapest, fastest. | Simple Q&A, latency-critical |
| `low` (default) | LLM decomposes query into ~3 subqueries. Best balance. | **Recommended for SpectraVerse** |
| `medium` | Iterative search, deeper reasoning. Most expensive. | Complex multi-hop questions |

---

## Two Output Modes

| Mode | What you get | Use case |
|---|---|---|
| `extractedData` | Full search results as JSON string with `ref_id` per chunk | You pass this to your own LLM for downstream answer formulation. **Recommended for SpectraVerse** because we want to use the citations to drive DSP parameters, not just chat. |
| `answerSynthesis` | Pre-formulated natural-language answer with inline citation markers `【0:2†source】` | When you want a chatbot-style answer directly |

For SpectraVerse the agent will:
1. Use **GPT-4o vision** to describe the uploaded image (separate Azure OpenAI call)
2. Send that description as a query to the **knowledge base** with `output_mode=extractedData`
3. Receive grounded music theory data with citations
4. Map that data to audio params for the synthesizer
5. Send citations back to the frontend for display

---

## Pricing Summary

### Azure AI Search (agentic retrieval)
- **Free tier**: monthly token allowance for agentic retrieval — covers all dev + small demos
- **Basic tier**: ~$73/month + per-token after free allowance
- Token-based billing, NOT query-based

### Azure OpenAI (LLM cost)
- `gpt-4o-mini`: $0.15/M input, $0.60/M output tokens
- `gpt-4.1-mini`: similar
- `gpt-4o`: ~$2.50/M input, $10/M output
- `text-embedding-3-large`: $0.13/M tokens

### Cost estimate for SpectraVerse demo
Per generation request:
- GPT-4o vision describing image: ~500 input + 200 output tokens = $0.0002
- Knowledge base retrieval: ~2000 input + 350 output for query planning = $0.0005
- ~150M reranker tokens at $0.022/M = ~$0.003 (covered by free tier first)
- **Total per request: ~$0.001 to $0.003**

100 demo runs ≈ **$0.30**. Easily under our $10 sprint budget.

---

## The Retrieve Action — Exact Request Shape

Once the knowledge base exists, this is what we POST against it:

```python
from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
from azure.search.documents.knowledgebases.models import (
    KnowledgeBaseMessage,
    KnowledgeBaseMessageTextContent,
    KnowledgeBaseRetrievalRequest,
    SearchIndexKnowledgeSourceParams,
)

kb_client = KnowledgeBaseRetrievalClient(
    endpoint="https://your-search.search.windows.net",
    knowledge_base_name="spectraverse-music-theory-kb",
    credential=AzureKeyCredential("admin_key"),
)

request = KnowledgeBaseRetrievalRequest(
    messages=[
        KnowledgeBaseMessage(
            role="assistant",
            content=[KnowledgeBaseMessageTextContent(
                text="You are a music theory expert. Cite sources by ref_id."
            )],
        ),
        KnowledgeBaseMessage(
            role="user",
            content=[KnowledgeBaseMessageTextContent(
                text="A stormy sea at twilight. What musical key, BPM, "
                     "and instruments would best represent this image?"
            )],
        ),
    ],
    knowledge_source_params=[
        SearchIndexKnowledgeSourceParams(
            knowledge_source_name="music-theory-ks",
            include_references=True,
            include_reference_source_data=True,
        )
    ],
)

result = kb_client.retrieve(request)
```

## Response Shape

```json
{
  "response": [
    {
      "role": "assistant",
      "content": [{
        "type": "text",
        "text": "[{\"ref_id\":\"0\",\"title\":\"Music Theory Keys\",\"content\":\"D minor is associated with tragic, dark, serious...\"},{\"ref_id\":\"1\",\"title\":\"Synesthesia\",\"content\":\"Stormy/oceanic imagery maps to deep blue → B♭ minor or E♭ minor...\"}]"
      }]
    }
  ],
  "references": [
    {
      "type": "searchIndex",
      "id": "0",
      "activitySource": 1,
      "docKey": "01_music_theory_keys.md",
      "sourceData": {
        "id": "01_music_theory_keys.md",
        "content": "D minor — tragic, dark, serious, doom...",
        "page_chunk": "Mozart Requiem, Bach Toccata & Fugue..."
      }
    }
  ],
  "activity": [
    { "type": "modelQueryPlanning", "inputTokens": 2302, "outputTokens": 109, "elapsedMs": 2396 },
    { "type": "searchIndex", "knowledgeSourceName": "music-theory-ks", "count": 5, "elapsedMs": 1137 },
    { "type": "agenticReasoning", "reasoningTokens": 103368 }
  ]
}
```

We use:
- `response[0].content[0].text` — JSON string of grounded chunks → parse and feed to GPT-4o for final mapping
- `references[*].docKey` + `sourceData` — for citation display in the UI
- `activity` — for "show your work" inspection panel (judge-friendly)

---

## SpectraVerse Architecture

```
   User uploads image
          │
          ▼
   ┌──────────────────────────┐
   │ FastAPI: /api/generate/  │
   │   image-to-audio-foundry │
   └──────────┬───────────────┘
              │
              ▼
   ┌──────────────────────────┐
   │ FoundryAgent             │
   │ ─────────────────────── │
   │ 1. GPT-4o Vision         │  ← Azure OpenAI direct call
   │    describe(image_b64)   │
   │    → "stormy sea, deep   │
   │       blues, turbulent"  │
   │                          │
   │ 2. Foundry IQ retrieve   │  ← Azure AI Search KB
   │    query(description)    │
   │    → grounded music data │
   │      + citations         │
   │                          │
   │ 3. GPT-4o-mini map       │  ← Azure OpenAI (small)
   │    extract params from   │
   │    grounded data         │
   │    → {key, bpm, ...}     │
   └──────────┬───────────────┘
              │
              ▼
   ┌──────────────────────────┐
   │ DSPSynthesizer           │  ← unchanged from Sprint 2
   │ synthesize(params)       │
   └──────────┬───────────────┘
              │
              ▼
   { audio_b64, citations[], reasoning_steps[] }
              │
              ▼
   Frontend renders:
     ▶ AudioOutputPanel (Sprint 2)
     ▶ CitationPanel (NEW)
     ▶ ReasoningPanel (NEW)
```

---

## Sprint 3 Scaffolding Strategy

Build offline-first with mocks so app stays running:

1. **`backend/app/backend_foundry_agent.py`** — class with three methods:
   - `describe_image(image_bytes) → str` (uses GPT-4o vision OR mock)
   - `query_knowledge(description, style) → dict` (uses Foundry IQ OR returns canned data)
   - `extract_params(grounded_data) → dict` (uses GPT-4o-mini OR rule-based mapping)

2. **`backend/scripts/setup_foundry_kb.py`** — one-time setup script:
   - Reads `data/knowledge_base/*.md`
   - Creates Azure AI Search index
   - Uploads documents
   - Creates knowledge source
   - Creates knowledge base
   - Outputs the names to stdout for `.env` config

3. **`.env` additions**:
   ```
   AZURE_SEARCH_ENDPOINT=https://your-service.search.windows.net
   AZURE_SEARCH_API_KEY=...
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
   AZURE_OPENAI_API_KEY=...
   AZURE_OPENAI_GPT4O_DEPLOYMENT=gpt-4o
   AZURE_OPENAI_GPT4O_MINI_DEPLOYMENT=gpt-4o-mini
   FOUNDRY_KB_NAME=spectraverse-music-theory-kb
   FOUNDRY_KS_NAME=music-theory-ks
   ```

   Without these, `FoundryAgent` falls back to mock mode automatically. **App keeps working today.**

4. **New endpoint**: `/api/generate/image-to-audio-foundry`
   - Same shape as Sprint 2 endpoint but adds `citations[]` and `reasoning_steps[]` to response

5. **New frontend components**:
   - `CitationPanel.tsx` — list of cited sources with hover-to-expand content
   - `ReasoningPanel.tsx` — agent's thought process (vision description → KB query → param extraction)
   - Toggle in `UploadZone.tsx`: "Local DSP" vs "AI-grounded (Foundry)" with cost badge

---

## Why This Wins for the Competition

The judges will see most entries doing one of these:
- Calling GPT-4o for fun → "we used Azure OpenAI"
- Building a chatbot → "we used Foundry Agent Service"

SpectraVerse will be the **only entry** that:
- Uses GPT-4o vision for **non-chat** application (image understanding)
- Uses Foundry IQ for **citation-backed creative decisions** (not Q&A)
- Shows its work — the judge can see WHICH music theory document recommended D minor for a stormy sunset
- Connects three Microsoft services (Search + Foundry + OpenAI) into a real artistic pipeline

That's a **distinctive narrative** judges will remember.

---

## Next Implementation Step

Build the offline-first scaffolding:
1. `FoundryAgent` class with mock fallback
2. `requirements.txt` additions
3. `backend_foundry_agent.py` 
4. `/api/generate/image-to-audio-foundry` endpoint  
5. Frontend `CitationPanel` + `ReasoningPanel`
6. Toggle in UploadZone

App stays functional throughout. When Azure is provisioned, paste env vars → it goes live.
