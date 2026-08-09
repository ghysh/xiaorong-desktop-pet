Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($projectRoot)) {
    Write-Error "错误：无法定位项目根目录。"
    exit 1
}

Set-Location -LiteralPath $projectRoot

$condaCommand = Get-Command conda -ErrorAction SilentlyContinue
if ($null -ne $condaCommand) {
    $condaExecutable = $condaCommand.Source
}
else {
    $candidatePaths = @(
        $env:CONDA_EXE,
        (Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe"),
        (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe"),
        "C:\ProgramData\miniconda3\Scripts\conda.exe",
        "C:\ProgramData\anaconda3\Scripts\conda.exe",
        "D:\anaconda3\Scripts\conda.exe"
    )
    $condaExecutable = $candidatePaths | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and (Test-Path -LiteralPath $_)
    } | Select-Object -First 1
}

if ([string]::IsNullOrWhiteSpace($condaExecutable)) {
    Write-Error "错误：未找到 Conda 命令。请安装 Conda 或将 conda 加入 PATH。"
    exit 1
}

try {
    $environmentJson = & $condaExecutable env list --json
    if ($LASTEXITCODE -ne 0) {
        throw "Conda 无法读取环境列表。"
    }

    $environmentPaths = ($environmentJson | ConvertFrom-Json).envs
    $dpEnvironment = $environmentPaths | Where-Object {
        [System.IO.Path]::GetFileName($_) -eq "dp"
    }
    if ($null -eq $dpEnvironment) {
        Write-Error "错误：未找到 dp 环境。请先执行 conda create -n dp python=3.11 -y。"
        exit 1
    }

    & $condaExecutable run -n dp python -m desktop_pet
    if ($LASTEXITCODE -ne 0) {
        throw "桌宠开发环境验证程序退出码为 $LASTEXITCODE。"
    }
}
catch {
    Write-Error "错误：启动失败。$($_.Exception.Message)"
    exit 1
}
