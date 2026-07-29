param(
    [string]$Target = "seahorse-valley",
    [int]$Width = 640,
    [int]$Height = 360,
    [int]$Repeats = 5,
    [int]$ReferenceSamples = 24,
    [string]$Output = "double-single-benchmark-results.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Virtual environment not found. Run .\scripts\run_windows.ps1 once first."
}

Push-Location $ProjectRoot
try {
    & $Python .\scripts\benchmark_double_single.py `
        --target $Target `
        --width $Width `
        --height $Height `
        --repeats $Repeats `
        --reference-samples $ReferenceSamples `
        --output $Output
    if ($LASTEXITCODE -ne 0) {
        throw "Double-single benchmark failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
