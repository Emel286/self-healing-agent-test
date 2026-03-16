// ============================================================================
// Module: Networking
// Deploys a Virtual Network with a dedicated subnet for AKS nodes.
// The VNet provides network isolation for the Kubernetes cluster.
// ============================================================================

// ---------- Parameters ----------

@description('Azure region where networking resources will be deployed')
param location string

@description('Name prefix used to generate resource names (e.g., <prefix>-vnet)')
param namePrefix string

@description('Address space (CIDR) for the Virtual Network')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('Address prefix (CIDR) for the AKS node subnet')
param aksSubnetAddressPrefix string = '10.0.0.0/22'

@description('Name of the AKS subnet')
param aksSubnetName string = 'snet-aks'

@description('Enable Azure DDoS Protection on the VNet')
param enableDdosProtection bool = false

@description('Tags to apply to all networking resources')
param tags object = {}

// ---------- Resources ----------

// Virtual Network - provides the network backbone for AKS and other services
resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: '${namePrefix}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    enableDdosProtection: enableDdosProtection
    subnets: [
      {
        // Subnet dedicated to AKS node pools
        name: aksSubnetName
        properties: {
          addressPrefix: aksSubnetAddressPrefix
        }
      }
    ]
  }
}

// ---------- Outputs ----------

@description('The resource ID of the Virtual Network')
output vnetId string = vnet.id

@description('The name of the Virtual Network')
output vnetName string = vnet.name

@description('The resource ID of the AKS subnet')
output aksSubnetId string = vnet.properties.subnets[0].id
