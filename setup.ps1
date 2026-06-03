# SpectraVerse Windows setup helper (PowerShell)
param()

Write-Host "Setting up SpectraVerse local environment..."

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

$pythonVersion = (& python --version 2>&1)
$pythonCmd = "python"
$pythonArgs = ""
$usePy312 = $false
if ($pythonVersion -match 'Python (\d+)\.(\d+)\.(\d+)') {
    $major = [int]$matches[1]
    $minor = [int]$matches[2]
    Write-Host "Detected Python version: $pythonVersion"
    if ($major -ne 3 -or $minor -lt 11 -or $minor -gt 13) {
        Write-Host "Python interpreter is not in the supported range. Checking for py -3.13 or py -3.12..."
        try {
            $pythonVersion313 = (& py -3.13 --version 2>&1)
        } catch {
            $pythonVersion313 = $null
        }
        try {
            $pythonVersion312 = (& py -3.12 --version 2>&1)
        } catch {
            $pythonVersion312 = $null
        }
        if ($pythonVersion313 -and $pythonVersion313 -match 'Python 3\.13') {
            Write-Host "Found Python 3.13 via py -3.13. Using that interpreter."
            $usePy312 = $true
            $pythonCmd = "py"
            $pythonArgs = "-3.13"
            $pythonVersion = $pythonVersion313
        } elseif ($pythonVersion312 -and $pythonVersion312 -match 'Python 3\.12') {
            Write-Host "Found Python 3.12 via py -3.12. Using that interpreter."
            $usePy312 = $true
            $pythonCmd = "py"
            $pythonArgs = "-3.12"
            $pythonVersion = $pythonVersion312
        } else {
            Write-Error "This repository supports Windows Python 3.12 or 3.13 for the backend."
            Write-Error "Install Python 3.12 or 3.13 and retry, or install Build Tools if you are using an unsupported version."
            exit 1
        }
    }
    if ($minor -eq 11) {
        Write-Warning "Python 3.11 is supported as a fallback, but 3.12 or 3.13 is recommended for this repo."
    }
} else {
    Write-Warning "Unable to determine Python version. Ensure Python is on PATH."
}

# Create Python venv
if (-not (Test-Path .\venv)) {
    if ($usePy312) {
        & $pythonCmd $pythonArgs -m venv .\venv
    } else {
        & python -m venv .\venv
    }
}
Write-Host "Activating venv..."
. .\venv\Scripts\Activate.ps1

Write-Host "Installing backend core dependencies..."
if ($usePy312) {
    & $pythonCmd $pythonArgs -m pip install --upgrade pip setuptools wheel
    & $pythonCmd $pythonArgs -m pip install --prefer-binary -r backend\requirements.txt
} else {
    python -m pip install --upgrade pip setuptools wheel
    pip install --prefer-binary -r backend\requirements.txt
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backend dependency install failed."
    Write-Error "If you are on Windows, install Visual Studio Build Tools (C++ toolchain) or use Python 3.11/3.12."
    Write-Error "Example: winget install --id Microsoft.VisualStudio.2022.BuildTools -e"
    exit $LASTEXITCODE
}

Write-Host "Frontend: install dependencies (run in separate terminal if desired)"
if (Test-Path frontend\package.json) {
    Write-Host "Running npm ci in frontend..."
    Push-Location frontend
    npm ci
    Pop-Location
}

Write-Host "Done. Start backend: uvicorn backend.app.main:app --reload --port 8000"
Write-Host "Start frontend: cd frontend; npm run dev"
