param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceRoot = Join-Path $repoRoot 'tests\fixtures\manual_assets'
$dataRoot = Join-Path $repoRoot 'data'

foreach ($assetType in @('worldbooks', 'styles', 'characters', 'entities')) {
    $sourceDir = Join-Path $sourceRoot $assetType
    $targetDir = Join-Path $dataRoot $assetType
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

    Get-ChildItem -LiteralPath $sourceDir -Filter '*.yml' | ForEach-Object {
        $target = Join-Path $targetDir $_.Name
        if ((Test-Path -LiteralPath $target) -and -not $Force) {
            Write-Host "已保留现有测试资产: $($_.Name)"
        } else {
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
            Write-Host "已安装测试资产: $($_.Name)"
        }
    }
}

Write-Host '测试资产已安装到本机 data/；该目录被 Git 忽略，不会推送。'
