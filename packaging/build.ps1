# Build the Windows exe and the installer wizard (nothing is released or uploaded).
# Usage (from anywhere):  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
# The finished app and installer go to the project's release folder:  release\OrbSim\OrbSim.exe  and  release\OrbSim-Setup-<version>.exe  (git-ignored, never committed).
# Temporary PyInstaller work files go to the system temp folder.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$release = Join-Path (Get-Location) 'release'; $work = Join-Path $env:TEMP 'orbsim_build\work'
New-Item -ItemType Directory -Force $release, $work | Out-Null
python -m pip install -r requirements-dev.txt
python packaging\make_icon.py
python packaging\make_wizard_images.py
python -m PyInstaller packaging\mathkit.spec --noconfirm --distpath $release --workpath $work
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "C:\Program Files (x86)\Inno Setup 6\ISCC.exe", "C:\Program Files\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { Write-Warning "Inno Setup 6 not found (winget install JRSoftware.InnoSetup). The app folder is in $release\OrbSim."; exit 0 }
& $iscc "/DBuildRoot=$release" packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed' }
Write-Host "App folder: $release\OrbSim`nInstaller:  $release"
