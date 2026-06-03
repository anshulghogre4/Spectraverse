# SpectraVerse: Directory Structure & File Organization Guide

## 🎯 Quick Summary

You have **25 component files** sitting in the repository root. We need to organize them into a proper project structure. Since the create tool requires parent directories to exist first, here's a **manual step-by-step approach** for Windows.

---

## 📁 **STEP 1: Create Folder Structure (Windows)**

### Using File Explorer:

```
1. Go to f:\Preparation\Microsoft_Agents_League
2. Create folders:
   - frontend
   - frontend\app
   - frontend\app\components
   - frontend\app\components\Upload
   - frontend\app\components\Spectrogram
   - frontend\public

   - backend
   - backend\app
   - backend\app\services
   - backend\app\routes
   - backend\app\utils
```

### Using PowerShell/CMD:

```powershell
# Frontend directories
mkdir frontend\app\components\Upload
mkdir frontend\app\components\Spectrogram
mkdir frontend\public

# Backend directories
mkdir backend\app\services
mkdir backend\app\routes
mkdir backend\app\utils
```

---

## 📋 **STEP 2: File Organization Map**

After folders exist, copy/move files according to this table:

| **Root File**                       | **Move To**                           | **New Name**                |
| ----------------------------------- | ------------------------------------- | --------------------------- |
| frontend_page.tsx                   | frontend\app\                         | page.tsx                    |
| frontend_UploadZone.tsx             | frontend\app\components\Upload\       | UploadZone.tsx              |
| frontend_SpectrogramVisualizer.tsx  | frontend\app\components\Spectrogram\  | SpectrogramVisualizer.tsx   |
| frontend_package.json               | frontend\                             | package.json                |
| backend_main_v2.py                  | backend\app\                          | main.py                     |
| backend_vision_analyzer.py          | backend\app\services\                 | vision_analyzer.py          |
| backend_semantic_mapper.py          | backend\app\services\                 | semantic_mapper.py          |
| backend_image_to_audio_pipeline.py  | backend\app\services\                 | image_to_audio_pipeline.py  |
| backend_audio_to_visual_pipeline.py | backend\app\services\                 | audio_to_visual_pipeline.py |
| backend_audio_analyzer.py           | backend\app\services\                 | audio_analyzer.py           |
| backend_dsp_synthesizer.py          | backend\app\services\                 | dsp_synthesizer.py          |
| backend_requirements.txt            | backend\                              | requirements.txt            |
| semantic_mappings.json              | . (root)                              | semantic_mappings.json      |

---

## ✨ **STEP 3: Final Structure**

After organization, you'll have:

```
f:\Preparation\Microsoft_Agents_League\
├── frontend/
│   ├── app/
│   │   ├── page.tsx                    ← main UI
│   │   ├── layout.tsx                  (create new)
│   │   ├── globals.css                 (create new)
│   │   └── components/
│   │       ├── Upload/
│   │       │   └── UploadZone.tsx
│   │       └── Spectrogram/
│   │           └── SpectrogramVisualizer.tsx
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json                   (create new)
│   ├── tailwind.config.ts              (create new)
│   ├── postcss.config.js               (create new)
│   ├── next.config.js                  (create new)
│   └── .env.local.example              (create new)
│
├── backend/
│   ├── app/
│   │   ├── __init__.py                 (create new, empty)
│   │   ├── main.py                     ← FastAPI router
│   │   ├── services/
│   │   │   ├── __init__.py             (create new, empty)
│   │   │   ├── vision_analyzer.py
│   │   │   ├── semantic_mapper.py
│   │   │   ├── image_to_audio_pipeline.py
│   │   │   ├── audio_to_visual_pipeline.py
│   │   │   ├── audio_analyzer.py
│   │   │   └── dsp_synthesizer.py
│   │   ├── routes/
│   │   │   └── __init__.py             (create new, empty)
│   │   └── utils/
│   │       └── __init__.py             (create new, empty)
│   ├── requirements.txt
│   ├── .env.local.example              (create new)
│   └── venv/                           (after pip install)
│
├── semantic_mappings.json              ← stays in root
├── Dockerfile.backend
├── Dockerfile.frontend
├── .gitignore                          (create new)
├── docker-compose.yml                  (optional, create new)
├── README.md
├── SETUP.md
├── COMPLETE_GUIDE.md
├── BUILD_STATUS.md
├── QUICK_START.md
└── [other docs...]
```

---

## 🔧 **STEP 4: Create New Config Files**

Once folder structure exists, create these new files:

### Frontend Config Files

**frontend/app/layout.tsx**

```tsx
export const metadata = {
  title: "SpectraVerse",
  description: "Hear images. Visualize music.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-black text-white">{children}</body>
    </html>
  );
}
```

**frontend/app/globals.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**frontend/tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "strict": true,
    "jsx": "preserve",
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

**frontend/tailwind.config.ts**

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
export default config;
```

**frontend/postcss.config.js**

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

**frontend/next.config.js**

```js
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
};
module.exports = nextConfig;
```

### Backend Config Files

**backend/app/**init**.py** (empty, just creates package)

**backend/app/services/**init**.py** (empty)

**backend/app/routes/**init**.py** (empty)

**backend/app/utils/**init**.py** (empty)

### Root Config

**.gitignore**

```
node_modules/
__pycache__/
*.pyc
.env.local
.next/
build/
dist/
venv/
.venv
*.egg-info/
.DS_Store
```

---

## 🚀 **STEP 5: Install & Run**

After files are organized:

```bash
# Terminal 1: Frontend
cd frontend
npm install
npm run dev

# Terminal 2: Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

---

## 📊 **Current Status**

- ✅ 25 component files generated (logic complete)
- ✅ Documentation complete (SETUP.md, COMPLETE_GUIDE.md, etc.)
- ✅ Database tracking active (changelog, todos, dependencies)
- ⏳ **NEXT**: Create folder structure + copy files
- ⏳ **THEN**: npm install + pip install
- ⏳ **FINALLY**: npm run dev + uvicorn (app should run!)

---

## 🎯 **TL;DR - Quick Action Items**

1. **Create directories** (PowerShell/CMD or File Explorer)
2. **Move files** to proper locations (see table above)
3. **Create empty **init**.py files** in backend folders
4. **Create config files** (layout.tsx, tsconfig.json, etc.)
5. **Run**: `npm install` + `pip install -r requirements.txt`
6. **Start**: `npm run dev` + `uvicorn app.main:app --reload`

Once complete, **SpectraVerse is running!** 🎉

---

## 💡 Next Steps After This

- [ ] Test Image→Audio endpoint: POST `/api/generate/image-to-audio`
- [ ] Test Audio→Visual pipeline (Sprint 4)
- [ ] Add Azure Vision API credentials
- [ ] Add Redis cache URL
- [ ] Set up Docker images
- [ ] Deploy to Azure Container Apps
