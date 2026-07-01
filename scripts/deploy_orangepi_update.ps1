param(
    [string]$TargetHost = "192.168.0.106",
    [string]$User = "root",
    [string]$RemoteRoot = "/opt/skyshield"
)

$ErrorActionPreference = "Stop"

function Quote-Sh([string]$Value) {
    if ($Value.Contains("'")) {
        throw "Remote shell path must not contain single quotes: $Value"
    }

    return "'$Value'"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$remote = "${User}@${TargetHost}"
$remoteRootQ = Quote-Sh $RemoteRoot

Write-Host "[1/4] Preparing remote directories on $remote"
& ssh $remote "mkdir -p $remoteRootQ/src $remoteRootQ/deploy/orangepi $remoteRootQ/backend/app/routers /etc/skyshield"

$files = @(
    @{ Local = "src/sdr_worker.py"; Remote = "$RemoteRoot/src/sdr_worker.py" },
    @{ Local = "backend/app/routers/dashboard.py"; Remote = "$RemoteRoot/backend/app/routers/dashboard.py" },
    @{ Local = "deploy/orangepi/skyshield.env.example"; Remote = "$RemoteRoot/deploy/orangepi/skyshield.env.example" },
    @{ Local = "ORANGE_PI_DEPLOYMENT.md"; Remote = "$RemoteRoot/ORANGE_PI_DEPLOYMENT.md" }
)

Write-Host "[2/4] Uploading worker, dashboard, and Orange Pi config template"
foreach ($file in $files) {
    if (-not (Test-Path $file.Local)) {
        throw "Local file not found: $($file.Local)"
    }

    $destination = "${remote}:$($file.Remote)"
    & scp $file.Local $destination
}

Write-Host "[3/4] Updating /etc/skyshield/skyshield.env to monitor only 868 and 1280 MHz"
$remoteScript = @'
set -euo pipefail

ENV_FILE="/etc/skyshield/skyshield.env"
mkdir -p "$(dirname "$ENV_FILE")"
touch "$ENV_FILE"

tmp_file="$(mktemp)"
grep -Ev '^(SCAN_CHANNELS_JSON|NARROWBAND_ENABLED_BANDS)=' "$ENV_FILE" > "$tmp_file" || true

cat >> "$tmp_file" <<'ENV_LINES'
SCAN_CHANNELS_JSON='[{"freq":869000000,"name":"868-870 MHz (Drone)"},{"freq":1280000000,"name":"1279-1281 MHz (Drone)"}]'
NARROWBAND_ENABLED_BANDS=868_870,1279_1281
ENV_LINES

install -m 600 "$tmp_file" "$ENV_FILE"
rm -f "$tmp_file"

echo "Active scan settings:"
grep -E '^(SCAN_CHANNELS_JSON|NARROWBAND_ENABLED_BANDS)=' "$ENV_FILE"
'@

$remoteScript | & ssh $remote "bash -s"

Write-Host "[4/4] Restarting backend and SDR worker"
& ssh $remote "systemctl daemon-reload; systemctl restart skyshield-backend.service skyshield-sdr-worker.service; systemctl status skyshield-backend.service skyshield-sdr-worker.service --no-pager -l"

Write-Host "Done. Dashboard: http://$TargetHost:8000/dashboard"