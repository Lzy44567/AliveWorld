$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }

Push-Location $repoRoot
try {
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed with exit code $LASTEXITCODE" }
    Push-Location (Join-Path $repoRoot 'aliveworld-ui')
    try {
        node tests/entityVisibility.test.mjs
        if ($LASTEXITCODE -ne 0) { throw "Frontend behavior tests failed with exit code $LASTEXITCODE" }
        node --test tests/feedbackOperation.test.mjs tests/promptNavigation.test.mjs
        if ($LASTEXITCODE -ne 0) { throw "Feedback/prompt lifecycle tests failed with exit code $LASTEXITCODE" }
        node --test tests/streaming.test.mjs
        if ($LASTEXITCODE -ne 0) { throw "Streaming tests failed with exit code $LASTEXITCODE" }
        node --test tests/characterChat.test.mjs tests/characterConversationList.test.mjs tests/characterInteraction.test.mjs tests/characterCognition.test.mjs
        if ($LASTEXITCODE -ne 0) { throw "Character conversation tests failed with exit code $LASTEXITCODE" }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
} finally {
    Pop-Location
}
