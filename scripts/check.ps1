$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    New-Item -ItemType Directory -Force artifacts | Out-Null
    uv --cache-dir .uv-cache sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'Dependency synchronization failed' }
    uv --cache-dir .uv-cache run --locked ruff format --check packages tests scripts
    if ($LASTEXITCODE -ne 0) { throw 'Formatting failed' }
    uv --cache-dir .uv-cache run --locked ruff check packages tests scripts
    if ($LASTEXITCODE -ne 0) { throw 'Lint failed' }
    uv --cache-dir .uv-cache run --locked mypy
    if ($LASTEXITCODE -ne 0) { throw 'Type checking failed' }
    uv --cache-dir .uv-cache run --locked pytest -q --basetemp artifacts/pytest-temp
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
} finally {
    Pop-Location
}
