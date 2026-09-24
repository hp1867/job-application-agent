param([switch]$Offline,[switch]$NoDocuments,[switch]$Dashboard)
$jobPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (!(Test-Path -LiteralPath $jobPython)) { throw 'Configured Python runtime is unavailable. Update this script to the project environment.' }
Push-Location $PSScriptRoot
try {
    if ($Dashboard) { & $jobPython -m backend.app.cli serve }
    else {
        $jobArguments = @('-m','backend.app.cli','run')
        if ($Offline) {$jobArguments += '--offline'}
        if ($NoDocuments) {$jobArguments += '--no-documents'}
        & $jobPython @jobArguments
    }
} finally { Pop-Location }
