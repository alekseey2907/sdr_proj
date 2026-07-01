<#
Сбор инвентаря парка SkyShield.

Читает с каждого устройства (по SSH) device_id и версию, собирает в один CSV.
Список устройств берется из файла (по строке на хост) или из параметра -Hosts.

Примеры:
  .\scripts\collect_inventory.ps1 -Hosts 100.70.123.76,100.70.123.90
  .\scripts\collect_inventory.ps1 -HostsFile .\fleet_hosts.txt -OutFile fleet_inventory.csv
#>
param(
    [string[]]$Hosts,
    [string]$HostsFile,
    [string]$User = "root",
    [string]$OutFile = "fleet_inventory.csv"
)

$ErrorActionPreference = "Stop"

$targetHosts = @()
if ($Hosts) { $targetHosts += $Hosts }
if ($HostsFile) {
    if (-not (Test-Path $HostsFile)) { throw "HostsFile not found: $HostsFile" }
    $targetHosts += Get-Content $HostsFile | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith("#") }
}

if (-not $targetHosts -or $targetHosts.Count -eq 0) {
    throw "Provide -Hosts a,b,c or -HostsFile path.txt"
}

$remoteCmd = "cat /etc/skyshield/device.json 2>/dev/null; echo '---'; cat /opt/skyshield/sdr_proj/VERSION 2>/dev/null"

$rows = @()
foreach ($h in $targetHosts) {
    Write-Host "Collecting from $h ..." -ForegroundColor Cyan
    $deviceId = "unreachable"
    $version = "unknown"
    try {
        $output = & ssh "$User@$h" $remoteCmd 2>$null
        $joined = ($output -join "`n")
        $parts = $joined -split "---"
        if ($parts.Count -ge 1 -and $parts[0].Trim()) {
            try {
                $json = $parts[0] | ConvertFrom-Json
                if ($json.device_id) { $deviceId = $json.device_id }
            } catch { $deviceId = "parse_error" }
        }
        if ($parts.Count -ge 2 -and $parts[1].Trim()) {
            $version = $parts[1].Trim()
        }
    } catch {
        $deviceId = "unreachable"
    }

    $rows += [pscustomobject]@{
        host       = $h
        device_id  = $deviceId
        version    = $version
        checked_at = (Get-Date).ToString("s")
    }
}

$rows | Export-Csv -Path $OutFile -NoTypeInformation -Encoding UTF8
Write-Host "`nInventory written to $OutFile" -ForegroundColor Green
$rows | Format-Table -AutoSize
