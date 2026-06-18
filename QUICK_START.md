# SpectraVerse — Quick Start

## Live demo

https://purple-glacier-02aebbb0f.7.azurestaticapps.net

> Backend is on scale-to-zero — first request after idle may take 5–10 s.

---

## Run locally (3 steps)

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

You need at least one LLM key in `backend/.env`. Minimum:

```
GEMINI_API_KEY=your_key_here   # free tier, no card required
```

Full variable list: see [README.md](README.md#running-locally).

### 2. Frontend

Create `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

### 3. Verify

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"...","service":"SpectraVerse API",...}
```

---

## Environment variables

| File | Variable | Purpose |
|------|----------|---------|
| `backend/.env` | `OPENAI_API_KEY` | GPT-4o (vision-capable) |
| `backend/.env` | `GEMINI_API_KEY` | Gemini 2.5 Flash — free, vision-capable |
| `backend/.env` | `GROQ_API_KEY` | Llama 4 Scout — free, fast |
| `backend/.env` | `AZURE_SEARCH_ENDPOINT` | Foundry IQ citations (optional) |
| `backend/.env` | `AZURE_SEARCH_API_KEY` | Azure AI Search auth |
| `backend/.env` | `FOUNDRY_KB_NAME` | Knowledge base name |
| `frontend/.env.local` | `NEXT_PUBLIC_API_URL` | Local backend URL (not committed) |
