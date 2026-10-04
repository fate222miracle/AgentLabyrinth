$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    uv --cache-dir .uv-cache sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'Dependency synchronization failed' }
    uv --cache-dir .uv-cache run --locked python -m scripts.check
    if ($LASTEXITCODE -ne 0) { throw 'Quality gate failed' }
} finally {
    Pop-Location
}
