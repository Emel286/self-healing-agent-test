using 'main.bicep'

// ---------- General ----------
// Change the team name suffix to match your assigned resource group
// Teams: apex, bolt, core, edge, forge, gauge, index, koda, link, mira, nova
param location = 'westeurope'
param namePrefix = 'shk8s-apex'

// ---------- Networking ----------
param vnetAddressPrefix = '10.0.0.0/16'
param aksSubnetAddressPrefix = '10.0.0.0/22'
param aksSubnetName = 'snet-aks'
param networkPlugin = 'azure'
param networkPolicy = 'azure'

// ---------- AKS ----------
param kubernetesVersion = '1.34'
param systemNodeVmSize = 'Standard_D2s_v3'
param systemNodeCount = 3

// ---------- Azure OpenAI ----------
param openaiLocation = 'westeurope'
param openaiModelName = 'gpt-4o-mini'

// ---------- Tags ----------
param tags = {
  environment: 'dev'
  project: 'aks-workshop'
}
