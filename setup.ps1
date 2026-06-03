# SpectraVerse Windows setup helper (PowerShell)
# Usage: .\setup.ps1
param()

Write-Host "Setting up SpectraVerse local environment..."

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

# --- Detect Python version ---
$pythonVersion = (& python --version 2>&1)
$pythonCmd = "python"
$pythonArgs = ""
$usePyLauncher = $false

if ($pythonVersion -match 'Python (\d+)\.(\d+)\.(\d+)') {
    $major = [int]$matches[1]
    $minor = [int]$matches[2]
    Write-Host "Detected: $pythonVersion"
    if ($major -ne 3 -or $minor -lt 11 -or $minor -gt 13) {
        Write-Host "Checking for py -3.13 or py -3.12..."
        $v313 = try { & py -3.13 --version 2>&1 } catch { $null }
        $v312 = try { & py -3.12 --version 2>&1 } catch { $null }
        if ($v313 -match 'Python 3\.13') {
            Write-Host "Using py -3.13"
            $usePyLauncher = $true; $pythonCmd = "py"; $pythonArgs = "-3.13"
        } elseif ($v312 -match 'Python 3\.12') {
            Write-Host "Using py -3.12"
            $usePyLauncher = $true; $pythonCmd = "py"; $pythonArgs = "-3.12"
        } else {
            Write-Error "Requires Python 3.12 or 3.13. Install from python.org and retry."
            exit 1
        }
    }
} else {
    Write-Warning "Could not detect Python version — ensure python is on PATH."
}

# --- Create .venv (project convention: dot-prefixed) ---
if (-not (Test-Path .\.venv)) {
    Write-Host "Creating .venv..."
    if ($usePyLauncher) {
        & $pythonCmd $pythonArgs -m venv .\.venv
    } else {
        & python -m venv .\.venv
    }
}

Write-Host "Activating .venv..."
. .\.venv\Scripts\Activate.ps1

# --- Install backend dependencies ---
Write-Host "Installing backend dependencies (--prefer-binary avoids MSVC compilation)..."
python -m pip install --upgrade pip setuptools wheel --quiet
pip install --prefer-binary -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backend install failed. Try: winget install --id Microsoft.VisualStudio.2022.BuildTools -e"
    exit $LASTEXITCODE
}

# --- Install frontend dependencies ---
if (Test-Path frontend\package.json) {
    Write-Host "Installing frontend dependencies..."
    Push-Location frontend
    npm install
    Pop-Location
}

Write-Host ""
Write-Host "Setup complete! Start the app:"
Write-Host "  Terminal 1 (backend):  cd backend; uvicorn app.main:app --reload --port 8000"
Write-Host "  Terminal 2 (frontend): cd frontend; npm run dev"
Write-Host "  Browser: http://localhost:3000"
