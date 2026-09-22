param([Parameter(Mandatory=$true)][ValidateSet('kokoro','chatterbox')][string]$Engine)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
if (-not $dockerCommand) { throw 'Install and start Docker Desktop with Linux containers, then run this launcher again.' }

# Invoke Docker directly through .NET: Windows PowerShell 5.1 otherwise
# turns stderr warnings into terminating NativeCommandError records.
# Exit status, not the presence of stderr output, determines success.
function Invoke-DockerProcess {
    param([string]$ArgumentText, [switch]$Quiet)
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $dockerCommand.Source
    $info.Arguments = $ArgumentText
    $info.UseShellExecute = $false
    $info.RedirectStandardOutput = [bool]$Quiet
    $info.RedirectStandardError = [bool]$Quiet
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    try {
        [void]$process.Start()
        if ($Quiet) {
            $stdout = $process.StandardOutput.ReadToEndAsync()
            $stderr = $process.StandardError.ReadToEndAsync()
        }
        $process.WaitForExit()
        if ($Quiet) {
            [void]$stdout.GetAwaiter().GetResult()
            [void]$stderr.GetAwaiter().GetResult()
        }
        return $process.ExitCode
    } finally { $process.Dispose() }
}

$code = Invoke-DockerProcess -ArgumentText 'info' -Quiet
if ($code -ne 0) { throw 'Docker Desktop is not ready. Start its Linux engine, verify docker info has a Server section, then retry.' }
$compose = Join-Path $root 'services\compose.yaml'
if (-not (Test-Path -LiteralPath $compose)) { throw "Missing voice configuration: $compose" }
Write-Host "Starting local $Engine. First installation downloads engine dependencies and models."
$arguments = 'compose -f "' + $compose + '"'
if ($Engine -eq 'chatterbox') {
    $arguments += ' --profile arabic up -d --build chatterbox'
} else {
    $arguments += ' up -d kokoro'
}
$code = Invoke-DockerProcess -ArgumentText $arguments
if ($code -ne 0) { throw "Voice service failed to start (Docker exit code $code). Read the Docker output above." }
Write-Host 'Return to SceneForge > Audio > Local voice engines and click Connect.'
Write-Host 'A short audition verifies model readiness. The first Chatterbox audition may download the model.'
$port = if ($Engine -eq 'chatterbox') { 8881 } else { 8880 }
$ready = $false
Write-Host "Checking service on 127.0.0.1:$port ..."
for ($attempt=0; $attempt -lt 20; $attempt++) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/v1/audio/voices" -TimeoutSec 3
        if ($response.StatusCode -eq 200) { $ready=$true; break }
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) {
    Write-Host 'Voice service is not responding. Recent container logs:' -ForegroundColor Yellow
    [void](Invoke-DockerProcess -ArgumentText ('compose -f "' + $compose + '" logs --tail 80 ' + $Engine))
    throw 'The container did not become ready. Save the output above. Run DIAGNOSE_VOICE.bat for status and logs.'
}
Write-Host 'Voice API is responding. Connect in Audio, then audition a short sentence.' -ForegroundColor Green
