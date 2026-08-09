Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $projectRoot

$candidates = @(
    $env:CONDA_EXE,
    "D:\anaconda3\Scripts\conda.exe",
    (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe"),
    (Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe")
)
$condaExecutable = $candidates | Where-Object {
    -not [string]::IsNullOrWhiteSpace($_) -and (Test-Path -LiteralPath $_)
} | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($condaExecutable)) {
    Write-Error "Conda was not found. Desktop Pet must be built in the dp environment."
    exit 1
}

& $condaExecutable run -n dp python scripts\build_release.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Desktop Pet 1.0.0 release build failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

Write-Host "Desktop Pet 1.0.0 onedir release build completed."
