# infra-devai-hackathon

Azure Kubernetes Service (AKS) infrastructure deployed using **Bicep** (Infrastructure as Code) on **Azure**. This repository serves as a **hackathon platform** with hands-on labs for learning AKS operations, resiliency, and best practices.

> **Disclaimer:** This workshop is designed for **learning and experimentation purposes only**. The infrastructure, scripts, and configurations provided are not intended for production use. Security controls have been simplified to reduce friction during the labs. Before adapting any of this material for production workloads, review the [Security Considerations](#security-considerations) section and consult your organization's cloud security and compliance teams.

## Hackathon Labs

| Lab | Topic | Description |
|-----|-------|-------------|
| [Lab 1](labs/lab1-resiliency/) | **AKS Resiliency & Failure Basics** | Health probes, self-healing, node auto-repair, Pod Disruption Budgets |
| [Lab 2](labs/lab2-devai-diagnosis/) | **Agent-Assisted Diagnosis (DevAI)** | AI-powered troubleshooting, YAML generation, context engineering |
| [Lab 3](labs/lab3-sre-agent/) | **End-to-End SRE Agent Flow** | Multi-agent detect → diagnose → remediate pipeline, observability, automated remediation |

> Complete the infrastructure deployment below before starting the labs.

## Overview

This project provisions the following Azure resources in the **West Europe (Netherlands)** region:

| Resource | Description |
|----------|-------------|
| **Resource Group** | Container for all deployed resources |
| **Virtual Network** | Network isolation with a dedicated AKS subnet |
| **User-Assigned Managed Identity** | Identity used by AKS to interact with Azure resources |
| **AKS Cluster** | Managed Kubernetes cluster with a system node pool |

## Project Structure

```
.
├── main.bicep            # Main orchestration template (subscription-level)
├── main.bicepparam       # Parameter values for the deployment
├── bicepconfig.json      # Bicep configuration file
├── README.md             # This file
└── modules/
    ├── network.bicep     # Virtual Network + AKS subnet
    ├── identity.bicep    # User-assigned managed identity
    └── aks.bicep         # AKS cluster with system node pool
```

## Prerequisites

Before deploying, ensure you have the following installed and configured:

1. **Azure CLI** (v2.60+)
   ```powershell
   # Install via winget
   winget install Microsoft.AzureCLI

   # Verify
   az --version
   ```

2. **Bicep CLI** (bundled with Azure CLI)
   ```powershell
   az bicep install
   az bicep version
   ```

3. **kubectl and kubelogin** (for post-deployment cluster access)
   ```powershell
   az aks install-cli
   ```
   > **Note:** After installation, restart your terminal or update PATH manually:
   > ```powershell
   > $env:PATH += ";$env:USERPROFILE\.azure-kubectl;$env:USERPROFILE\.azure-kubelogin"
   > ```

4. **Azure subscription** with **Contributor** role (or higher)
   ```powershell
   # Verify your role
   az role assignment list --assignee "<your-email>" --output table
   ```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `location` | `westeurope` | Azure region for all resources |
| `resourceGroupName` | — | Name of the resource group to create |
| `namePrefix` | — | Prefix for all resource names |
| `vnetAddressPrefix` | `10.0.0.0/16` | VNet address space (CIDR) |
| `aksSubnetAddressPrefix` | `10.0.0.0/22` | AKS subnet address prefix (CIDR) |
| `aksSubnetName` | `snet-aks` | Name of the AKS subnet |
| `enableDdosProtection` | `false` | Enable DDoS protection on VNet |
| `networkPlugin` | `azure` | AKS network plugin (`azure` or `kubenet`) |
| `networkPolicy` | `azure` | AKS network policy (`azure`, `calico`, or `none`) |
| `serviceCidr` | `172.16.0.0/16` | Kubernetes internal service CIDR |
| `dnsServiceIP` | `172.16.0.10` | DNS service IP (within serviceCidr) |
| `kubernetesVersion` | `1.34` | Kubernetes version |
| `systemNodeVmSize` | `Standard_D2s_v3` | VM size for system node pool |
| `systemNodeCount` | `3` | Number of nodes in system node pool |
| `tags` | `{}` | Tags applied to all resources |

## Step-by-Step Deployment Guide

### Step 1 — Login to Azure

```powershell
az login
```

### Step 2 — Select your subscription

```powershell
# List available subscriptions
az account list --output table

# Set the target subscription
az account set --subscription "<subscription-id-or-name>"

# Verify
az account show --output table
```

### Step 3 — Customize parameters (optional)

Edit `main.bicepparam` to adjust resource names, region, networking, or AKS settings.

### Step 4 — Validate the template (dry run)

```powershell
az deployment sub validate `
  --location westeurope `
  --template-file main.bicep `
  --parameters main.bicepparam
```

### Step 5 — Preview changes (What-If)

```powershell
az deployment sub what-if `
  --location westeurope `
  --template-file main.bicep `
  --parameters main.bicepparam
```

> **Note:** You may see a `NestedDeploymentShortCircuited` warning for the AKS module. This is expected — `what-if` cannot evaluate cross-module references until resources exist.

### Step 6 — Deploy

```powershell
az deployment sub create `
  --location westeurope `
  --template-file main.bicep `
  --parameters main.bicepparam `
  --name devai-hackathon-deployment
```

> The `--location` flag specifies where the deployment metadata is stored, not where resources are created (that's controlled by the `location` parameter).

### Step 7 — Assign AKS RBAC role

Since the cluster uses Azure RBAC for Kubernetes authorization, assign yourself the cluster admin role:

```powershell
$userId = az ad signed-in-user show --query id -o tsv
$aksId = az aks show --resource-group rg-devai-hackathon --name devai-hackathon-aks --query id -o tsv

az role assignment create `
  --assignee $userId `
  --role "Azure Kubernetes Service RBAC Cluster Admin" `
  --scope $aksId
```

> Role propagation may take 1–2 minutes.

### Step 8 — Connect to the AKS cluster

```powershell
# Fetch credentials
az aks get-credentials --resource-group rg-devai-hackathon --name devai-hackathon-aks

# Convert kubeconfig to use Azure CLI authentication
kubelogin convert-kubeconfig -l azurecli
```

## Post-Deployment Validation

Run the following commands to verify the deployment was successful:

```powershell
# Verify the resource group exists
az group show --name rg-devai-hackathon --output table

# Verify the AKS cluster is running
az aks show --resource-group rg-devai-hackathon --name devai-hackathon-aks --query "powerState" -o tsv

# List cluster nodes
kubectl get nodes

# Check system pods are running
kubectl get pods -n kube-system

# Verify cluster info
kubectl cluster-info

# Check AKS networking (VNet)
az network vnet show --resource-group rg-devai-hackathon --name devai-hackathon-vnet --output table

# Check managed identity
az identity show --resource-group rg-devai-hackathon --name devai-hackathon-aks-identity --output table
```

## Cluster Management

```powershell
# Stop the cluster (saves costs when not in use)
az aks stop --resource-group rg-devai-hackathon --name devai-hackathon-aks

# Start the cluster
az aks start --resource-group rg-devai-hackathon --name devai-hackathon-aks

# Check cluster power state
az aks show --resource-group rg-devai-hackathon --name devai-hackathon-aks --query "powerState" -o tsv
```

## Cost Considerations

This workshop deploys billable Azure resources. The estimates below are provided for **awareness and planning purposes only** — actual costs depend on your Azure region, pricing tier, negotiated discounts, and usage patterns. **Always verify current pricing with your Azure administrator or the [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/) before deploying.**

| Resource | SKU | Estimated Cost | Notes |
|----------|-----|---------------|-------|
| **AKS Cluster** | 3x Standard_D2s_v3 (2 vCPU, 8 GiB) | ~$0.30/hr ($7.20/day) | The cluster control plane is free; you only pay for VMs |
| **Azure OpenAI** | S0 + gpt-4o-mini (GlobalStandard) | ~$0.01–0.05/lab run | Pay-per-token; Lab 3 uses ~2K-5K tokens per diagnosis call |
| **Virtual Network** | Standard | Free | No charge for VNet or subnets |
| **Managed Identity** | — | Free | No charge for user-assigned identities |
| **Public IP** (AKS load balancer) | Standard | ~$0.005/hr | Created automatically by AKS |

> **Important:** These are approximate figures based on pay-as-you-go pricing at the time of writing. Consult your organization's cloud team or Azure account representative for accurate cost projections specific to your environment.

### Cost optimization tips

- **Stop the cluster** when not in use — this deallocates the VMs and stops compute charges:
  ```powershell
  az aks stop --resource-group rg-devai-hackathon --name devai-hackathon-aks
  ```
- **Delete the resource group** when done with all labs to remove everything:
  ```powershell
  az group delete --name rg-devai-hackathon --yes --no-wait
  ```
- The AKS node pool has autoscaling (1–5 nodes) — idle clusters scale down to 1 node
- Prometheus retention is set to 2h to minimize storage on the small VMs
- Azure OpenAI uses `gpt-4o-mini` (lowest cost model) with 1K TPM capacity

## Security Considerations

> **This workshop is not production-ready.** The infrastructure and configurations are intentionally simplified to reduce setup friction and focus on learning objectives. Do not deploy this configuration as-is in production environments. The tables below describe what security measures are in place and what should be hardened before any production use.

This infrastructure is designed for **workshop/hackathon use** and uses security defaults appropriate for a learning environment.

### What's secure by default

| Area | Implementation | Details |
|------|---------------|--------|
| **Authentication** | Microsoft Entra ID | AKS uses Azure RBAC for Kubernetes authorization — no static kubeconfig tokens |
| **OpenAI auth** | Entra ID (token-based) | `disableLocalAuth=true` — API keys are disabled, authentication uses `AzureCliCredential` |
| **Identity** | User-assigned managed identity | AKS control plane uses a managed identity instead of a service principal |
| **Network plugin** | Azure CNI | Pods get VNet IPs, enabling NSG rules and Azure network policies |
| **Network policy** | Azure | Pod-to-pod traffic can be restricted with Kubernetes NetworkPolicy resources |
| **RBAC** | Azure RBAC | Cluster access is role-based — "Azure Kubernetes Service RBAC Cluster Admin" role required |

### Workshop simplifications (review for production)

| Area | Workshop Setting | Production Recommendation |
|------|-----------------|---------------------------|
| **API server** | Public endpoint | Enable [private cluster](https://learn.microsoft.com/azure/aks/private-clusters) or authorized IP ranges |
| **Grafana password** | `admin` (hardcoded in Helm) | Use Azure Managed Grafana or a Kubernetes Secret with a strong password |
| **DDoS protection** | Disabled | Enable Azure DDoS Protection for internet-facing workloads |
| **Container registry** | Public images (nginx) | Use Azure Container Registry with private endpoint and image scanning |
| **Secrets management** | Environment variables | Use Azure Key Vault with the [AKS Secrets Store CSI driver](https://learn.microsoft.com/azure/aks/csi-secrets-store-driver) |
| **Logging** | Prometheus only (local) | Enable [Azure Monitor Container Insights](https://learn.microsoft.com/azure/azure-monitor/containers/container-insights-overview) for centralized logging |
| **Node OS** | Default (Ubuntu/AzureLinux) | Enable automatic node OS upgrades and [Defender for Containers](https://learn.microsoft.com/azure/defender-for-cloud/defender-for-containers-introduction) |

> **Next step:** If you plan to move any of these patterns to production, work with your organization's security and platform teams to apply your company's security baselines. The [Azure Well-Architected Framework — Security pillar](https://learn.microsoft.com/azure/well-architected/security/) provides comprehensive guidance.

## Cleanup

To delete all deployed resources:

```powershell
az group delete --name rg-devai-hackathon --yes --no-wait
```

> Since all resources reside in a single resource group, deleting it removes everything.
