param(
    [string]$TargetHost,
    [string]$User = "root",
    [ValidateSet("rf", "acoustic", "all")]
    [string]$Project = "all",
    [string]$Branch = "main",
    [string]$RfRoot = "/opt/skyshield",
    [string]$AcousticRoot = "/opt/skyshield-acoustic",
    [string]$RfBackendService = "skyshield-backend.service",
    [string]$RfWorkerService = "skyshield-sdr-worker.service",
    [string]$AcousticBackendService = "skyshield-acoustic-backend.service",
    [string]$AcousticWorkerService = "skyshield-acoustic-worker.service",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($TargetHost)) {
    throw "Specify -TargetHost (for example: 100.77.10.25 or orange-01.tailnet.ts.net)."
}

function Invoke-Remote {
    param([string]$Remote)
    & ssh "$User@$TargetHost" $Remote
    if ($LASTEXITCODE -ne 0) {
        throw "Remote command failed: $Remote"
    }
}

function Invoke-RemoteScript {
    param([string]$ScriptBody)
    $normalized = $ScriptBody -replace "`r`n", "`n"
    $normalized = $normalized -replace "`r", "`n"
    $normalized | & ssh "$User@$TargetHost" "bash -s"
    if ($LASTEXITCODE -ne 0) {
        throw "Remote script failed"
    }
}

function Update-Project {
    param(
        [string]$Name,
        [string]$Root,
        [string[]]$Services
    )

    Write-Host "`n=== Updating $Name project on $TargetHost ===" -ForegroundColor Cyan

    $installBlock = @"
set -eu
cd '$Root'
if [ ! -d .git ]; then
  echo 'ERROR: no .git in $Root. Clone repo first.'
  exit 2
fi
git fetch --all --prune
git checkout '$Branch'
git pull --ff-only origin '$Branch'
"@

    if (-not $SkipInstall) {
        $installBlock += @"
chmod +x scripts/orangepi_install.sh
./scripts/orangepi_install.sh
"@
    }

    Invoke-RemoteScript $installBlock

    $serviceList = ($Services -join " ")
    Invoke-Remote "systemctl daemon-reload; systemctl restart $serviceList; systemctl --no-pager --full status $serviceList"
}

$runRf = $Project -in @("rf", "all")
$runAcoustic = $Project -in @("acoustic", "all")

if ($runRf) {
    Update-Project -Name "RF" -Root $RfRoot -Services @($RfBackendService, $RfWorkerService)
}

if ($runAcoustic) {
    Update-Project -Name "Acoustic" -Root $AcousticRoot -Services @($AcousticBackendService, $AcousticWorkerService)
}

Write-Host "`nDone. Use scripts/remote_logs.ps1 to watch runtime logs." -ForegroundColor Green
