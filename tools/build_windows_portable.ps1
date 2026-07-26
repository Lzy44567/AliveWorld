param(
    [switch]$PackageOnly,
    [switch]$SkipFrontendBuild,
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$Project = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Project ".venv\Scripts\python.exe"
$Version = (Get-Content -LiteralPath (Join-Path $Project "VERSION") -Raw).Trim()
$ReleaseDir = Join-Path $Project "release"
$PortableName = "AliveWorld-$Version-windows-x64"
$ArchiveRootName = "AliveWorld"
$ZipPath = Join-Path $ReleaseDir "$PortableName.zip"

if (-not $PackageOnly) {
    if (-not $SkipFrontendBuild) {
        Push-Location (Join-Path $Project "aliveworld-ui")
        try {
            npm run build
            if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
        } finally {
            Pop-Location
        }
    }

    if (-not $SkipDependencyInstall) {
        & $Python -m pip install -r (Join-Path $Project "requirements-build.txt")
        if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }
    }

    & $Python (Join-Path $Project "tools\build_windows_icon.py")
    if ($LASTEXITCODE -ne 0) { throw "Windows icon generation failed." }

    $SmokeUserData = Join-Path $Project "dist\AliveWorld\UserData"
    $UserDataBackupRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("AliveWorld-userdata-" + [guid]::NewGuid().ToString("N"))
    $HasSmokeUserData = Test-Path -LiteralPath $SmokeUserData -PathType Container
    if ($HasSmokeUserData) {
        New-Item -ItemType Directory -Force -Path $UserDataBackupRoot | Out-Null
        Copy-Item -LiteralPath $SmokeUserData -Destination (Join-Path $UserDataBackupRoot "UserData") -Recurse
        Write-Host "Temporarily backed up local smoke-test UserData."
    }

    Push-Location $Project
    try {
        & $Python -m PyInstaller --noconfirm --clean "AliveWorld.spec"
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
    } finally {
        Pop-Location
        if ($HasSmokeUserData) {
            $RestoredUserData = Join-Path $UserDataBackupRoot "UserData"
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $SmokeUserData) | Out-Null
            Copy-Item -LiteralPath $RestoredUserData -Destination $SmokeUserData -Recurse -Force
            Remove-Item -LiteralPath $UserDataBackupRoot -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "Restored local smoke-test UserData after compilation."
        }
    }
}
elseif (-not (Test-Path -LiteralPath (Join-Path $Project "dist\AliveWorld\AliveWorld.exe"))) {
    throw "PackageOnly requested, but dist\AliveWorld\AliveWorld.exe does not exist."
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("AliveWorld-package-" + [guid]::NewGuid().ToString("N"))
$Staging = Join-Path $TempRoot $ArchiveRootName
try {
    New-Item -ItemType Directory -Force -Path $Staging | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $Project "dist\AliveWorld") -Force |
        Where-Object { $_.Name -ne "UserData" } |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $Staging -Recurse }
    Copy-Item -LiteralPath (Join-Path $Project "README.md") -Destination $Staging
    Copy-Item -LiteralPath (Join-Path $Project "docs\INSTALL_WINDOWS.md") -Destination (Join-Path $Staging "INSTALL_WINDOWS.md")
    Copy-Item -LiteralPath (Join-Path $Project "docs\USER_GUIDE.md") -Destination (Join-Path $Staging "USER_GUIDE.md")
    Compress-Archive -LiteralPath $Staging -DestinationPath $ZipPath -CompressionLevel Optimal
} finally {
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

& (Join-Path $Project "tools\test_windows_portable_package.ps1") -ZipPath $ZipPath -ExpectedVersion $Version
if ($LASTEXITCODE -ne 0) { throw "Portable package verification failed." }

$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$ZipPath.sha256" -Encoding ascii -Value "$Hash  $PortableName.zip"

Write-Host "Created: $ZipPath"
Write-Host "SHA256: $Hash"
Write-Host "Build output for local smoke test: $(Join-Path $Project 'dist\AliveWorld\AliveWorld.exe')"
Write-Host "Local smoke-test UserData is preserved across builds and excluded from the ZIP."
Write-Host "The ZIP always contains a stable AliveWorld root so overwrite upgrades preserve UserData."
Write-Host "Distribute the ZIP above; the release directory does not keep a second unpacked copy."
