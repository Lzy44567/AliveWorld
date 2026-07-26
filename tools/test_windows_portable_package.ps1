param(
    [Parameter(Mandatory = $true)]
    [string]$ZipPath,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedVersion
)

$ErrorActionPreference = "Stop"
$ZipPath = (Resolve-Path -LiteralPath $ZipPath).Path
$TempBase = [System.IO.Path]::GetTempPath()
$TempRoot = Join-Path $TempBase ("AliveWorld-release-test-" + [guid]::NewGuid().ToString("N"))

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

try {
    $FirstExtract = Join-Path $TempRoot "first"
    New-Item -ItemType Directory -Force -Path $FirstExtract | Out-Null
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $FirstExtract

    $Roots = @(Get-ChildItem -LiteralPath $FirstExtract -Directory -Force)
    Assert-True ($Roots.Count -eq 1) "ZIP must contain exactly one root directory."
    $AppRoot = $Roots[0].FullName
    Assert-True ($Roots[0].Name -eq "AliveWorld") "ZIP root must be the stable AliveWorld directory."
    Assert-True (Test-Path -LiteralPath (Join-Path $AppRoot "AliveWorld.exe") -PathType Leaf) "AliveWorld.exe is missing."
    Assert-True (Test-Path -LiteralPath (Join-Path $AppRoot "_internal") -PathType Container) "PyInstaller runtime is missing."
    Assert-True (Test-Path -LiteralPath (Join-Path $AppRoot "README.md") -PathType Leaf) "README.md is missing."
    Assert-True (Test-Path -LiteralPath (Join-Path $AppRoot "INSTALL_WINDOWS.md") -PathType Leaf) "INSTALL_WINDOWS.md is missing."
    Assert-True (Test-Path -LiteralPath (Join-Path $AppRoot "USER_GUIDE.md") -PathType Leaf) "USER_GUIDE.md is missing."
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $AppRoot "UserData"))) "Public ZIP must not contain UserData."

    $PrivateFiles = @(
        Get-ChildItem -LiteralPath $AppRoot -File -Recurse -Force |
            Where-Object {
                $_.Name -in @("config.yml", "legacy_migration.json", "session_state.json") -or
                $_.Extension -eq ".log"
            }
    )
    Assert-True ($PrivateFiles.Count -eq 0) "Public ZIP contains private configuration, save state, or logs."

    $BundledData = Join-Path $AppRoot "_internal\data"
    if (Test-Path -LiteralPath $BundledData -PathType Container) {
        $NonTemplateData = @(
            Get-ChildItem -LiteralPath $BundledData -File -Recurse -Force |
                Where-Object { $_.Name -notmatch "\.template\.(yml|yaml|json)$" }
        )
        Assert-True ($NonTemplateData.Count -eq 0) "Bundled data contains a non-template asset."
    }

    $Sentinel = Join-Path $AppRoot "UserData\data\saves\UpgradeSentinel\keep.txt"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Sentinel) | Out-Null
    Set-Content -LiteralPath $Sentinel -Encoding UTF8 -Value "preserve-$ExpectedVersion"

    Expand-Archive -LiteralPath $ZipPath -DestinationPath $FirstExtract -Force
    Assert-True (Test-Path -LiteralPath $Sentinel -PathType Leaf) "Overwrite upgrade removed UserData."
    Assert-True ((Get-Content -LiteralPath $Sentinel -Raw -Encoding UTF8).Trim() -eq "preserve-$ExpectedVersion") "Overwrite upgrade changed UserData."

    Write-Host "Portable verification passed: structure, privacy, and overwrite-upgrade preservation."
}
finally {
    $ResolvedTemp = [System.IO.Path]::GetFullPath($TempRoot)
    $ResolvedBase = [System.IO.Path]::GetFullPath($TempBase)
    if ($ResolvedTemp.StartsWith($ResolvedBase, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $ResolvedTemp).StartsWith("AliveWorld-release-test-")) {
        Remove-Item -LiteralPath $ResolvedTemp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
