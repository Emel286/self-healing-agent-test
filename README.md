# infra-devai-hackathon

A hands-on hackathon for teams who want to learn how to operate, troubleshoot, and automate Kubernetes workloads on Azure using AI-powered tools. Through three progressive labs, participants go from understanding AKS resiliency fundamentals, to diagnosing broken workloads with GitHub Copilot and Azure Copilot, to building a multi-agent SRE pipeline that detects, diagnoses, and remediates incidents automatically. This repo contains the Bicep infrastructure templates, deployment scripts, lab guides, and solution code needed to run the hackathon end-to-end.

> **Disclaimer:** This hackathon is designed for **learning and experimentation purposes only**. The infrastructure, scripts, and configurations provided are not intended for production use. Security controls have been simplified to reduce friction during the labs. Before adapting any of this material for production workloads, review the [Cost & Security Considerations](considerations/) and consult your organization's cloud security and compliance teams.

## Hackathon Labs

| Lab | Topic | Description |
|-----|-------|-------------|
| [Lab 1](labs/lab1-resiliency/) | **AKS Resiliency & Failure Basics** | Health probes, self-healing, node auto-repair, Pod Disruption Budgets |
| [Lab 2](labs/lab2-devai-diagnosis/) | **Agent-Assisted Diagnosis (DevAI)** | AI-powered troubleshooting, YAML generation, context engineering |
| [Lab 3](labs/lab3-sre-agent/) | **End-to-End SRE Agent Flow** | Multi-agent detect → diagnose → remediate pipeline, observability, automated remediation |

> Complete the infrastructure deployment below before starting the labs.

## Overview

This project provisions the following Azure resources in the **West Europe (Netherlands)** region into **pre-existing resource groups** (one per team):

| Resource | Description |
|----------|-------------|
| **Virtual Network** | Network isolation with a dedicated AKS subnet |
| **User-Assigned Managed Identity** | Identity used by AKS to interact with Azure resources |
| **AKS Cluster** | Managed Kubernetes cluster with a system node pool |
| **Azure OpenAI** | GPT-4o-mini model for Lab 3 SRE diagnosis agent |

## Project Structure

```
.
├── main.bicep            # Main orchestration template (resource-group-level)
├── main.bicepparam       # Parameter values for the deployment
├── bicepconfig.json      # Bicep configuration file
├── deploy-all.ps1        # Deploy to all teams (or a single team)
├── delete-all.ps1        # Delete resources for all teams (or a single team)
├── teams.json            # Team config (gitignored — sensitive)
├── README.md             # This file
├── considerations/       # Cost & security considerations
│   └── README.md
└── modules/
    ├── network.bicep     # Virtual Network + AKS subnet
    ├── identity.bicep    # User-assigned managed identity
    ├── openai.bicep      # Azure OpenAI + model deployment
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
| `namePrefix` | — | Prefix for all resource names (e.g., `shk8s-apex`) |
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

```powershell
$teamName = "apex"
$rgName = "rg-hackathon-self-healing-k8s-agent-$teamName"
$aksName = "shk8s-$teamName-aks"

# Verify AKS cluster is running
az aks show --resource-group $rgName --name $aksName --query "powerState" -o tsv

# List cluster nodes
kubectl get nodes

# Check system pods
kubectl get pods -n kube-system
```

## Cluster Management

```powershell
$teamName = "apex"
$rgName = "rg-hackathon-self-healing-k8s-agent-$teamName"
$aksName = "shk8s-$teamName-aks"

# Stop the cluster (saves costs)
az aks stop --resource-group $rgName --name $aksName

# Start the cluster
az aks start --resource-group $rgName --name $aksName
```

## Cost & Security Considerations

> **This workshop is not production-ready.** The infrastructure is intentionally simplified for learning purposes.

- **Cost**: Each team's AKS cluster costs ~$0.30/hr (~$7.20/day). Stop clusters when not in use. Azure OpenAI costs ~$0.01–0.05 per lab run.
- **Security**: Entra ID authentication is enabled by default (no API keys). The API server is publicly accessible — use private clusters for production.

For detailed cost breakdowns, security baselines, and production hardening guidance, see the **[considerations/](considerations/)** folder.

## Cleanup

```powershell
# Delete resources for all teams
.\delete-all.ps1

# Delete resources for a single team
.\delete-all.ps1 -Team apex
```

> This deletes the deployed resources (AKS, VNet, identity, OpenAI) inside each team's resource group, not the resource groups themselves.
