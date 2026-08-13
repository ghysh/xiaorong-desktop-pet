Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$condaExecutable = "D:\anaconda3\Scripts\conda.exe"

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    Write-Error "小融 1.2.0 只能在 Windows x64 上构建。"
    exit 1
}

if (-not [Environment]::Is64BitOperatingSystem) {
    Write-Error "小融 1.2.0 仅支持 64 位 Windows。"
    exit 1
}

if (-not (Test-Path -LiteralPath $condaExecutable -PathType Leaf)) {
    Write-Error "找不到指定的 Conda：$condaExecutable"
    exit 1
}

Set-Location -LiteralPath $projectRoot

$environmentJson = & $condaExecutable env list --json
if ($LASTEXITCODE -ne 0) {
    Write-Error "Conda 无法读取环境列表。"
    exit 1
}

$dpEnvironment = (
    ($environmentJson | ConvertFrom-Json).envs |
    Where-Object {
        [IO.Path]::GetFileName($_) -eq "dp"
    } |
    Select-Object -First 1
)

if ($null -eq $dpEnvironment) {
    Write-Error "找不到 dp 环境；构建脚本不会自动创建或修改环境。"
    exit 1
}

Write-Host "开始构建小融 1.2.0..."
Write-Host "项目目录：$projectRoot"
Write-Host "Conda 环境：$dpEnvironment"

& $condaExecutable run --no-capture-output -n dp `
    python scripts\build_xiaorong_release.py

$buildExitCode = $LASTEXITCODE

if ($buildExitCode -ne 0) {
    Write-Error "小融 1.2.0 发布构建失败，退出码：$buildExitCode"
    exit $buildExitCode
}

$releaseExecutable = Join-Path `
    $projectRoot `
    "release\小融-1.2.0-win64.exe"

if (-not (Test-Path -LiteralPath $releaseExecutable -PathType Leaf)) {
    Write-Error "构建流程未生成预期发布文件：$releaseExecutable"
    exit 1
}

Write-Host ""
Write-Host "小融 1.2.0 发布构建完成。"
Write-Host "发布文件：$releaseExecutable"
