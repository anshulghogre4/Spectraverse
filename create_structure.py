#!/usr/bin/env python3
"""
Create SpectraVerse project directory structure
Run this script to initialize all folders and files
"""

import os
import json
from pathlib import Path

def create_project_structure():
    """Create complete Next.js + FastAPI project structure"""
    
    base_path = Path(".")
    
    # Frontend directories
    frontend_dirs = [
        "frontend/app",
        "frontend/app/components/Upload",
        "frontend/app/components/Spectrogram",
        "frontend/public",
        "frontend/public/shaders",
    ]
    
    # Backend directories
    backend_dirs = [
        "backend",
        "backend/app",
        "backend/app/routes",
        "backend/app/services",
        "backend/app/utils",
    ]
    
    # Create all directories
    for dir_path in frontend_dirs + backend_dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"✓ Created: {dir_path}")
    
    # Create __init__.py files for Python packages
    init_files = [
        "backend/app/__init__.py",
        "backend/app/routes/__init__.py",
        "backend/app/services/__init__.py",
        "backend/app/utils/__init__.py",
    ]
    
    for init_file in init_files:
        Path(init_file).touch()
        print(f"✓ Created: {init_file}")
    
    print("\n✅ Project structure created successfully!")
    print("\nNext steps:")
    print("1. cd frontend && npm install")
    print("2. cd backend && python -m venv venv && source venv/Scripts/activate && pip install -r requirements.txt")
    print("3. npm run dev (frontend)")
    print("4. uvicorn app.main_v2:app --reload (backend)")

if __name__ == "__main__":
    create_project_structure()
