$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location -LiteralPath $root

python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }

$venvPython = Join-Path $root '.venv-build\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv .venv-build
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the build virtual environment.' }
}

& $venvPython -m pip install --disable-pip-version-check -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install build dependencies.' }

& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name DeSSaveConverter `
    --specpath build `
    --workpath build\pyinstaller `
    --distpath dist `
    des_save_gui.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$exe = Join-Path $root 'dist\DeSSaveConverter.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw 'Expected executable was not created.' }
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
[System.IO.File]::WriteAllText(
    "$exe.sha256",
    "$hash  DeSSaveConverter.exe`n",
    [System.Text.Encoding]::ASCII
)
Write-Host "Built: $exe"
Write-Host "SHA256: $hash"
