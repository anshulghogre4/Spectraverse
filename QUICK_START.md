# SpectraVerse Quick Start Guide

**Status**: All code generated, now organize into project structure

---

## 📁 Current Status

You have **25 component files** in the repository root that need to be organized into:

- `frontend/` folder (Next.js project)
- `backend/` folder (FastAPI project)

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Create Project Structure

**Option A: Using Python (Recommended)**

```bash
cd Microsoft_Agents_League
python create_structure.py
```

**Option B: Using Bash**

```bash
bash create_structure.sh
```

**Option C: Manual (Windows - use File Explorer or PowerShell)**

```powershell
# Create directories
mkdir frontend/app/components/Upload
mkdir frontend/app/components/Spectrogram
mkdir backend/app/services
mkdir backend/app/utils

# Create Python init files
New-Item -Path backend/app/__init__.py
New-Item -Path backend/app/services/__init__.py
```

### Step 2: Copy Component Files

After structure is created, organize these files:

**Frontend Components** → `frontend/app/`

```
frontend_page.tsx → frontend/app/page.tsx
frontend_SpectrogramVisualizer.tsx → frontend/app/components/Spectrogram/SpectrogramVisualizer.tsx
frontend_UploadZone.tsx → frontend/app/components/Upload/UploadZone.tsx
frontend_package.json → frontend/package.json
```

**Backend Services** → `backend/app/services/`

```
backend_main_v2.py → backend/app/main.py (main router)
backend_vision_analyzer.py → backend/app/services/vision_analyzer.py
backend_semantic_mapper.py → backend/app/services/semantic_mapper.py
backend_image_to_audio_pipeline.py → backend/app/services/image_to_audio_pipeline.py
backend_audio_to_visual_pipeline.py → backend/app/services/audio_to_visual_pipeline.py
backend_audio_analyzer.py → backend/app/services/audio_analyzer.py
backend_dsp_synthesizer.py → backend/app/services/dsp_synthesizer.py
backend_requirements.txt → backend/requirements.txt
```

**Frontend Config** → `frontend/`

```
frontend_package.json → frontend/package.json
```

**Shared Assets** → Repository Root

```
semantic_mappings.json → .
```

---

## 📂 Final Structure

```
Microsoft_Agents_League/
│
├─ frontend/                          # Next.js App Router
│  ├─ app/
│  │  ├─ page.tsx                     (main UI)
│  │  ├─ layout.tsx                   (root layout)
│  │  ├─ globals.css                  (tailwind imports)
│  │  ├─ components/
│  │  │  ├─ Upload/
│  │  │  │  └─ UploadZone.tsx
│  │  │  └─ Spectrogram/
│  │  │     └─ SpectrogramVisualizer.tsx
│  │  └─ ...
│  ├─ public/
│  ├─ package.json
│  ├─ tsconfig.json
│  ├─ tailwind.config.ts
│  ├─ postcss.config.js
│  └─ next.config.js
│
├─ backend/                           # FastAPI
│  ├─ app/
│  │  ├─ main.py                      (FastAPI routes)
│  │  ├─ __init__.py
│  │  ├─ services/
│  │  │  ├─ __init__.py
│  │  │  ├─ vision_analyzer.py
│  │  │  ├─ semantic_mapper.py
│  │  │  ├─ image_to_audio_pipeline.py
│  │  │  ├─ audio_to_visual_pipeline.py
│  │  │  ├─ audio_analyzer.py
│  │  │  └─ dsp_synthesizer.py
│  │  ├─ routes/
│  │  └─ utils/
│  ├─ requirements.txt
│  └─ venv/                           (after pip install)
│
├─ semantic_mappings.json             # Intelligence core
├─ Dockerfile.backend
├─ Dockerfile.frontend
├─ docker-compose.yml
├─ .gitignore
├─ README.md
├─ SETUP.md
├─ COMPLETE_GUIDE.md
└─ [Documentation files]

```

---

## ⚡ 3-Step Execution Plan

### 1️⃣ **Create Structure** (1 minute)

```bash
python create_structure.py
# or: bash create_structure.sh
```

### 2️⃣ **Copy Files** (2 minutes)

```bash
# Frontend
cp frontend_page.tsx frontend/app/
cp frontend_UploadZone.tsx frontend/app/components/Upload/
cp frontend_SpectrogramVisualizer.tsx frontend/app/components/Spectrogram/
cp frontend_package.json frontend/

# Backend
cp backend_main_v2.py backend/app/main.py
cp backend_vision_analyzer.py backend/app/services/
cp backend_semantic_mapper.py backend/app/services/
cp backend_image_to_audio_pipeline.py backend/app/services/
cp backend_audio_to_visual_pipeline.py backend/app/services/
cp backend_audio_analyzer.py backend/app/services/
cp backend_dsp_synthesizer.py backend/app/services/
cp backend_requirements.txt backend/

# Config
cp semantic_mappings.json .
```

### 3️⃣ **Install Dependencies & Run** (2 minutes)

```bash
# Terminal 1: Frontend
cd frontend
npm install
npm run dev

# Terminal 2: Backend
cd backend
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Browser: http://localhost:3000
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

---

## ✅ Verification

### Frontend ✓

```bash
curl http://localhost:3000
# Should load the SpectraVerse UI
```

### Backend Health

```bash
curl http://localhost:8000/health
# {
#   "status": "ok",
#   "version": "0.2.0",
#   "service": "SpectraVerse API"
# }
```

### Image→Audio Test

```bash
curl -X POST -F "file=@test.jpg" \
  "http://localhost:8000/api/generate/image-to-audio?mode=classic"

# Returns:
# {
#   "job_id": "abc12345",
#   "status": "success",
#   "result": {
#     "audio_array": [...],
#     "image_features": {...},
#     "audio_params": {...}
#   }
# }
```

---

## 🔗 File Mapping Reference

| Root File                           | Destination                                                   | Purpose            |
| ----------------------------------- | ------------------------------------------------------------- | ------------------ |
| frontend_page.tsx                   | frontend/app/page.tsx                                         | Main UI component  |
| frontend_UploadZone.tsx             | frontend/app/components/Upload/UploadZone.tsx                 | Upload component   |
| frontend_SpectrogramVisualizer.tsx  | frontend/app/components/Spectrogram/SpectrogramVisualizer.tsx | Real-time viz      |
| frontend_package.json               | frontend/package.json                                         | Dependencies       |
| backend_main_v2.py                  | backend/app/main.py                                           | FastAPI routes     |
| backend_vision_analyzer.py          | backend/app/services/                                         | Vision analysis    |
| backend_semantic_mapper.py          | backend/app/services/                                         | Semantic mapping   |
| backend_image_to_audio_pipeline.py  | backend/app/services/                                         | Image→Audio        |
| backend_audio_to_visual_pipeline.py | backend/app/services/                                         | Audio→Visual       |
| backend_audio_analyzer.py           | backend/app/services/                                         | Audio analysis     |
| backend_dsp_synthesizer.py          | backend/app/services/                                         | DSP synthesis      |
| backend_requirements.txt            | backend/requirements.txt                                      | Python packages    |
| semantic_mappings.json              | . (root)                                                      | Intelligence rules |

---

## 🐛 Troubleshooting

### "Module not found" error in backend

```bash
# Make sure __init__.py files exist
touch backend/app/__init__.py
touch backend/app/services/__init__.py
```

### Frontend won't start

```bash
# Clear cache and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Port already in use

```bash
# Use different port
uvicorn app.main:app --port 8001
# or
npm run dev -- -p 3001
```

---

## ✨ Once Structure is Ready

Run the **complete setup** from SETUP.md:

```bash
# All steps already prepared - just follow the guide
cat SETUP.md
```

---

**Status**: Components ready → Structure created → Dependencies installed → App running 🎉

**Time to First Run**: ~5 minutes (structure) + ~5 minutes (npm/pip) = **10 minutes total**
