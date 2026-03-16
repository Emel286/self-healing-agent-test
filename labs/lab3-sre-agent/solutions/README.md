# Lab 3 — Solutions

## Solution 1 — Set Up Observability

### Step 1: Install Helm (if not already installed)

Helm is required to deploy the Prometheus + Grafana stack. Install it via winget:

```powershell
winget install Helm.Helm --accept-source-agreements --accept-package-agreements
```

> **Note:** If you're in VS Code and Helm was just installed, new terminals may not see it in PATH. Either restart VS Code or add this to your [PowerShell profile](https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_profiles) (`$PROFILE`):
> ```powershell
> $env:PATH = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
> ```

Verify:
```powershell
helm version --short
```

### Step 2: Deploy Prometheus + Grafana

The `kube-prometheus-stack` Helm chart deploys Prometheus, Grafana, and pre-configured alerting rules in a single command.

```powershell
# Add the Prometheus community Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

```powershell
# Install kube-prometheus-stack into a dedicated monitoring namespace
helm install prometheus prometheus-community/kube-prometheus-stack `
  --namespace monitoring `
  --create-namespace `
  --set grafana.adminPassword=admin `
  --set prometheus.prometheusSpec.retention=2h
```

> **Why `retention=2h`?** Our Standard_D2s_v3 node has limited resources. A short retention keeps disk and memory usage low — we only need enough history for the lab exercises.

Wait for all pods to be ready:

```powershell
kubectl get pods -n monitoring -w
```

Expected output — all pods should reach `Running` / `Ready` within 2-3 minutes:
```
NAME                                                     READY   STATUS    RESTARTS   AGE
alertmanager-prometheus-kube-prometheus-alertmanager-0    2/2     Running   0          2m
prometheus-grafana-xxxxx-yyyyy                           3/3     Running   0          2m
prometheus-kube-prometheus-operator-xxxxx-yyyyy           1/1     Running   0          2m
prometheus-kube-state-metrics-xxxxx-yyyyy                 1/1     Running   0          2m
prometheus-prometheus-kube-prometheus-prometheus-0        2/2     Running   0          2m
prometheus-prometheus-node-exporter-xxxxx                 1/1     Running   0          2m
```

### Step 3: Access Grafana

Port-forward Grafana to your local machine:

```powershell
kubectl port-forward svc/prometheus-grafana -n monitoring 3000:80
```

Open [http://localhost:3000](http://localhost:3000) in your browser.
- **Username:** `admin`
- **Password:** `admin`

The stack comes with pre-built Kubernetes dashboards. Navigate to **Dashboards** → **Browse** to explore cluster health, node metrics, and pod resource usage.

### Step 4: Verify metrics collection

In a separate terminal, verify Prometheus is scraping metrics:

```powershell
kubectl top nodes
kubectl top pods -n monitoring
```

### Step 5: Create the lab namespace

```powershell
kubectl create namespace lab3
```

### Event streaming

Kubernetes events can be streamed for automated processing:

```powershell
kubectl get events -n lab3 --watch-only -o json
```

### Discussion Answer

**Key signals for SRE agents:**
1. **Metrics** (Prometheus): CPU, memory, request rates, error rates, latency percentiles
2. **Logs** (stdout/stderr): Application errors, stack traces, startup failures
3. **Events** (Kubernetes): State transitions, scheduling failures, probe failures, OOM kills
4. **Traces** (distributed): Request flow across services, bottleneck identification

**Minimum viable stack for automated response:** Kubernetes events + pod status (kubectl) + container logs. This is enough for 80% of common incidents without deploying additional infrastructure.

---

## Solution 2 — Create an Incident Scenario

### Deploy the degrading application

```powershell
kubectl apply -f labs/lab3-sre-agent/solutions/manifests/02-degrading-app.yaml
```

This deploys an Nginx container with a custom startup script that:
- **Phase 1 (0–60s):** Healthy — serves 200 responses, passes both probes
- **Phase 2 (60–120s):** Starts returning 500 on `/` (but readiness probe still passes)
- **Phase 3 (120s+):** Removes readiness file (503 on `/ready`) and starts consuming memory via `/dev/shm` until OOM-killed

### Monitor the degradation

The app degrades through three phases. Run these commands in separate terminals to observe each transition in real time.

**Terminal 1 — Watch pod status** (keep this running throughout):

```powershell
kubectl get pods -n lab3 -l app=degrading-app -w
```

**Terminal 2 — Watch events:**

```powershell
kubectl get events -n lab3 --watch
```

**Terminal 3 — Stream logs:**

```powershell
kubectl logs -n lab3 -l app=degrading-app -c web -f
```

### What you'll see at each phase

**Phase 1 (0–60s) — Healthy.** Both pods are `1/1 Running` with 0 restarts. Logs show normal nginx access entries:

```
NAME                            READY   STATUS    RESTARTS   AGE
degrading-app-xxxxx-yyyyy       1/1     Running   0          15s
degrading-app-xxxxx-zzzzz       1/1     Running   0          15s
```

Logs show successful probe responses:
```
10.0.0.10 - - "GET /healthz HTTP/1.1" 200 2 "kube-probe/1.34"
10.0.0.10 - - "GET /ready HTTP/1.1" 200 6 "kube-probe/1.34"
```

> Everything looks fine. The liveness probe (`/healthz`) and readiness probe (`/ready`) both return 200.

**Phase 2 (60–120s) — Error responses on `/`.** The nginx config reloads to return 500 on `/`. However, pods still show `1/1 Running` because the readiness probe checks `/ready` (which still works):

```
NAME                            READY   STATUS    RESTARTS   AGE
degrading-app-xxxxx-yyyyy       1/1     Running   0          82s
degrading-app-xxxxx-zzzzz       1/1     Running   0          83s
```

> **Subtle point:** The pod looks healthy from `kubectl get pods`. This simulates a real-world scenario where the app serves errors to users but probes still pass — you'd need Prometheus metrics or log analysis to catch this.

**Phase 3 (120s+) — Readiness failure + memory growth → OOMKill.** The `ready.txt` file is removed (readiness probe returns 503), and a memory hog starts writing to `/dev/shm`. Pods drop to `0/1` READY, then get OOM-killed:

```
NAME                            READY   STATUS             RESTARTS      AGE
degrading-app-xxxxx-yyyyy       0/1     Running            1 (9s ago)    2m37s
degrading-app-xxxxx-zzzzz       0/1     OOMKilled          1             2m38s
```

Events show both the readiness failure and the OOM pattern:
```
Warning  Unhealthy  Readiness probe failed: HTTP probe failed with statuscode: 503
```

After a few more OOM cycles, pods enter `CrashLoopBackOff`:
```
NAME                            READY   STATUS             RESTARTS      AGE
degrading-app-xxxxx-yyyyy       0/1     CrashLoopBackOff   3 (24s ago)   5m
degrading-app-xxxxx-zzzzz       0/1     CrashLoopBackOff   3 (25s ago)   5m
```

Use `kubectl describe` to confirm the OOMKill:

```powershell
kubectl describe pod -n lab3 -l app=degrading-app | Select-String -Pattern 'State:|Reason:|Exit Code:|Restart Count:'
```

Expected output:
```
    State:          Terminated
      Reason:       OOMKilled
      Exit Code:    137
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
    Restart Count:  3
```

> **Key signals:** Exit code 137 = SIGKILL from OOM killer. The memory limit is 64Mi, and the `/dev/shm` writes exceed it. The combined readiness failure (503) + OOMKill (137) + CrashLoopBackOff is exactly the kind of multi-signal incident that detection agents need to pick up.

### Discussion Answer

A realistic incident simulation should:
- **Start healthy**: Let monitoring baselines establish before degradation
- **Degrade gradually**: Real incidents rarely go from perfect to broken instantly
- **Produce multiple signals**: Not just one metric — the combination tells the story
- **Have a clear root cause**: So participants can verify their diagnosis is correct

---

## Solution 3 — Build a Detection Agent

### Reference implementation: `scripts/detection_agent.py`

```powershell
pip install kubernetes
python labs/lab3-sre-agent/solutions/scripts/detection_agent.py
```

The detection agent:
1. Connects to the cluster via kubeconfig
2. Polls pod status every 15 seconds
3. Checks for: CrashLoopBackOff, ImagePullBackOff, Pending, high restarts, unready pods
4. Outputs structured JSON alerts

### Example alert output

```json
{
  "timestamp": "2026-03-14T19:30:00Z",
  "severity": "critical",
  "type": "pod_crash_loop",
  "what": "Pod degrading-app-xxxxx is in CrashLoopBackOff (5 restarts)",
  "where": {
    "namespace": "lab3",
    "pod": "degrading-app-xxxxx",
    "node": "aks-systempool-12345-vmss000000",
    "container": "web"
  },
  "context": {
    "restart_count": 5,
    "last_state": "OOMKilled",
    "exit_code": 137
  }
}
```

### Discussion Answer

**Polling vs. event-driven:**
- **Polling** (this lab): Simple, predictable, easy to reason about. Downside: detection latency = polling interval. Good for hackathons and simple setups.
- **Event-driven** (production): Uses Kubernetes watch API or event streaming (KEDA, Azure Event Grid). Lower latency, more efficient. Downside: more complex to implement, need to handle reconnections and missed events.

**"Gather before concluding"**: The detection agent should collect facts (pod status, restart count, last exit code) without jumping to conclusions. The diagnosis agent handles interpretation.

---

## Solution 4 — Build a Diagnosis Agent

### Reference implementation: `scripts/diagnosis_agent.py`

```powershell
pip install kubernetes openai azure-identity
```

### Authentication options

The diagnosis agent supports three authentication methods, tried in order:

| Priority | Method | Environment Variables | When to use |
|----------|--------|----------------------|-------------|
| 1 | **Azure OpenAI + Entra ID** | `AZURE_OPENAI_ENDPOINT` only | Workshop default. Uses your `az login` session. No API keys needed. |
| 2 | **Azure OpenAI + API key** | `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_KEY` | When `disableLocalAuth=false` and you prefer API keys. |
| 3 | **OpenAI (direct)** | `OPENAI_API_KEY` | Personal OpenAI account. |

**For this workshop**, we use **Option 1 (Entra ID)** because the infrastructure is deployed in a restricted environment where `disableLocalAuth=true` is enforced on Azure OpenAI accounts. This means API keys cannot be retrieved, so we authenticate via Microsoft Entra ID using the `AzureCliCredential` from the `azure-identity` package.

**Prerequisites for Entra ID auth:**
- You must be logged in with `az login`
- Your user must have the **"Cognitive Services OpenAI User"** role on the Azure OpenAI account (assigned during infra deployment via Bicep)
- The `azure-identity` Python package must be installed

```powershell
# Set the endpoint (no key needed — Entra ID auth via az login)
$env:AZURE_OPENAI_ENDPOINT = "https://<your-prefix>-openai.openai.azure.com/"
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-4o-mini"

# Run the diagnosis agent
python labs/lab3-sre-agent/solutions/scripts/diagnosis_agent.py --alert-file alert.json
```

The diagnosis agent:
1. Reads the structured alert from the detection agent
2. Runs targeted context-gathering commands based on alert type
3. Structures the context (symptoms, logs, events, spec)
4. Sends it to the LLM with an SRE system prompt
5. Returns a structured diagnosis

### Context-gathering strategy per alert type

| Alert Type | Context Gathered |
|-----------|-----------------|
| `pod_crash_loop` | Pod describe, previous logs, exit code, events, resource usage |
| `pod_image_pull` | Pod describe, image name, registry connectivity, pull secrets |
| `pod_pending` | Pod describe, scheduler events, node resources, taints/tolerations |
| `pod_not_ready` | Pod describe, readiness probe config, logs, endpoint status |

### Example diagnosis output

```json
{
  "root_cause": "Container is being OOM-killed. Memory limit of 64Mi is insufficient for the application under load. The application has a memory leak in the request handler that accumulates ~2Mi per 100 requests.",
  "evidence": [
    "Exit code 137 (OOMKilled) in last termination state",
    "Memory usage trend: 30Mi → 48Mi → 62Mi → OOMKilled over 5 minutes",
    "Pod events show repeated OOMKilled at ~64Mi"
  ],
  "remediation_steps": [
    "Increase memory limit to 256Mi as immediate fix",
    "Investigate memory leak in the application code",
    "Consider adding a memory-based HPA to scale horizontally"
  ],
  "confidence": "high",
  "risk_level": "low"
}
```

### LLM system prompt

The diagnosis agent uses a carefully crafted system prompt (the `SYSTEM_PROMPT` variable in `diagnosis_agent.py`) to shape how the LLM analyzes incidents. This is the Lab 2 context engineering principle in practice — the quality of the diagnosis depends heavily on how you frame the request:

- **SRE persona** — tells the model to think like an expert Kubernetes operator, not a generic assistant
- **Expected input structure** — so the model knows what data it's receiving (alerts, pod describe, logs, events)
- **Forced JSON output schema** — ensures the response is machine-parseable by the next agent in the pipeline
- **Behavioral guardrails** — "Be specific", "Do not guess" prevent vague or hallucinated diagnoses

Without this prompt, the model gives generic advice. With it, you get evidence-based, structured diagnoses that reference exact log lines and event messages.

```
You are an expert Kubernetes SRE performing root cause analysis for an AKS cluster incident.

You will receive a structured incident report containing:
- Alert details (what, where, when, severity)
- Pod description and spec
- Container logs (current and previous)
- Kubernetes events
- Resource usage metrics

Analyze the evidence and provide your diagnosis as JSON with these fields:
- root_cause: Clear explanation of what happened and why
- evidence: Array of specific data points supporting your diagnosis
- remediation_steps: Ordered list of actions to resolve the issue
- confidence: "high", "medium", or "low"
- risk_level: Risk of the suggested remediation ("low", "medium", "high")

Be specific. Reference exact log lines, event messages, and metric values in your evidence.
Do not guess — if you're uncertain, say so and suggest additional data to collect.
```

### Discussion Answer

The Azure SRE Agent blog emphasizes:
- **Confidence scoring**: Not all diagnoses are equal. High confidence → auto-remediate. Low confidence → escalate to human.
- **Escalation triggers**: Unknown failure patterns, multiple simultaneous incidents, actions that exceed blast radius limits, security-related events.
- **Human override**: Always provide a way for humans to override the agent's decision.

---

## Solution 5 — Build a Remediation Agent

### Reference implementation: `scripts/remediation_agent.py`

```powershell
python labs/lab3-sre-agent/solutions/scripts/remediation_agent.py --diagnosis-file diagnosis.json --dry-run
```

### Implemented actions

**1. Restart pod:**
```powershell
# Dry run
kubectl delete pod <pod-name> -n <namespace> --dry-run=server

# Execute
kubectl delete pod <pod-name> -n <namespace>
```

**2. Scale deployment:**
```powershell
# Record current state
kubectl get deployment <name> -n <namespace> -o yaml > rollback.yaml

# Scale
kubectl scale deployment <name> -n <namespace> --replicas=<new-count>
```

**3. Patch resource (e.g., fix memory limit):**
```powershell
# Record current state
kubectl get deployment <name> -n <namespace> -o yaml > rollback.yaml

# Patch
kubectl patch deployment <name> -n <namespace> --type=json `
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"}]'
```

### Safety guardrails implementation

```python
def check_guardrails(action, diagnosis):
    # 1. Blast radius check
    if action.affected_pods > MAX_BLAST_RADIUS:
        return GuardrailResult.BLOCKED, "Exceeds blast radius limit"

    # 2. Risk-based approval
    if diagnosis.risk_level == "high":
        return GuardrailResult.NEEDS_APPROVAL, "High-risk action requires human approval"

    # 3. Namespace protection
    if action.namespace in PROTECTED_NAMESPACES:
        return GuardrailResult.BLOCKED, "Cannot modify protected namespace"

    # 4. Time-of-day check (optional)
    if is_business_hours() and diagnosis.confidence != "high":
        return GuardrailResult.NEEDS_APPROVAL, "Medium/low confidence during business hours"

    return GuardrailResult.APPROVED, "All guardrails passed"
```

### Example remediation report

```json
{
  "timestamp": "2026-03-14T19:35:00Z",
  "action": "patch_resource",
  "target": "deployment/degrading-app in lab3",
  "change": "Increased memory limit from 64Mi to 256Mi",
  "before_state": "saved to rollback/degrading-app-20260314-193500.yaml",
  "result": "success",
  "verification": {
    "pod_status": "Running",
    "ready": "1/1",
    "restarts_since_fix": 0
  }
}
```

### Verify with the detection → diagnosis pipeline

After remediation, re-run the same detect → diagnose pipeline that found the original issue. This closes the feedback loop — if the agents that detected the problem now report "all clear", the fix is confirmed. If they find something new, you've uncovered a deeper issue.

```powershell
# Re-run detection against the remediated deployment
python labs/lab3-sre-agent/solutions/scripts/detection_agent.py --output alert-post-fix.json

# If an alert is found, diagnose it
python labs/lab3-sre-agent/solutions/scripts/diagnosis_agent.py --alert-file alert-post-fix.json --output diagnosis-post-fix.json
```

> **What you may see:** The memory fix resolves the OOMKill (exit code 137, CrashLoopBackOff), but the detection agent may catch a *new* issue — the readiness probe failing with 503. This is because the app's startup script still removes `ready.txt` after 120s. Increasing memory fixed one symptom but revealed the underlying application logic bug.
>
> **Don't fix it here.** This is exactly the scenario Solution 6 (the orchestrator) is designed for — a multi-agent loop that automatically iterates: detect a new issue, diagnose it, propose a fix, and repeat until the deployment is healthy. Leave the readiness issue for the orchestrator to handle.

### Discussion Answer

**Never auto-remediate without approval:**
- Deleting PersistentVolumeClaims or StatefulSet pods with data
- Scaling to zero replicas
- Modifying RBAC/security policies
- Actions in production namespaces during business hours
- Any action when multiple incidents are active simultaneously

**Blast radius definition:**
- Number of pods/replicas affected
- Number of users/services dependent on the target
- Whether the target is a single point of failure
- The reversibility of the action

---

## Solution 6 — Orchestrate the Multi-Agent Pipeline

We use a **fresh namespace** (`lab3-orchestrator`) so the orchestrator gets a clean incident to work with — no leftover patches from Solution 5. This also demonstrates that the agents are namespace-agnostic.

### Step 1: Create a fresh namespace and deploy the incident

```powershell
# Create a dedicated namespace for the orchestrator exercise
kubectl create namespace lab3-orchestrator

# Deploy the degrading app into the new namespace
(Get-Content labs/lab3-sre-agent/solutions/manifests/02-degrading-app.yaml) -replace 'namespace: lab3', 'namespace: lab3-orchestrator' | kubectl apply -f -
```

> **Why a new namespace?** In Solution 5 you patched the memory limit in `lab3`, so that deployment is already fixed. A fresh namespace gives the orchestrator an untouched incident — OOMKill, readiness failure, and all — so it can demonstrate the full iterative loop.

### Step 2: Run the full pipeline manually (optional)

You can run each agent step-by-step to see the data flowing between them:

```powershell
# Detection
python labs/lab3-sre-agent/solutions/scripts/detection_agent.py --namespace lab3-orchestrator --output alert.json

# Diagnosis
python labs/lab3-sre-agent/solutions/scripts/diagnosis_agent.py --alert-file alert.json --output diagnosis.json

# Remediation (dry-run first)
python labs/lab3-sre-agent/solutions/scripts/remediation_agent.py --diagnosis-file diagnosis.json --dry-run

# If the plan looks good, execute
python labs/lab3-sre-agent/solutions/scripts/remediation_agent.py --diagnosis-file diagnosis.json --execute
```

### Step 3: Or run the orchestrator

```powershell
python labs/lab3-sre-agent/solutions/scripts/orchestrator.py --namespace lab3-orchestrator --watch
```

The orchestrator connects all three agents in a loop:
1. Detection polls every 15s
2. On alert → runs diagnosis
3. On diagnosis → shows remediation plan
4. Waits for human approval → executes
5. Verifies fix → logs result
6. Returns to monitoring

### Example end-to-end timeline

```
[19:30:00] DETECT  | Monitoring lab3-orchestrator namespace...
[19:30:15] DETECT  | Pod degrading-app-abc123 — restart count: 3, status: CrashLoopBackOff
[19:30:15] ALERT   | severity=critical type=pod_crash_loop pod=degrading-app-abc123
[19:30:16] DIAGNOSE| Gathering context: describe, logs, events...
[19:30:18] DIAGNOSE| Sending to LLM for analysis...
[19:30:21] DIAGNOSE| Root cause: OOMKilled (memory limit 64Mi, usage peaked at 63Mi)
[19:30:21] DIAGNOSE| Confidence: high | Risk: low
[19:30:21] REMEDIATE| Plan: Patch deployment memory limit 64Mi → 256Mi
[19:30:21] REMEDIATE| [DRY RUN] Would patch deployment/degrading-app memory limit to 256Mi
[19:30:21] APPROVAL | Execute this remediation? [y/n]: y
[19:30:22] REMEDIATE| Saved rollback state to rollback/degrading-app-20260314-193022.yaml
[19:30:22] REMEDIATE| Patching deployment/degrading-app...
[19:30:23] REMEDIATE| Patch applied. Waiting for rollout...
[19:30:35] VERIFY   | Pod degrading-app-def456: Running, Ready 1/1, Restarts: 0
[19:30:35] RESOLVED | Incident resolved. Total time: 20 seconds
```

### Discussion Answer

**Compared to the Microsoft on-call Copilot blog:**
- Our lab implements a simplified version of the same multi-agent pattern
- The blog describes additional agents: notification, escalation, post-mortem
- Production systems need: persistence (incident database), retry logic, SLA tracking, integration with PagerDuty/ServiceNow, audit logs

**For production, add:**
- **Incident database**: Track all incidents, diagnoses, and remediations
- **Escalation policies**: If auto-remediation fails twice, page a human
- **SLA tracking**: Measure detection-to-resolution time
- **Post-mortem generation**: AI-generated incident summaries
- **Feedback loop**: Humans rate diagnosis quality to improve future performance
- **Multi-cluster support**: Single agent monitoring multiple clusters

---

## Cost & Security Notes

### Cost

The orchestrator in `--watch` mode makes repeated Azure OpenAI calls (one per detected issue per cycle). Cost estimates are approximate — **verify current pricing with your Azure administrator or the [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/)** before running extended sessions.

- A 10-iteration run ≈ 10 LLM calls ≈ ~$0.05–0.10 (approximate, based on pay-as-you-go pricing)
- The escalation logic (exits after 2 failed attempts per issue type) prevents unbounded API calls
- Always Ctrl+C or let the escalation logic exit the loop when testing is done

### Security

> **Reminder:** These scripts are for learning and experimentation — not production use. Review with your security team before adapting.

- **Entra ID auth** — No API keys in code or environment. The `AzureCliCredential` uses your active `az login` session.
- **Rollback state** — Saved to `rollback/` before every mutation. Never patch without recording the previous state.
- **Grace period** — Pod deletes use `--grace-period=5` to avoid hanging on terminating containers, but this skips graceful shutdown. In production, use the default grace period.
- **Namespace scope** — All agents accept `--namespace` and never operate outside it. The orchestrator only monitors and remediates within the specified namespace.

---

## Solution 7 — Cleanup

```powershell
# Delete both lab namespaces
kubectl delete namespace lab3
kubectl delete namespace lab3-orchestrator

# Uninstall Prometheus + Grafana
helm uninstall prometheus -n monitoring
kubectl delete namespace monitoring
```

Verify:
```powershell
kubectl get all -n lab3
# Expected: No resources found in lab3 namespace.

kubectl get all -n lab3-orchestrator
# Expected: No resources found in lab3-orchestrator namespace.

kubectl get all -n monitoring
# Expected: No resources found in monitoring namespace.
```
