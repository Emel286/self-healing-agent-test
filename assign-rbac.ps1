<#
.SYNOPSIS
    Assigns AKS RBAC Cluster Admin role to each team's AD group.

.DESCRIPTION
    Reads team configuration from teams.json and assigns the
    "Azure Kubernetes Service RBAC Cluster Admin" role to each team's
    AD group, scoped to their AKS cluster.

.PARAMETER TeamsFile
    Path to the teams configuration JSON file. Defaults to teams.json.

.PARAMETER Team
    Optional. Assign role for a single team only (e.g., "apex").

.EXAMPLE
    # Assign RBAC for all teams
    .\assign-rbac.ps1

    # Assign RBAC for a single team
    .\assign-rbac.ps1 -Team apex
#>

param(
    [string]$TeamsFile = "teams.json",
    [string]$Team
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $TeamsFile)) {
    Write-Error "Teams file not found: $TeamsFile"
    return
}

$config = Get-Content $TeamsFile | ConvertFrom-Json
$subscription = $config.subscription
$rgPrefix = $config.rgPrefix
$namePrefix = $config.namePrefix
$role = "Azure Kubernetes Service RBAC Cluster Admin"

$teams = if ($Team) {
    $config.teams | Where-Object { $_.name -eq $Team }
} else {
    $config.teams
}

if (-not $teams) {
    Write-Error "Team '$Team' not found in $TeamsFile"
    return
}

Write-Host "`n=== AKS RBAC Role Assignment ===" -ForegroundColor Cyan
Write-Host "Subscription: $subscription"
Write-Host "Role: $role"
Write-Host "Teams: $(($teams | ForEach-Object { $_.name }) -join ', ')"
Write-Host ""

$succeeded = 0
$failed = 0

foreach ($t in $teams) {
    $teamName = $t.name
    $groupId = $t.groupId
    $rgName = "$rgPrefix-$teamName"
    $aksName = "$namePrefix-$teamName-aks"

    Write-Host "  $teamName : " -NoNewline

    $aksId = az aks show --resource-group $rgName --name $aksName --subscription $subscription --query id -o tsv 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED (cluster not found)" -ForegroundColor Red
        $failed++
        continue
    }

    $result = az role assignment create `
        --assignee $groupId `
        --role $role `
        --scope $aksId `
        --subscription $subscription `
        --output json 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "OK" -ForegroundColor Green
        $succeeded++
    } else {
        Write-Host "FAILED" -ForegroundColor Red
        Write-Host "    $result" -ForegroundColor DarkGray
        $failed++
    }
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "  Succeeded: $succeeded" -ForegroundColor Green
Write-Host "  Failed:    $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })
Write-Host ""
