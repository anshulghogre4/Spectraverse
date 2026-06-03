# SpectraVerse Local Setup Guide

**Generated**: 2026-05-29 03:19 UTC

---

## Quick Start (5 minutes)

### Prerequisites

- Node.js 18+
- Python 3.11+
- Docker (optional)
- Azure CLI (for deployment)

---

## Step 1: Clone & Initialize

```bash
cd f:\Preparation\Microsoft_Agents_League
git init
git config user.name "SpectraVerse Team"
git config user.email "team@spectraverse.dev"

# Create folder structure
mkdir -p spectraverse/{frontend,backend,infrastructure,docs}
cd spectraverse
```

---

## Step 2: Frontend (Next.js)

```bash
cd frontend

# Create Next.js app (TypeScript + TailwindCSS)
npx create-next-app@latest . --typescript --tailwind --eslint --no-git --import-alias '@/*'

# Install additional deps
npm install framer-motion three @react-three/fiber @react-three/drei web-audio-api

# Create directories
mkdir -p src/components/{Upload,Spectrogram,Player}
mkdir -p src/lib/{api,utils}
mkdir -p src/hooks
mkdir -p public/shaders

# Done!
cd ..
```

---

## Step 3: Backend (FastAPI)

```bash
cd backend

# Create Python venv
py -3.13 -m venv venv
source venv/Scripts/activate  # Windows: .\venv\Scripts\activate

# Recommended Python versions:
# - Windows: Python 3.12 or 3.13 is supported for the backend
# - Linux/macOS: Python 3.11+ is supported
# If you have multiple Python versions installed, use the py launcher above.
# This repo includes a .python-version pin at the root for pyenv and editor integrations.

# Create requirements.txt
cat > requirements.txt << EOF
fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6
librosa==0.10.0
torchaudio==2.1.0
numpy==2.4.6
python-dotenv==1.0.0
aiofiles==23.2.1
pydantic==2.4.2
azure-storage-blob==12.18.0
redis==5.0.0
EOF

python -m pip install --upgrade pip setuptools wheel
pip install --prefer-binary -r requirements.txt

# Create app structure
mkdir -p app/{routes,models,services,utils}

# Done!
cd ..
```

### Windows build tool note

If dependency install fails on Windows with a message about `link.exe`, install the Visual Studio Build Tools:

```powershell
winget install --id Microsoft.VisualStudio.2022.BuildTools -e
```

Then retry the install.

---

## Step 4: Create Core Files

### Backend: `backend/app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SpectraVerse API", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

@app.post("/api/analyze-image")
async def analyze_image(file):
    # TODO: Implement
    return {"status": "placeholder"}

@app.post("/api/analyze-audio")
async def analyze_audio(file):
    # TODO: Implement
    return {"status": "placeholder"}
```

### Frontend: `frontend/app/page.tsx`

```tsx
"use client";

import { useState } from "react";

export default function Home() {
  const [mode, setMode] = useState<"classic" | "creative">("classic");

  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-900 to-black p-8">
      <h1 className="text-5xl font-bold text-white mb-4">SpectraVerse</h1>
      <p className="text-xl text-gray-300 mb-8">
        Hear images. Visualize music.
      </p>

      <div className="flex gap-4 mb-12">
        <button
          onClick={() => setMode("classic")}
          className={`px-6 py-3 rounded-lg font-semibold transition ${
            mode === "classic"
              ? "bg-blue-500 text-white"
              : "bg-gray-700 text-gray-300"
          }`}
        >
          Classic Mode
        </button>
        <button
          onClick={() => setMode("creative")}
          className={`px-6 py-3 rounded-lg font-semibold transition ${
            mode === "creative"
              ? "bg-purple-500 text-white"
              : "bg-gray-700 text-gray-300"
          }`}
        >
          Creative Mode
        </button>
      </div>

      <div className="grid md:grid-cols-2 gap-8">
        {/* Image Upload */}
        <div className="bg-gray-800 rounded-lg p-8 border-2 border-dashed border-gray-600 hover:border-blue-400 cursor-pointer transition">
          <h2 className="text-2xl font-bold text-white mb-4">
            📸 Image to Audio
          </h2>
          <p className="text-gray-400">
            Drag & drop an image or click to upload
          </p>
        </div>

        {/* Audio Upload */}
        <div className="bg-gray-800 rounded-lg p-8 border-2 border-dashed border-gray-600 hover:border-purple-400 cursor-pointer transition">
          <h2 className="text-2xl font-bold text-white mb-4">
            🎵 Audio to Visual
          </h2>
          <p className="text-gray-400">Drag & drop audio or click to upload</p>
        </div>
      </div>
    </main>
  );
}
```

### Docker: `docker-compose.yml`

```yaml
version: "3.9"
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - AZURE_BLOB_ACCOUNT=${AZURE_BLOB_ACCOUNT}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Step 5: Start Development

```bash
# Terminal 1: Backend
cd backend
source venv/Scripts/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev

# Browser: http://localhost:3000
```

---

## Step 6: Git Commit

```bash
git add .
git commit -m "Sprint 1: Project scaffold - Next.js + FastAPI + Docker setup

- Initialize Next.js with TailwindCSS and TypeScript
- Set up FastAPI backend with CORS and health check
- Docker Compose for local development
- Basic UI with mode selection

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Environment Variables (`.env`)

```
# Azure
AZURE_BLOB_ACCOUNT=spectraverse
AZURE_BLOB_KEY=your_key_here
AZURE_VISION_API_KEY=your_key_here

# Redis
REDIS_URL=redis://localhost:6379

# API
API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Next Steps (After Setup)

1. **Sprint 1.4**: Build upload components with drag-drop
2. **Sprint 1.5**: Define semantic mapping rules (JSON)
3. **Sprint 2**: Integrate librosa for audio analysis
4. **Sprint 3**: Azure Vision API integration

---

**Total Setup Time**: ~15-20 minutes  
**Status**: 🟢 Ready to build
