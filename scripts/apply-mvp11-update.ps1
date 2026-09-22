# MVP 1.1 includes frontend, renderer and sound asset changes; project data is untouched.
param([string]$AppPath)
$ErrorActionPreference = 'Stop'
$bundleRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($AppPath)) {
    Write-Host 'Stop SceneForge before applying this update.'
    $AppPath = Read-Host 'Existing working app folder (contains backend and frontend)'
}
$targetRoot = (Resolve-Path -LiteralPath $AppPath.Trim().Trim('"')).Path
if ($targetRoot.Equals($bundleRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Choose the existing app, not the update package.' }
if (-not (Test-Path -LiteralPath (Join-Path $targetRoot 'backend\app\main.py'))) { throw 'SceneForge backend not found.' }
if (-not (Test-Path -LiteralPath (Join-Path $targetRoot 'frontend\package.json'))) { throw 'SceneForge frontend not found.' }
$items = @('frontend\dist', 'frontend\src', 'frontend\public', 'frontend\index.html', 'backend\app', 'assets\sfx')
foreach ($item in $items) {
    if (-not (Test-Path -LiteralPath (Join-Path $bundleRoot $item))) { throw "Incomplete update: missing $item" }
}
$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + ([guid]::NewGuid().ToString('N').Substring(0,6))
$backup = Join-Path $targetRoot "_mvp11_backups\$stamp"
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$originalItems = @()
foreach ($item in $items) {
    $old = Join-Path $targetRoot $item
    if (Test-Path -LiteralPath $old) {
        $parent = Split-Path -Parent (Join-Path $backup $item)
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        Copy-Item -LiteralPath $old -Destination $parent -Recurse -Force
        $originalItems += $item
    }
}
try {
    foreach ($item in $items) {
        $target = Join-Path $targetRoot $item
        $parent = Split-Path -Parent $target
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        Copy-Item -LiteralPath (Join-Path $bundleRoot $item) -Destination $parent -Recurse -Force
    }
} catch {
    $updateFailure = $_
    foreach ($item in $items) {
        $target = Join-Path $targetRoot $item
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        if ($originalItems -contains $item) {
            Copy-Item -LiteralPath (Join-Path $backup $item) -Destination (Split-Path -Parent $target) -Recurse -Force
        }
    }
    throw $updateFailure
}
Write-Host 'MVP 1.1 applied.' -ForegroundColor Green
Write-Host "Backup: $backup"
Write-Host 'Restart the ORIGINAL app, then Ctrl+F5 in the browser.'
Write-Host 'Projects, media, API keys and installed dependencies are preserved.'
Write-Host 'Re-render scenes to hear synchronized typewriter audio.'
