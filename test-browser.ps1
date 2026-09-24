param()
$ErrorActionPreference = 'Stop'
$jobRuntime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
$jobNode = Join-Path $jobRuntime 'node\bin\node.exe'
$jobPython = Join-Path $jobRuntime 'python\python.exe'
$jobPlaywright = Join-Path $jobRuntime 'node\node_modules\playwright'
if (!(Test-Path -LiteralPath $jobNode) -or !(Test-Path -LiteralPath $jobPython) -or !(Test-Path -LiteralPath $jobPlaywright)) {
    throw 'Bundled test runtime unavailable. See docs/BROWSER_BRIDGE.md for the portable test command.'
}
$jobPreviousPython = $env:JOB_AGENT_TEST_PYTHON
$jobPreviousPlaywright = $env:JOB_AGENT_TEST_PLAYWRIGHT
try {
    $env:JOB_AGENT_TEST_PYTHON = $jobPython
    $env:JOB_AGENT_TEST_PLAYWRIGHT = $jobPlaywright
    & $jobNode (Join-Path $PSScriptRoot 'tests\browser_smoke.cjs')
    if ($LASTEXITCODE -ne 0) { throw 'Local browser smoke test failed. The main candidate and application database were not used.' }
} finally {
    $env:JOB_AGENT_TEST_PYTHON = $jobPreviousPython
    $env:JOB_AGENT_TEST_PLAYWRIGHT = $jobPreviousPlaywright
}
