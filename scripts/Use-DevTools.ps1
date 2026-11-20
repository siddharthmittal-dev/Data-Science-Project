# Run from the repository: . .\scripts\Use-DevTools.ps1
# Adds installed tools to this terminal only; does not change Windows PATH.
$repoPath = Split-Path -Parent $PSScriptRoot
$toolPaths = @(
    '.venv\Scripts'
    '.tools\node-v24.22.2-win-x64'
    '.tools\cloudflare\node_modules\.bin'
    '.tools\azure-cli\bin'
    '.tools\postgresql\pgsql\bin'
    '.tools\bin'
)
$installedPaths = foreach ($relativePath in $toolPaths) {
    $candidatePath = Join-Path $repoPath $relativePath
    if (Test-Path -LiteralPath $candidatePath -PathType Container) {
        $candidatePath
    }
}
$env:PATH = (($installedPaths + ($env:PATH -split ';') | Select-Object -Unique) -join ';')
if (Test-Path -LiteralPath (Join-Path $repoPath '.venv\Scripts\python.exe')) {
    $env:VIRTUAL_ENV = Join-Path $repoPath '.venv'
}
# Keep necessary CLI configuration private and avoid accumulating debug logs.
if (-not $env:AZURE_CONFIG_DIR) {
    $env:AZURE_CONFIG_DIR = Join-Path $repoPath '.tools\azure-config'
}
$env:AZURE_CORE_COLLECT_TELEMETRY = 'false'
$env:WRANGLER_WRITE_LOGS = 'false'
$env:WRANGLER_SEND_METRICS = 'false'
Write-Host 'Project tools are available in this terminal. Run python, node, npm.cmd, or wrangler.'
