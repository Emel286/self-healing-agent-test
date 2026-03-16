// ============================================================================
// Module: Identity
// Deploys a user-assigned managed identity for AKS.
// This identity allows the AKS cluster to authenticate to Azure services
// (e.g., pulling images from ACR, managing load balancers, attaching disks).
// ============================================================================

// ---------- Parameters ----------

@description('Azure region where the managed identity will be created')
param location string

@description('Name prefix used to generate the identity name (e.g., <prefix>-aks-identity)')
param namePrefix string

@description('Tags to apply to the managed identity')
param tags object = {}

// ---------- Resources ----------

// User-assigned managed identity for the AKS control plane
resource aksIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-aks-identity'
  location: location
  tags: tags
}

// ---------- Outputs ----------

@description('The resource ID of the managed identity')
output identityId string = aksIdentity.id

@description('The principal (object) ID — used for role assignments')
output principalId string = aksIdentity.properties.principalId

@description('The client (application) ID — used in workload identity configurations')
output clientId string = aksIdentity.properties.clientId
