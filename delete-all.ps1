<#
.SYNOPSIS
    Deletes hackathon resources from team resource groups.

.DESCRIPTION
    Reads team configuration from teams.json and deletes all deployed resources
    inside each team's resource group. Does NOT delete the resource groups themselves.

.PARAMETER TeamsFile
    Path to the teams configuration JSON file. Defaults to teams.json.

.PARAMETER Team
    Optional. Delete resources for a single team only (e.g., "apex").

.PARAMETER Force
    Skip confirmation prompt.

.EXAMPLE
    # Delete all teams (with confirmation)
    .\delete-all.ps1

    # Delete a single team
    .\delete-all.ps1 -Team bolt

    # Skip confirmation
    .\delete-all.ps1 -Force
#>

param(
    [string]$TeamsFile = "teams.json",
    [string]$Team,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $TeamsFile)) {
    Write-Error "Teams file not found: $TeamsFile"
    return
}

$config = Get-Content $TeamsFile | ConvertFrom-Json
$subscription = $config.subscription
$rgPrefix = $config.rgPrefix

$teams = if ($Team) {
    $config.teams | Where-Object { $_.name -eq $Team }
} else {
    $config.teams
}

if (-not $teams) {
    Write-Error "Team '$Team' not found in $TeamsFile"
    return
}

Write-Host "`n=== Hackathon Resource Cleanup ===" -ForegroundColor Red
Write-Host "Subscription: $subscription"
Write-Host "Teams: $(($teams | ForEach-Object { $_.name }) -join ', ')"
Write-Host ""

if (-not $Force) {
    $confirm = Read-Host "This will DELETE all deployed resources (AKS, VNet, Identity, OpenAI) for the teams listed above. Continue? (y/N)"
    if ($confirm -ne 'y') {
        Write-Host "Cancelled." -ForegroundColor Yellow
        return
    }
}

$jobs = @()

foreach ($t in $teams) {
    $teamName = $t.name
    $rgName = if ($t.PSObject.Properties.Name -contains 'rgName' -and -not [string]::IsNullOrWhiteSpace($t.rgName)) {
        $t.rgName
    } else {
        "$rgPrefix$teamName"
    }

    Write-Host "Starting cleanup for team '$teamName' -> $rgName" -ForegroundColor Yellow

    $jobs += Start-Job -Name $teamName -ScriptBlock {
        param($rg, $sub)

        $resources = az resource list --resource-group $rg --subscription $sub --query "[].id" -o tsv 2>&1
        if ($LASTEXITCODE -ne 0 -or -not $resources) {
            return "No resources found in $rg"
        }

        foreach ($id in ($resources -split "`n")) {
            $id = $id.Trim()
            if ($id) {
                az resource delete --ids $id --subscription $sub 2>&1 | Out-Null
            }
        }

        return "Cleaned $rg"
    } -ArgumentList $rgName, $subscription
}

Write-Host "`nWaiting for all cleanups to complete..." -ForegroundColor Cyan

$results = $jobs | Wait-Job | Receive-Job

Write-Host "`n=== Cleanup Results ===" -ForegroundColor Cyan

foreach ($job in $jobs) {
    $status = if ($job.State -eq "Completed") { "OK" } else { "FAILED" }
    $color = if ($status -eq "OK") { "Green" } else { "Red" }
    Write-Host "  $($job.Name): $status" -ForegroundColor $color
}

$jobs | Remove-Job -Force

Write-Host "`nDone. Resource groups were preserved (only contents deleted).`n" -ForegroundColor Cyan
