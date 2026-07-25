param(
    [switch]$PackageOnly
)

$ErrorActionPreference = "Stop"
$Project = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Project ".venv\Scripts\python.exe"
$Version = (Get-Content -LiteralPath (Join-Path $Project "VERSION") -Raw).Trim()
$ReleaseDir = Join-Path $Project "release"
$PortableName = "AliveWorld-$Version-windows-x64"
$ZipPath = Join-Path $ReleaseDir "$PortableName.zip"

if (-not $PackageOnly) {
    Push-Location (Join-Path $Project "aliveworld-ui")
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    } finally {
        Pop-Location
    }

    & $Python -m pip install -r (Join-Path $Project "requirements-build.txt")
    if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }

    & $Python (Join-Path $Project "tools\build_windows_icon.py")
    if ($LASTEXITCODE -ne 0) { throw "Windows icon generation failed." }

    Push-Location $Project
    try {
        & $Python -m PyInstaller --noconfirm --clean "AliveWorld.spec"
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
    } finally {
        Pop-Location
    }
}
elseif (-not (Test-Path -LiteralPath (Join-Path $Project "dist\AliveWorld\AliveWorld.exe"))) {
    throw "PackageOnly requested, but dist\AliveWorld\AliveWorld.exe does not exist."
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("AliveWorld-package-" + [guid]::NewGuid().ToString("N"))
$Staging = Join-Path $TempRoot $PortableName
try {
    New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
    Copy-Item -LiteralPath (Join-Path $Project "dist\AliveWorld") -Destination $Staging -Recurse
    Copy-Item -LiteralPath (Join-Path $Project "README.md") -Destination $Staging
    Copy-Item -LiteralPath (Join-Path $Project "docs\INSTALL_WINDOWS.md") -Destination (Join-Path $Staging "INSTALL_WINDOWS.md")
    Compress-Archive -LiteralPath $Staging -DestinationPath $ZipPath -CompressionLevel Optimal
} finally {
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$ZipPath.sha256" -Encoding ascii -Value "$Hash  $PortableName.zip"

Write-Host "Created: $ZipPath"
Write-Host "SHA256: $Hash"
