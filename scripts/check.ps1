$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    New-Item -ItemType Directory -Force artifacts | Out-Null
    uv --cache-dir .uv-cache sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'Dependency synchronization failed' }
    uv --cache-dir .uv-cache run --locked ruff format --check packages tests scripts apps/api
    if ($LASTEXITCODE -ne 0) { throw 'Formatting failed' }
    uv --cache-dir .uv-cache run --locked ruff check packages tests scripts apps/api
    if ($LASTEXITCODE -ne 0) { throw 'Lint failed' }
    uv --cache-dir .uv-cache run --locked mypy
    if ($LASTEXITCODE -ne 0) { throw 'Type checking failed' }
    uv --cache-dir .uv-cache run --locked pytest -q --basetemp artifacts/pytest-temp
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    foreach ($regressionName in @('course-smoke', 'course-four-categories', 'course-runtime', 'course-timeout')) {
        uv --cache-dir .uv-cache run --locked python -m scripts.run_regression "benchmarks/regression/$regressionName.json"
        if ($LASTEXITCODE -ne 0) { throw "Fixed-suite regression failed: $regressionName" }
    }
} finally {
    Pop-Location
}
