param(
    [string]$TargetHost,
    [string]$User = "root",
    [ValidateSet("rf", "acoustic", "all")]
    [string]$Project = "rf",
    [string]$RfBackendService = "skyshield-backend.service",
    [string]$RfWorkerService = "skyshield-sdr-worker.service",
    [string]$AcousticBackendService = "skyshield-acoustic-backend.service",
    [string]$AcousticWorkerService = "skyshield-acoustic-worker.service",
    [string]$Since = "15 minutes ago",
    [switch]$NoFollow
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($TargetHost)) {
    throw "Specify -TargetHost (for example: 100.77.10.25 or orange-01.tailnet.ts.net)."
}

$services = @()
if ($Project -in @("rf", "all")) {
    $services += @($RfBackendService, $RfWorkerService)
}
if ($Project -in @("acoustic", "all")) {
    $services += @($AcousticBackendService, $AcousticWorkerService)
}

$serviceList = $services -join " "
$followArg = if ($NoFollow) { "" } else { "-f" }

$cmd = "journalctl --no-pager $followArg --since '$Since'"
foreach ($svc in $services) {
    $cmd += " -u $svc"
}

Write-Host "Watching services on ${TargetHost}: $serviceList" -ForegroundColor Cyan
& ssh "$User@$TargetHost" $cmd
if ($LASTEXITCODE -ne 0) {
    throw "Failed to read logs from remote host"
}
