# Self-Healing Kubernetes Agents — DevAI Hackathon

## About This Hackathon

This is an **instructor-led hackathon** designed for teams who want to learn how to operate, troubleshoot, and automate Kubernetes workloads on Azure using AI-powered tools. A facilitator guides participants through three progressive labs — from Kubernetes resiliency fundamentals, to AI-assisted diagnosis with GitHub Copilot and Azure Copilot, to building a multi-agent SRE pipeline that detects, diagnoses, and remediates incidents automatically.

**Infrastructure is pre-provisioned by the facilitator** before the hackathon begins. Each team receives their own isolated Azure environment (AKS cluster + Azure OpenAI instance) so they can focus entirely on the labs without worrying about setup. Attendees only need Azure CLI, `kubectl`, and a terminal to get started.

> **Disclaimer:** This hackathon is designed for **learning and experimentation purposes only**. The infrastructure and configurations are not intended for production use — security controls have been simplified to reduce friction during the labs. See [Cost & Security Considerations](considerations/) for production hardening guidance.

## Hackathon Labs

| Lab | Topic | What You'll Do |
|-----|-------|----------------|
| [Lab 1](labs/lab1-resiliency/) | **AKS Resiliency & Failure Basics** | Configure health probes, observe self-healing, test Pod Disruption Budgets |
| [Lab 2](labs/lab2-devai-diagnosis/) | **Agent-Assisted Diagnosis (DevAI)** | Deploy broken workloads, use AI to diagnose and fix them, practice context engineering |
| [Lab 3](labs/lab3-sre-agent/) | **End-to-End SRE Agent Flow** | Build a multi-agent detect → diagnose → remediate pipeline in Python |

## Getting Started (Attendees)

Your facilitator has already provisioned your team's environment. Connect to your cluster and start the labs:

```powershell
# 1. Login to Azure
az login

# 2. Get your cluster credentials (replace <team> with your team name, e.g. apex)
az aks get-credentials `
  --resource-group rg-hackathon-self-healing-k8s-agent-<team> `
  --name shk8s-<team>-aks

# 3. Enable Azure CLI-based authentication
kubelogin convert-kubeconfig -l azurecli

# 4. Verify connectivity
kubectl get nodes
```

Then start with **[Lab 1 — AKS Resiliency & Failure Basics](labs/lab1-resiliency/)** and work through the labs in order.

> See the [Attendee Guide](ATTENDEE-GUIDE.md) for a full overview of topics, tech stack, and learning outcomes.

## Project Structure

```
.
├── labs/
│   ├── lab1-resiliency/          # Lab 1 — Health probes, self-healing, PDBs
│   │   └── solutions/manifests/  #   Solution YAMLs (healthy app, liveness, readiness, PDB)
│   ├── lab2-devai-diagnosis/     # Lab 2 — AI-assisted troubleshooting
│   │   └── solutions/manifests/  #   Broken + fixed YAMLs (CrashLoop, ImagePull, resource limits)
│   └── lab3-sre-agent/           # Lab 3 — Multi-agent SRE pipeline
│       └── solutions/
│           ├── manifests/        #   Test workloads (degrading app)
│           └── scripts/          #   Python agents (detection, diagnosis, remediation, orchestrator)
├── ATTENDEE-GUIDE.md             # One-pager for participants
├── considerations/               # Cost & security deep-dive
│
├── main.bicep                    # Infrastructure deployment (Bicep)
├── modules/                      # Bicep modules (AKS, OpenAI, network, identity)
├── deploy-all.ps1                # Deploy all teams
├── delete-all.ps1                # Cleanup all teams
└── teams.json                    # Team config (gitignored)
```

---

## Infrastructure Setup (Facilitators)

Everything below is for **facilitators** provisioning team environments. Attendees can skip to [Getting Started](#getting-started-attendees).

### Prerequisites

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

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `location` | `westeurope` | Azure region for all resources |
| `namePrefix` | — | Prefix for all resource names (e.g., `shk8s-apex`) |
| `kubernetesVersion` | `1.34` | Kubernetes version |
| `systemNodeVmSize` | `Standard_D2s_v3` | VM size for system node pool |
| `systemNodeCount` | `3` | Number of nodes in system node pool |

See `main.bicepparam` for the full list of parameters (networking, CIDR ranges, tags, etc.).

### Deployment

#### Step 1 — Login to Azure

```powershell
az login
```

#### Step 2 — Select your subscription

```powershell
# List available subscriptions
az account list --output table

# Set the target subscription
az account set --subscription "<subscription-id-or-name>"

# Verify
az account show --output table
```

#### Step 3 — Deploy a single team

```powershell
$teamName = "apex"
$rgName = "rg-hackathon-self-healing-k8s-agent-$teamName"

az deployment group create `
  --resource-group $rgName `
  --template-file main.bicep `
  --parameters main.bicepparam `
  --parameters namePrefix="shk8s-$teamName" `
  --name "deploy-$teamName"
```

Or deploy **all teams** at once using the helper script:

```powershell
.\deploy-all.ps1
```

#### Step 4 — Assign AKS RBAC roles

Each attendee needs the cluster admin role on their team's AKS cluster:

```powershell
$userId = az ad signed-in-user show --query id -o tsv
$aksId = az aks show --resource-group $rgName --name "shk8s-$teamName-aks" --query id -o tsv

az role assignment create `
  --assignee $userId `
  --role "Azure Kubernetes Service RBAC Cluster Admin" `
  --scope $aksId
```

> Role propagation may take 1–2 minutes.

### Post-Deployment Validation

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

### Cluster Management

```powershell
$teamName = "apex"
$rgName = "rg-hackathon-self-healing-k8s-agent-$teamName"
$aksName = "shk8s-$teamName-aks"

# Stop the cluster (saves costs)
az aks stop --resource-group $rgName --name $aksName

# Start the cluster
az aks start --resource-group $rgName --name $aksName
```

### Cost & Security Considerations

> **This workshop is not production-ready.** The infrastructure is intentionally simplified for learning purposes.

- **Cost**: Each team's AKS cluster costs ~$0.30/hr (~$7.20/day). Stop clusters when not in use. Azure OpenAI costs ~$0.01–0.05 per lab run.
- **Security**: Entra ID authentication is enabled by default (no API keys). The API server is publicly accessible — use private clusters for production.

For detailed cost breakdowns, security baselines, and production hardening guidance, see the **[considerations/](considerations/)** folder.

### Cleanup

```powershell
# Delete resources for all teams
.\delete-all.ps1

# Delete resources for a single team
.\delete-all.ps1 -Team apex
```

> This deletes the deployed resources (AKS, VNet, identity, OpenAI) inside each team's resource group, not the resource groups themselves.
