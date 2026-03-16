// ============================================================================
// Module: AKS (Azure Kubernetes Service)
// Deploys a managed Kubernetes cluster with a system node pool.
// Uses Azure CNI for networking and Entra ID (AAD) integration for RBAC.
// ============================================================================

// ---------- Parameters ----------

@description('Azure region where the AKS cluster will be deployed')
param location string

@description('Name of the AKS cluster resource')
param clusterName string

@description('DNS prefix for the AKS API server FQDN')
param dnsPrefix string

@description('Resource ID of the subnet where AKS nodes will be placed')
param subnetId string

@description('Resource ID of the user-assigned managed identity for the cluster')
param identityId string

@description('Kubernetes version to deploy (e.g., 1.34)')
param kubernetesVersion string = '1.34'

@description('VM size for the system node pool (runs core system pods)')
param systemNodeVmSize string = 'Standard_D2s_v3'

@description('Initial number of nodes in the system node pool')
@minValue(1)
@maxValue(50)
param systemNodeCount int = 3

@description('Network plugin for AKS (azure = Azure CNI, kubenet = basic)')
@allowed(['azure', 'kubenet'])
param networkPlugin string = 'azure'

@description('Network policy enforcement (azure, calico, or none)')
@allowed(['azure', 'calico', 'none'])
param networkPolicy string = 'azure'

@description('Service CIDR for Kubernetes internal services (must not overlap with VNet)')
param serviceCidr string = '172.16.0.0/16'

@description('DNS service IP address (must be within serviceCidr range)')
param dnsServiceIP string = '172.16.0.10'

@description('Tags to apply to the AKS cluster')
param tags object = {}

// ---------- Resources ----------

// AKS Managed Cluster - the core Kubernetes control plane and node pool
resource aksCluster 'Microsoft.ContainerService/managedClusters@2024-06-02-preview' = {
  name: clusterName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    dnsPrefix: dnsPrefix
    kubernetesVersion: kubernetesVersion

    // Network configuration - controls how pods and services communicate
    networkProfile: {
      networkPlugin: networkPlugin
      networkPolicy: networkPolicy
      serviceCidr: serviceCidr
      dnsServiceIP: dnsServiceIP
    }

    // System node pool - runs essential Kubernetes system pods (CoreDNS, metrics-server, etc.)
    agentPoolProfiles: [
      {
        name: 'systempool'
        count: systemNodeCount
        vmSize: systemNodeVmSize
        osType: 'Linux'
        mode: 'System'
        vnetSubnetID: subnetId
        enableAutoScaling: true
        minCount: 1
        maxCount: 5
      }
    ]

    // Entra ID (Azure AD) integration for Kubernetes RBAC
    aadProfile: {
      managed: true
      enableAzureRBAC: true
    }
    enableRBAC: true
  }
}

// ---------- Outputs ----------

@description('The name of the deployed AKS cluster')
output clusterName string = aksCluster.name

@description('The FQDN of the AKS API server')
output clusterFqdn string = aksCluster.properties.fqdn

@description('The resource ID of the AKS cluster')
output clusterId string = aksCluster.id
