param(
    [switch]$DryRun,
    [int]$MaxItems = 0
)

$cmd = "python -m app.run"
if ($DryRun) {
    $cmd += " --dry-run"
}
if ($MaxItems -gt 0) {
    $cmd += " --max-items $MaxItems"
}

Write-Host "Running: $cmd"
Invoke-Expression $cmd

