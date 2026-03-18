// ============================================================================
// Main Bicep template - Resource Group-level deployment
// Deploys: Virtual Network, Managed Identity, Azure OpenAI, and AKS Cluster
// Region: West Europe (The Netherlands)
// ============================================================================

// ---------- General Parameters ----------

@description('Azure region for all resources (default: West Europe / The Netherlands)')
param location string = 'westeurope'

@description('Name prefix used to generate unique resource names across modules')
param namePrefix string

@description('Tags applied to all resources for cost tracking and organization')
param tags object = {}

// ---------- Networking Parameters ----------

@description('Address space (CIDR) for the Virtual Network')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('Address prefix (CIDR) for the AKS node subnet')
param aksSubnetAddressPrefix string = '10.0.0.0/22'

@description('Name of the AKS subnet inside the VNet')
param aksSubnetName string = 'snet-aks'

@description('Enable DDoS protection on the VNet (adds cost)')
param enableDdosProtection bool = false

@description('Network plugin for AKS (azure or kubenet)')
@allowed(['azure', 'kubenet'])
param networkPlugin string = 'azure'

@description('Network policy for AKS (azure, calico, or none)')
@allowed(['azure', 'calico', 'none'])
param networkPolicy string = 'azure'

@description('Service CIDR for Kubernetes internal services')
param serviceCidr string = '172.16.0.0/16'

@description('DNS service IP (must be within serviceCidr range)')
param dnsServiceIP string = '172.16.0.10'

// ---------- Azure OpenAI Parameters ----------

@description('Azure region for Azure OpenAI')
param openaiLocation string = 'westeurope'

@description('Name of the GPT model to deploy (e.g., gpt-4o-mini, gpt-4o)')
param openaiModelName string = 'gpt-4o-mini'

@description('Version of the GPT model to deploy. Leave empty for latest default.')
param openaiModelVersion string = ''

@description('Token-per-minute capacity for the model deployment (in thousands). 1 = 1K TPM.')
param openaiDeploymentCapacity int = 1

// ---------- AKS Parameters ----------

@description('Kubernetes version to deploy')
param kubernetesVersion string = '1.34'

@description('VM size for the system node pool')
param systemNodeVmSize string = 'Standard_D2s_v3'

@description('Initial number of nodes in the system node pool')
@minValue(1)
@maxValue(50)
param systemNodeCount int = 3

// ---------- Module: Networking ----------
// Deploys a Virtual Network with a dedicated AKS subnet.
// The VNet provides network isolation and the subnet is used by AKS node pools.

module network 'modules/network.bicep' = {
  name: 'network-deployment'
  params: {
    location: location
    namePrefix: namePrefix
    vnetAddressPrefix: vnetAddressPrefix
    aksSubnetAddressPrefix: aksSubnetAddressPrefix
    aksSubnetName: aksSubnetName
    enableDdosProtection: enableDdosProtection
    tags: tags
  }
}

// ---------- Module: Identity ----------
// Deploys a user-assigned managed identity for the AKS cluster.
// This identity is used by AKS to interact with Azure resources (e.g., load balancers, disks).

module identity 'modules/identity.bicep' = {
  name: 'identity-deployment'
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

// ---------- Module: Azure OpenAI ----------
// Deploys an Azure OpenAI account with a GPT model deployment.
// Used by the Lab 3 SRE diagnosis agent for AI-powered root cause analysis.

module openai 'modules/openai.bicep' = {
  name: 'openai-deployment'
  params: {
    location: openaiLocation
    namePrefix: namePrefix
    modelName: openaiModelName
    modelVersion: openaiModelVersion
    deploymentCapacity: openaiDeploymentCapacity
    tags: tags
  }
}

// ---------- Module: AKS ----------
// Deploys an Azure Kubernetes Service cluster with a system node pool.
// Depends on the network module (for the subnet) and identity module (for the managed identity).

module aks 'modules/aks.bicep' = {
  name: 'aks-deployment'
  params: {
    location: location
    clusterName: '${namePrefix}-aks'
    dnsPrefix: namePrefix
    subnetId: network.outputs.aksSubnetId
    identityId: identity.outputs.identityId
    kubernetesVersion: kubernetesVersion
    systemNodeVmSize: systemNodeVmSize
    systemNodeCount: systemNodeCount
    networkPlugin: networkPlugin
    networkPolicy: networkPolicy
    serviceCidr: serviceCidr
    dnsServiceIP: dnsServiceIP
    tags: tags
  }
}

// ---------- Outputs ----------
// Values exported for use by CI/CD pipelines or subsequent deployments.

@description('Name of the deployed AKS cluster')
output aksClusterName string = aks.outputs.clusterName

@description('FQDN of the AKS cluster API server')
output aksClusterFqdn string = aks.outputs.clusterFqdn

@description('Name of the deployed Virtual Network')
output vnetName string = network.outputs.vnetName

@description('Client ID of the managed identity assigned to AKS')
output identityClientId string = identity.outputs.clientId

@description('Azure OpenAI endpoint URL')
output openaiEndpoint string = openai.outputs.endpoint

@description('Azure OpenAI model deployment name')
output openaiDeploymentName string = openai.outputs.deploymentName

@description('Azure OpenAI account name (for key retrieval via az CLI)')
output openaiAccountName string = openai.outputs.accountName
