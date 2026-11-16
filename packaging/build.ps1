# Build the Windows exe and the installer wizard (nothing is released or uploaded).
# Usage (from anywhere):  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
# Build output goes to %APPDATA%\Orbit Simulator\build (dist, work, installer) — not into the repository folder.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$build = Join-Path $env:APPDATA 'Orbit Simulator\build'
New-Item -ItemType Directory -Force "$build\dist", "$build\work", "$build\installer" | Out-Null
python -m pip install -r requirements-dev.txt
python packaging\make_icon.py
python packaging\make_wizard_images.py
python -m PyInstaller packaging\mathkit.spec --noconfirm --distpath "$build\dist" --workpath "$build\work"
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "C:\Program Files (x86)\Inno Setup 6\ISCC.exe", "C:\Program Files\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { Write-Warning "Inno Setup 6 not found (winget install JRSoftware.InnoSetup). The app folder is in $build\dist."; exit 0 }
& $iscc "/DBuildRoot=$build" packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed' }
Write-Host "Installer written to $build\installer"
