<#
.SYNOPSIS
    Deploys hackathon infrastructure to all team resource groups in parallel.

.DESCRIPTION
    Reads team configuration from teams.json and deploys the Bicep template
    to each team's pre-existing resource group. Deployments run in parallel.

.PARAMETER TeamsFile
    Path to the teams configuration JSON file. Defaults to teams.json.

.PARAMETER TemplateFile
    Path to the Bicep template. Defaults to main.bicep.

.PARAMETER ParametersFile
    Path to the Bicep parameters file. Defaults to main.bicepparam.

.PARAMETER Team
    Optional. Deploy to a single team only (e.g., "apex").

.EXAMPLE
    # Deploy to all teams
    .\deploy-all.ps1

    # Deploy to a single team
    .\deploy-all.ps1 -Team bolt
#>

param(
    [string]$TeamsFile = "teams.json",
    [string]$TemplateFile = "main.bicep",
    [string]$ParametersFile = "main.bicepparam",
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

$teams = if ($Team) { @($Team) } else { $config.teams | ForEach-Object { $_.name } }

Write-Host "`n=== Hackathon Deployment ===" -ForegroundColor Cyan
Write-Host "Subscription: $subscription"
Write-Host "Teams: $($teams -join ', ')"
Write-Host "Template: $TemplateFile"
Write-Host ""

$jobs = @()

foreach ($t in $teams) {
    $rgName = "$rgPrefix-$t"
    $prefix = "$namePrefix-$t"
    $deployName = "$t-deployment"

    Write-Host "Starting deployment for team '$t' -> $rgName" -ForegroundColor Yellow

    $jobs += Start-Job -Name $t -ScriptBlock {
        param($rg, $template, $params, $prefix, $sub, $deployName)
        az deployment group create `
            --resource-group $rg `
            --template-file $template `
            --parameters $params `
            --parameters namePrefix=$prefix `
            --subscription $sub `
            --name $deployName `
            --output json 2>&1
    } -ArgumentList $rgName, $TemplateFile, $ParametersFile, $prefix, $subscription, $deployName
}

Write-Host "`nWaiting for all deployments to complete..." -ForegroundColor Cyan

$results = $jobs | Wait-Job | Receive-Job

Write-Host "`n=== Deployment Results ===" -ForegroundColor Cyan

foreach ($job in $jobs) {
    $status = if ($job.State -eq "Completed") { "OK" } else { "FAILED" }
    $color = if ($status -eq "OK") { "Green" } else { "Red" }
    Write-Host "  $($job.Name): $status" -ForegroundColor $color
}

$jobs | Remove-Job -Force

Write-Host "`nDone.`n" -ForegroundColor Cyan
