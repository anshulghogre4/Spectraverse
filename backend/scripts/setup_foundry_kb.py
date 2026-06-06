"""
One-time setup script: provision Azure AI Search + Foundry IQ knowledge base
from local markdown files in data/knowledge_base/.

Run:
    cd backend
    python scripts/setup_foundry_kb.py

Required env vars (in .env or shell):
    AZURE_SEARCH_ENDPOINT   = https://<your-search>.search.windows.net
    AZURE_SEARCH_API_KEY    = <admin key>
    FOUNDRY_KB_NAME         = spectraverse-music-theory-kb (default)
    FOUNDRY_KS_NAME         = music-theory-ks (default)
    FOUNDRY_INDEX_NAME      = music-theory-index (default)

Optional (enables vector search — recommended):
    AZURE_OPENAI_ENDPOINT
    AZURE_OPENAI_API_KEY
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT = text-embedding-3-large
"""

from __future__ import annotations
import os
import sys
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any

# Make sure we can import from backend root when run as script
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "backend" / ".env")
except ImportError:
    pass

# ── Config ────────────────────────────────────────────────────────────────
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
SEARCH_KEY = os.getenv("AZURE_SEARCH_API_KEY", "")
KB_NAME = os.getenv("FOUNDRY_KB_NAME", "spectraverse-music-theory-kb")
KS_NAME = os.getenv("FOUNDRY_KS_NAME", "music-theory-ks")
INDEX_NAME = os.getenv("FOUNDRY_INDEX_NAME", "music-theory-index")

AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AOAI_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
EMBEDDING_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"
)
EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

KB_DIR = ROOT / "data" / "knowledge_base"


# ── Step 1: read knowledge base markdown files into chunked documents ─────

def chunk_markdown(text: str, max_chars: int = 1800) -> List[str]:
    """Split markdown by heading boundaries first, then size-limit each chunk."""
    sections: List[str] = []
    current: List[str] = []
    for line in text.splitlines():
        if line.startswith("## ") and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())

    chunks: List[str] = []
    for section in sections:
        if len(section) <= max_chars:
            chunks.append(section)
        else:
            # split very long sections by paragraphs
            paragraphs = section.split("\n\n")
            buf = ""
            for p in paragraphs:
                if len(buf) + len(p) + 2 > max_chars and buf:
                    chunks.append(buf.strip())
                    buf = p
                else:
                    buf = f"{buf}\n\n{p}" if buf else p
            if buf.strip():
                chunks.append(buf.strip())
    return [c for c in chunks if c]


def load_documents() -> List[Dict[str, Any]]:
    """Load all .md files from data/knowledge_base/ as chunked documents."""
    if not KB_DIR.exists():
        print(f"❌ Knowledge base directory not found: {KB_DIR}")
        sys.exit(1)

    docs: List[Dict[str, Any]] = []
    for md_file in sorted(KB_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        chunks = chunk_markdown(text)
        for i, chunk in enumerate(chunks):
            doc_id = hashlib.md5(
                f"{md_file.name}:{i}".encode()
            ).hexdigest()
            docs.append({
                "id": doc_id,
                "source_file": md_file.name,
                "chunk_index": i,
                "content": chunk,
            })
        print(f"  ✓ {md_file.name}: {len(chunks)} chunks")
    return docs


# ── Step 2: create the search index ───────────────────────────────────────

def create_index() -> None:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchField, SearchIndex, SemanticConfiguration, SemanticField,
        SemanticPrioritizedFields, SemanticSearch,
    )

    fields = [
        SearchField(name="id", type="Edm.String", key=True, filterable=True),
        SearchField(name="source_file", type="Edm.String", filterable=True, facetable=True),
        SearchField(name="chunk_index", type="Edm.Int32", filterable=True, sortable=True),
        SearchField(name="content", type="Edm.String", searchable=True),
    ]

    vector_search = None
    vectorizers_extra: List[Any] = []
    if AOAI_ENDPOINT and AOAI_KEY:
        from azure.search.documents.indexes.models import (
            AzureOpenAIVectorizer, AzureOpenAIVectorizerParameters,
            HnswAlgorithmConfiguration, VectorSearch, VectorSearchProfile,
        )
        fields.append(
            SearchField(
                name="content_vector",
                type="Collection(Edm.Single)",
                searchable=True,
                stored=False,
                vector_search_dimensions=3072,
                vector_search_profile_name="hnsw_text_3_large",
            )
        )
        vector_search = VectorSearch(
            profiles=[
                VectorSearchProfile(
                    name="hnsw_text_3_large",
                    algorithm_configuration_name="alg",
                    vectorizer_name="azure_openai_text_3_large",
                )
            ],
            algorithms=[HnswAlgorithmConfiguration(name="alg")],
            vectorizers=[
                AzureOpenAIVectorizer(
                    vectorizer_name="azure_openai_text_3_large",
                    parameters=AzureOpenAIVectorizerParameters(
                        resource_url=AOAI_ENDPOINT,
                        api_key=AOAI_KEY,
                        deployment_name=EMBEDDING_DEPLOYMENT,
                        model_name=EMBEDDING_MODEL,
                    ),
                )
            ],
        )

    semantic = SemanticSearch(
        default_configuration_name="semantic_config",
        configurations=[
            SemanticConfiguration(
                name="semantic_config",
                prioritized_fields=SemanticPrioritizedFields(
                    content_fields=[SemanticField(field_name="content")],
                ),
            )
        ],
    )

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic,
    )

    client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT, credential=AzureKeyCredential(SEARCH_KEY)
    )
    client.create_or_update_index(index)
    print(f"✅ Index '{INDEX_NAME}' created/updated"
          f" ({'with vector search' if vector_search else 'text-only'})")


# ── Step 3: upload chunked documents to the index ─────────────────────────

def upload_documents(docs: List[Dict[str, Any]]) -> None:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchIndexingBufferedSender

    # If we have vector search, also generate embeddings client-side
    # (the integrated vectoriser will handle queries; uploads need vectors too
    #  unless the index uses an indexer pipeline)
    embeddings_available = bool(AOAI_ENDPOINT and AOAI_KEY)
    if embeddings_available:
        try:
            from openai import AzureOpenAI
            aoai = AzureOpenAI(
                azure_endpoint=AOAI_ENDPOINT,
                api_key=AOAI_KEY,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            )
            for doc in docs:
                resp = aoai.embeddings.create(
                    model=EMBEDDING_DEPLOYMENT, input=doc["content"]
                )
                doc["content_vector"] = resp.data[0].embedding
            print(f"  ✓ Generated {len(docs)} embeddings")
        except Exception as e:
            print(f"  ⚠ Embedding generation failed ({e}) — uploading text-only")
            for doc in docs:
                doc.pop("content_vector", None)

    with SearchIndexingBufferedSender(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY),
    ) as sender:
        sender.upload_documents(documents=docs)
    print(f"✅ Uploaded {len(docs)} document chunks to '{INDEX_NAME}'")


# ── Step 4: create knowledge source pointing at the index ─────────────────

def create_knowledge_source() -> None:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndexFieldReference,
        SearchIndexKnowledgeSource,
        SearchIndexKnowledgeSourceParameters,
    )

    ks = SearchIndexKnowledgeSource(
        name=KS_NAME,
        description="SpectraVerse music theory + synesthesia knowledge",
        search_index_parameters=SearchIndexKnowledgeSourceParameters(
            search_index_name=INDEX_NAME,
            semantic_configuration_name="semantic_config",
            source_data_fields=[
                SearchIndexFieldReference(name="id"),
                SearchIndexFieldReference(name="source_file"),
                SearchIndexFieldReference(name="content"),
            ],
        ),
    )

    client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT, credential=AzureKeyCredential(SEARCH_KEY)
    )
    client.create_or_update_knowledge_source(knowledge_source=ks)
    print(f"✅ Knowledge source '{KS_NAME}' created/updated")


# ── Step 5: create knowledge base ─────────────────────────────────────────

def create_knowledge_base() -> None:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        KnowledgeBase, KnowledgeSourceReference,
    )

    kb = KnowledgeBase(
        name=KB_NAME,
        description="SpectraVerse music theory knowledge base — used by FoundryAgent",
        knowledge_sources=[KnowledgeSourceReference(name=KS_NAME)],
        output_mode="extractedData",
    )

    client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT, credential=AzureKeyCredential(SEARCH_KEY)
    )
    client.create_or_update_knowledge_base(knowledge_base=kb)
    print(f"✅ Knowledge base '{KB_NAME}' created/updated")


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    if not SEARCH_ENDPOINT or not SEARCH_KEY:
        print("❌ Missing required env vars:")
        print("   AZURE_SEARCH_ENDPOINT — your search service URL")
        print("   AZURE_SEARCH_API_KEY  — admin key from Azure portal")
        print("\nSee docs/AZURE_SETUP.md for full instructions.")
        sys.exit(1)

    print(f"🔧 Setting up Foundry IQ for SpectraVerse")
    print(f"   Search endpoint: {SEARCH_ENDPOINT}")
    print(f"   Knowledge base:  {KB_NAME}")
    print(f"   Knowledge source: {KS_NAME}")
    print(f"   Index:           {INDEX_NAME}")
    print()

    print("📂 Loading knowledge base markdown files…")
    docs = load_documents()
    if not docs:
        print("❌ No documents found.")
        sys.exit(1)
    print(f"   → {len(docs)} total chunks across {len(set(d['source_file'] for d in docs))} files")
    print()

    print("🏗  Creating search index…")
    create_index()

    print("📤 Uploading documents…")
    upload_documents(docs)

    print("🔗 Creating knowledge source…")
    create_knowledge_source()

    print("🧠 Creating knowledge base…")
    create_knowledge_base()

    print()
    print("🎉 Setup complete!")
    print(f"   Add these to your .env if not already there:")
    print(f"   FOUNDRY_KB_NAME={KB_NAME}")
    print(f"   FOUNDRY_KS_NAME={KS_NAME}")
    print(f"   AZURE_SEARCH_ENDPOINT={SEARCH_ENDPOINT}")
    print(f"   AZURE_SEARCH_API_KEY={'<your admin key>' if SEARCH_KEY else 'MISSING'}")


if __name__ == "__main__":
    main()
