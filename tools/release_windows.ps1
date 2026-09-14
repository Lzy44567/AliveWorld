param(
    [switch]$Publish,
    [switch]$PreflightOnly,
    [switch]$PackageOnly,
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = 'Stop'
$Project = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Project '.venv\Scripts\python.exe'
$VersionFile = Join-Path $Project 'VERSION'
$Changelog = Join-Path $Project 'CHANGELOG.md'

function Assert-LastExit([string]$Message) {
    if ($LASTEXITCODE -ne 0) { throw "$Message (exit $LASTEXITCODE)" }
}

function Invoke-NativeRetry([scriptblock]$Action, [string]$Message, [int]$Attempts = 3) {
    for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
        & $Action
        if ($LASTEXITCODE -eq 0) { return }
        if ($Attempt -lt $Attempts) {
            Write-Warning "$Message; retry $Attempt/$Attempts"
            Start-Sleep -Seconds ([Math]::Pow(2, $Attempt - 1))
        }
    }
    throw "$Message after $Attempts attempts"
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Repository Python environment is missing. Run install_windows.bat first.'
}
$Version = (Get-Content -LiteralPath $VersionFile -Raw).Trim()
if ($Version -notmatch '^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$') {
    throw "Invalid VERSION: $Version"
}
$Tag = "v$Version"
$PortableName = "AliveWorld-$Version-windows-x64"
$ReleaseDir = Join-Path $Project 'release'
$ZipPath = Join-Path $ReleaseDir "$PortableName.zip"
$HashPath = "$ZipPath.sha256"
$NotesPath = Join-Path $ReleaseDir "$PortableName-release-notes.md"

Push-Location $Project
try {
    $Root = (& git rev-parse --show-toplevel).Trim()
    Assert-LastExit 'Not inside a Git repository'
    if ([System.IO.Path]::GetFullPath($Root) -ne [System.IO.Path]::GetFullPath($Project)) {
        throw "Release script must run from the AliveWorld repository root: $Project"
    }
    $Dirty = @(& git status --porcelain --untracked-files=all)
    Assert-LastExit 'Unable to inspect Git worktree'
    if ($Dirty.Count -gt 0) {
        throw "Git worktree is not clean. Commit or remove these changes first:`n$($Dirty -join "`n")"
    }

    New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
    & $Python (Join-Path $Project 'tools\release_notes.py') `
        --version $Version --changelog $Changelog --output $NotesPath
    Assert-LastExit 'Unable to extract release notes'

    $Prerelease = $Version -match '(?i)(?:^|[-.])(dev|alpha|beta|rc)(?:[.-]|$)'
    $Commit = (& git rev-parse HEAD).Trim()
    Assert-LastExit 'Unable to resolve current commit'

    Write-Host "Release preflight passed: $Tag"
    Write-Host "Commit: $Commit"
    Write-Host "Release notes: $NotesPath"
    Write-Host "Release channel: $(if ($Prerelease) { 'pre-release' } else { 'stable' })"

    if ($PreflightOnly) {
        Write-Host 'PreflightOnly: tests, package build and online publication were skipped.'
        exit 0
    }

    & (Join-Path $Project 'tools\run_checks.ps1')
    Assert-LastExit 'Automated checks failed'
    Push-Location (Join-Path $Project 'aliveworld-ui')
    try {
        npm run test:e2e
        Assert-LastExit 'Playwright acceptance failed'
    } finally {
        Pop-Location
    }

    $BuildArguments = @('-SkipFrontendBuild')
    if ($PackageOnly) { $BuildArguments += '-PackageOnly' }
    if ($SkipDependencyInstall) { $BuildArguments += '-SkipDependencyInstall' }
    & (Join-Path $Project 'tools\build_windows_portable.ps1') @BuildArguments
    Assert-LastExit 'Windows portable build failed'
    if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $HashPath -PathType Leaf)) {
        throw "Release assets are incomplete: $ZipPath / $HashPath"
    }

    if (-not $Publish) {
        Write-Host 'Local release candidate is ready. No network publication was performed.'
        Write-Host "To publish this exact clean commit, rerun: .\tools\release_windows.ps1 -PackageOnly -Publish"
        exit 0
    }

    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw 'GitHub CLI (gh) is not installed or not available in PATH.'
    }
    & gh auth status
    Assert-LastExit 'GitHub CLI is not authenticated'
    Invoke-NativeRetry { git fetch origin main --quiet } 'Unable to refresh origin/main'
    & git merge-base --is-ancestor $Commit origin/main
    Assert-LastExit 'Current commit is not contained in origin/main; push or merge it before publishing'
    $RemoteTag = @()
    for ($Attempt = 1; $Attempt -le 3; $Attempt++) {
        $RemoteTag = @(& git ls-remote --tags origin "refs/tags/$Tag")
        if ($LASTEXITCODE -eq 0) { break }
        if ($Attempt -eq 3) { throw 'Unable to query remote tags after 3 attempts' }
        Start-Sleep -Seconds ([Math]::Pow(2, $Attempt - 1))
    }
    if ($RemoteTag.Count -gt 0) { throw "Remote tag already exists: $Tag" }
    & gh release view $Tag *> $null
    if ($LASTEXITCODE -eq 0) { throw "GitHub Release already exists: $Tag" }

    $Arguments = @(
        'release', 'create', $Tag, $ZipPath, $HashPath,
        '--target', $Commit,
        '--title', "AliveWorld $Tag",
        '--notes-file', $NotesPath
    )
    if ($Prerelease) { $Arguments += '--prerelease' }
    for ($Attempt = 1; $Attempt -le 3; $Attempt++) {
        & gh @Arguments
        if ($LASTEXITCODE -eq 0) { break }
        & gh release view $Tag *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Warning 'The create request returned an error, but the Release now exists; treating it as successful.'
            break
        }
        if ($Attempt -eq 3) { throw 'GitHub Release creation failed after 3 attempts' }
        Start-Sleep -Seconds ([Math]::Pow(2, $Attempt - 1))
    }
    Write-Host "Published GitHub Release: $Tag"
} finally {
    Pop-Location
}
