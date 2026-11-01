$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Path work -Force | Out-Null
$env:TEMP = Join-Path $PSScriptRoot 'work'
$env:TMP = $env:TEMP
$env:MPLCONFIGDIR = Join-Path $PSScriptRoot 'work\mpl'
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot 'work\pyinstaller_cache'
Copy-Item -LiteralPath engine.py -Destination engine_source.txt -Force
& '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --distpath release --workpath work\build packaging\Plota.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
