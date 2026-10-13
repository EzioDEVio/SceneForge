# SceneForge - Voicebox check. Read-only unless you add -ClearStuck or -Test.
# Run it while Voicebox is open:
#   powershell -ExecutionPolicy Bypass -File .\voicebox-diagnose.ps1
#   powershell -ExecutionPolicy Bypass -File .\voicebox-diagnose.ps1 -ClearStuck        (cancel jobs stuck at "Generating...")
#   powershell -ExecutionPolicy Bypass -File .\voicebox-diagnose.ps1 -Test "adien voice" (make one short test line)
# It writes voicebox-report.txt next to this script. Send that file back; it contains your voice
# names and the text of recent Voicebox narrations, nothing else (no keys, no audio).
param([string]$Url = 'http://127.0.0.1:17493', [switch]$ClearStuck, [string]$Test = '')

$ErrorActionPreference = 'Continue'
[System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy   # this computer only, never a proxy
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Report = Join-Path $Here 'voicebox-report.txt'
$lines = New-Object System.Collections.Generic.List[string]
function Say($text) { Write-Host $text; $lines.Add($text) }
function Get-Json($path) {
    try { return Invoke-RestMethod -Uri ($Url + $path) -TimeoutSec 30 }
    catch { Say ("  ! " + $path + " failed: " + $_.Exception.Message); return $null }
}

Say ("Voicebox check " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " at " + $Url)
Say ""
Say "1. Is Voicebox answering?"
$health = Get-Json '/health'
if (-not $health) { Say "  Voicebox is not answering at $Url. Open Voicebox, wait until its window shows your voices, and run this again."; $lines | Set-Content -Path $Report -Encoding UTF8; exit 1 }
Say ("  yes: " + ($health | ConvertTo-Json -Compress -Depth 3))

Say ""
Say "2. Voices (profiles)"
$profiles = @(Get-Json '/profiles' | ForEach-Object { $_ })   # a JSON list arrives as one object; unroll it
foreach ($p in $profiles) {
    Say ("  - {0} | id {1} | type {2} | preset engine {3} | default engine {4} | language {5}" -f $p.name, $p.id, $p.voice_type, $p.preset_engine, $p.default_engine, $p.language)
}

Say ""
Say "3. Models (downloaded / downloading / loaded)"
$models = Get-Json '/models/status'
if ($models) {
    foreach ($m in @($models.models | ForEach-Object { $_ })) {
        Say ("  - {0} ({1}) downloaded={2} downloading={3} loaded={4} size={5} MB" -f $m.model_name, $m.display_name, $m.downloaded, $m.downloading, $m.loaded, [math]::Round([double]($m.size_mb), 0))
    }
}

Say ""
Say "4. Recent narrations (newest first)"
$history = Get-Json '/history?limit=20'
$stuck = @()
if ($history) {
    foreach ($h in @($history.items | ForEach-Object { $_ })) {
        $age = ''
        try { $age = [int]((Get-Date).ToUniversalTime() - [datetime]::Parse($h.created_at)).TotalMinutes } catch {}
        $short = ([string]$h.text -replace '\s+', ' ')
        if ($short.Length -gt 50) { $short = $short.Substring(0, 50) }
        Say ("  - {0} | {1} | engine {2} {3} | {4} | {5} min ago | error: {6} | text: {7}" -f $h.id, $h.profile_name, $h.engine, $h.model_size, $h.status, $age, $h.error, $short)
        if (($h.status -eq 'generating' -or $h.status -eq 'loading_model') -and $age -ne '' -and $age -ge 10) { $stuck += $h }
    }
}
Say ""
if ($stuck.Count) {
    Say ("  {0} narration(s) are stuck at Generating. Voicebox makes one narration at a time, so they block all new ones." -f $stuck.Count)
    if ($ClearStuck) {
        foreach ($h in $stuck) {
            try { $r = Invoke-RestMethod -Method Post -Uri ($Url + '/generate/' + $h.id + '/cancel') -TimeoutSec 30; Say ("  cancelled " + $h.id + ": " + $r.message) }
            catch { Say ("  ! could not cancel " + $h.id + ": " + $_.Exception.Message) }
        }
    } else { Say "  Run again with -ClearStuck to cancel them (or quit Voicebox completely and open it again)." }
} else { Say "  No stuck narrations." }

if ($Test) {
    Say ""
    Say ("5. Test narration with the voice '" + $Test + "'")
    $p = $profiles | Where-Object { $_.name -eq $Test } | Select-Object -First 1
    if (-not $p) { Say "  ! No voice with that exact name." }
    else {
        $engine = if ($p.default_engine) { $p.default_engine } elseif ($p.preset_engine) { $p.preset_engine } else { $null }
        $body = @{ profile_id = $p.id; text = 'This is a short SceneForge test.'; language = $(if ($p.language) { $p.language } else { 'en' }) }
        if ($engine) { $body.engine = $engine }
        Say ("  sending: " + ($body | ConvertTo-Json -Compress))
        try {
            $g = Invoke-RestMethod -Method Post -Uri ($Url + '/generate') -ContentType 'application/json' -Body ($body | ConvertTo-Json) -TimeoutSec 120
            Say ("  queued " + $g.id + " status " + $g.status)
            $deadline = (Get-Date).AddMinutes(5)
            do {
                Start-Sleep -Seconds 3
                $s = Invoke-RestMethod -Uri ($Url + '/history/' + $g.id) -TimeoutSec 30
                Write-Host ("    " + (Get-Date -Format 'HH:mm:ss') + " " + $s.status)
            } while (($s.status -eq 'generating' -or $s.status -eq 'loading_model') -and (Get-Date) -lt $deadline)
            Say ("  final status: " + $s.status + " | error: " + $s.error + " | duration: " + $s.duration)
            if ($s.status -eq 'generating' -or $s.status -eq 'loading_model') {
                Say "  Still not finished after 5 minutes: Voicebox itself is not producing audio for this voice."
            }
        } catch { Say ("  ! generate failed: " + $_.Exception.Message + " " + $_.ErrorDetails.Message) }
    }
}

$lines | Set-Content -Path $Report -Encoding UTF8
Write-Host ""
Write-Host "Saved $Report - send this file back." -ForegroundColor Green
