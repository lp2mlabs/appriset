$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Buat .venv dan instal requirements.txt terlebih dahulu.' }
New-Item -ItemType Directory -Path 'build-tmp', 'release', 'assets' -Force | Out-Null
$env:TEMP = Join-Path $PSScriptRoot 'build-tmp'
$env:TMP = $env:TEMP
$env:PATH = (Join-Path $PSScriptRoot '.venv\Scripts') + ';' + $env:SystemRoot + '\System32;' + $env:SystemRoot
& $taskPython tools\prepare_release.py
if ($LASTEXITCODE -ne 0) { throw 'Persiapan rilis gagal.' }
& $taskPython -m PyInstaller --noconfirm --distpath release --workpath build 'WebImage Studio.spec'
if ($LASTEXITCODE -ne 0) { throw 'Build EXE gagal.' }
Copy-Item -LiteralPath README.md -Destination release\PANDUAN.md -Force
Copy-Item -LiteralPath THIRD-PARTY-NOTICES.md -Destination release\THIRD-PARTY-NOTICES.md -Force
Get-Item -LiteralPath 'release\WebImage Studio.exe' | Select-Object FullName, Length
