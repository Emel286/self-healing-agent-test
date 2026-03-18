# Cost & Security Considerations

> **This workshop is not production-ready.** The infrastructure and configurations are intentionally simplified to reduce setup friction and focus on learning objectives. Do not deploy this configuration as-is in production environments.

---

## Cost Considerations

This workshop deploys billable Azure resources. The estimates below are provided for **awareness and planning purposes only** — actual costs depend on your Azure region, pricing tier, negotiated discounts, and usage patterns. **Always verify current pricing with your Azure administrator or the [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/) before deploying.**

### Per-team cost estimate

| Resource | SKU | Estimated Cost | Notes |
|----------|-----|---------------|-------|
| **AKS Cluster** | 3x Standard_D2s_v3 (2 vCPU, 8 GiB) | ~$0.30/hr ($7.20/day) | Control plane is free; you only pay for VMs |
| **Azure OpenAI** | S0 + gpt-4o-mini (GlobalStandard) | ~$0.01–0.05/lab run | Pay-per-token; Lab 3 uses ~2K-5K tokens per diagnosis call |
| **Virtual Network** | Standard | Free | No charge for VNet or subnets |
| **Managed Identity** | — | Free | No charge for user-assigned identities |
| **Public IP** (AKS load balancer) | Standard | ~$0.005/hr | Created automatically by AKS |

> **Important:** These are approximate figures based on pay-as-you-go pricing at the time of writing. Multiply per-team costs by the number of teams to estimate total workshop cost. Consult your organization's cloud team for accurate projections.

### Cost optimization tips

- **Stop clusters when not in use** — this deallocates the VMs and stops compute charges:
  ```powershell
  $teamName = "apex"
  az aks stop --resource-group "rg-hackathon-self-healing-k8s-agent-$teamName" --name "shk8s-$teamName-aks"
  ```
- **Delete resources when done** with all labs:
  ```powershell
  .\delete-all.ps1
  ```
- The AKS node pool has autoscaling (1–5 nodes) — idle clusters scale down to 1 node
- Prometheus retention is set to 2h to minimize storage on the small VMs
- Azure OpenAI uses `gpt-4o-mini` (lowest cost model) with 1K TPM capacity

---

## Security Considerations

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

### Production hardening checklist

- [ ] Enable private cluster or API server authorized IP ranges
- [ ] Enable Azure DDoS Protection
- [ ] Use Azure Container Registry with private endpoints
- [ ] Integrate Azure Key Vault for secrets management
- [ ] Enable Azure Monitor Container Insights
- [ ] Enable Defender for Containers
- [ ] Enable automatic node OS upgrades
- [ ] Review and apply network policies
- [ ] Replace Helm-managed Grafana with Azure Managed Grafana
- [ ] Configure pod security standards (restricted)

> **Next step:** If you plan to move any of these patterns to production, work with your organization's security and platform teams to apply your company's security baselines. The [Azure Well-Architected Framework — Security pillar](https://learn.microsoft.com/azure/well-architected/security/) provides comprehensive guidance.
