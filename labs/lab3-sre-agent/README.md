# Lab 3 — End-to-End SRE Agent Flow

## Objective

Build and test a multi-agent SRE workflow that can **detect**, **diagnose**, and **remediate** incidents on your AKS cluster. This lab brings together observability, AI-assisted troubleshooting, and automated remediation into a cohesive on-call copilot experience.

By the end of this lab you will:

- Set up observability on your AKS cluster (metrics, logs, alerts)
- Create realistic incident scenarios that trigger automated detection
- Build an agent-assisted triage and diagnosis workflow
- Implement automated remediation actions with safety guardrails
- Understand the multi-agent architecture pattern for SRE operations

## Prerequisites

- Completed infrastructure deployment (see root [README.md](../../README.md))
- Completed [Lab 1](../lab1-resiliency/) and [Lab 2](../lab2-devai-diagnosis/) (concepts build on each other)
- `kubectl` connected to the AKS cluster
- [Helm](https://helm.sh/docs/intro/install/) installed (`winget install Helm.Helm` on Windows)
- Python 3.10+ installed locally
- GitHub Copilot available in your IDE
- Azure OpenAI endpoint (deployed with the workshop infrastructure)

### Azure OpenAI Authentication

The workshop infrastructure deploys an Azure OpenAI resource (`<prefix>-openai`) with a `gpt-4o-mini` model. Authentication uses **Microsoft Entra ID** (formerly Azure AD) via your `az login` session — no API keys required.

This is the recommended approach for environments where `disableLocalAuth=true` is enforced (common in enterprise subscriptions). You need:

1. **`azure-identity` Python package** — `pip install azure-identity`
2. **"Cognitive Services OpenAI User" role** on the OpenAI account (assigned during infra deployment)
3. **An active `az login` session** — the same one you use for `kubectl`

> **Other options:** If you have a personal OpenAI API key, set `OPENAI_API_KEY` instead. If your environment allows API keys on Azure OpenAI, set `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_KEY`. The solution scripts support all three methods.

## Reference Documentation

- [Building a multi-agent on-call Copilot (blog)](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/building-a-multi-agent-on-call-copilot-with-microsoft-agent-framework/4499962)
- [Open-source multi-agent SRE lab (GitHub)](https://github.com/leestott/On-Call-Copilot-Multi-Agent)
- [kube-prometheus-stack Helm chart](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
- [Grafana dashboards for Kubernetes](https://grafana.com/grafana/dashboards/?search=kubernetes)
- [Kubernetes Event-Driven Autoscaling (KEDA)](https://learn.microsoft.com/azure/aks/keda-about)

---

## Challenge 1 — Set Up Observability

**Goal:** Deploy a lightweight observability stack on your AKS cluster so agents have signals to work with (metrics, logs, events).

**Requirements:**
- Deploy a namespace `lab3` for all lab resources
- Deploy a Prometheus + Grafana stack using the `kube-prometheus-stack` Helm chart
- Verify you can collect pod metrics (`kubectl top pods`)
- Set up a mechanism to stream Kubernetes events into a queryable format

**What to observe:**
- Prometheus scrapes pod and node metrics
- Grafana dashboards show cluster health
- Kubernetes events are accessible for automated processing

**Hints:**
- Use the `kube-prometheus-stack` Helm chart — it deploys Prometheus, Grafana, and alerting rules in a single command
- Set a short retention period (e.g., 2h) to keep resource usage low on a small cluster
- Port-forward Grafana to access dashboards locally: `kubectl port-forward svc/prometheus-grafana -n monitoring 3000:80`
- Events can be collected with a simple script that polls `kubectl get events`

> **Discussion:** What are the key signals an SRE agent needs? (metrics, logs, events, traces) What's the minimum viable observability stack for automated incident response?

---

## Challenge 2 — Create an Incident Scenario

**Goal:** Deploy a workload that will degrade over time, simulating a realistic production incident. The degradation should be detectable through the observability stack.

**Requirements:**
- Deploy an application that starts healthy, then gradually degrades
- The degradation should produce observable signals:
  - Increasing error rates (5xx responses)
  - Rising latency
  - Memory growth (potential OOM)
- The incident should be detectable within 2–3 minutes
- Include a Service so the degradation affects traffic routing

**What to observe:**
- The application starts serving 200 responses
- Over time, error rate increases and latency spikes
- Eventually pods may restart or become unready
- These signals should be visible in your observability stack

**Hints:**
- A simple HTTP server that gradually increases its error rate works well
- Consider using a ConfigMap or environment variable to control the failure timing
- Memory leaks can be simulated by allocating increasing amounts of memory

> **Discussion:** What makes a good incident simulation realistic? How do you balance between "too easy to detect" and "too subtle"?

---

## Challenge 3 — Build a Detection Agent

**Goal:** Create a Python script (or notebook) that acts as a **detection agent** — it monitors cluster state and raises alerts when anomalies are detected.

**Requirements:**
- The agent should poll cluster state periodically (every 15–30 seconds)
- Detect at least 3 types of anomalies:
  - Pods not in `Running` state or with high restart counts
  - Pods with `READY 0/x` (readiness failures)
  - High error rates from pod logs
- When an anomaly is detected, output a structured alert with:
  - **What**: Description of the anomaly
  - **Where**: Namespace, pod name, node
  - **When**: Timestamp
  - **Severity**: Critical / Warning / Info
- The output should be in JSON format (consumable by the next agent)

**What to observe:**
- The agent detects the degradation from Challenge 2 within its polling interval
- Alerts are structured and contain actionable information
- The detection is the first step of the detect → diagnose → remediate pipeline

**Hints:**
- Use the `kubernetes` Python client library or shell out to `kubectl`
- Start simple: check pod status, then add log analysis
- Think about what context the next agent (diagnosis) will need from your alert

> **Discussion:** How does this compare to the "gather before concluding" principle from the Azure SRE Agent? What are the trade-offs between polling vs. event-driven detection?

---

## Challenge 4 — Build a Diagnosis Agent

**Goal:** Create a diagnosis agent that receives alerts from the detection agent and uses AI to perform root cause analysis.

**Requirements:**
- Input: A structured alert (JSON) from the detection agent
- The agent should:
  1. Gather additional context (pod describe, logs, events, resource usage)
  2. Structure the context using the principles from Lab 2
  3. Send the structured context to an LLM (OpenAI / Azure OpenAI / local model) for analysis
  4. Output a structured diagnosis with:
     - **Root cause**: What's happening and why
     - **Evidence**: Supporting data from logs/events
     - **Suggested remediation**: Actionable fix steps
     - **Confidence**: High / Medium / Low
     - **Risk**: Impact of the suggested remediation

**What to observe:**
- The agent gathers targeted context based on the alert type
- The LLM diagnosis is more accurate than a generic query because of structured context
- Different alert types produce different context-gathering strategies

**Hints:**
- Use the `openai` Python library with Azure OpenAI SDK
- The workshop Azure OpenAI endpoint uses Entra ID auth — just set `AZURE_OPENAI_ENDPOINT` and ensure you're logged in with `az login`
- Apply the context engineering principles from Lab 2 — structure matters
- Include the pod YAML spec in the context for misconfig diagnoses
- Consider using a system prompt that gives the LLM an "SRE persona"

**Example system prompt:**
```
You are an expert Kubernetes SRE. You receive structured incident reports 
and perform root cause analysis. Always provide evidence-based diagnoses.
Format your response as JSON with fields: root_cause, evidence, 
remediation_steps, confidence, risk_level.
```

> **Discussion:** How does the Azure SRE Agent blog describe the balance between automation and human oversight? When should a diagnosis agent escalate to a human instead of proceeding?

---

## Challenge 5 — Build a Remediation Agent

**Goal:** Create a remediation agent that can execute safe fixes based on the diagnosis agent's output. Implement safety guardrails to prevent dangerous actions.

**Requirements:**
- Input: A structured diagnosis (JSON) from the diagnosis agent
- Implement at least 3 remediation actions:
  - **Restart a pod** — for CrashLoopBackOff or OOM situations
  - **Scale a deployment** — to handle increased load
  - **Patch a resource** — fix a misconfiguration (e.g., image, resource limits)
- Safety guardrails:
  - **Dry-run mode**: Show what would be done without executing
  - **Approval gate**: Require human confirmation for high-risk actions
  - **Blast radius check**: Refuse actions that affect more than N pods at once
  - **Rollback plan**: Record the previous state before any change
- Output a remediation report (what was done, result, before/after state)

**What to observe:**
- Remediation actions are executed safely with guardrails
- Dry-run mode shows the plan without making changes
- High-risk actions pause for human approval
- The remediation report provides a clear audit trail

**Hints:**
- Use `kubectl` commands with `--dry-run=server` for dry-run mode
- Store the current state (e.g., `kubectl get deployment -o yaml`) before making changes
- Use a simple approval mechanism (e.g., prompt for y/n in the terminal)
- Think about what makes an action "high risk" vs "low risk"
- After remediation, re-run the detection → diagnosis pipeline to verify the fix. If the agents that found the original issue now report "all clear", the fix is confirmed. If they find something *new*, you've uncovered a deeper issue — leave it for the orchestrator in Challenge 6

> **Discussion:** What actions should NEVER be automated without human approval? How do you define blast radius for SRE automation? What's the role of rollback in safe remediation?

---

## Challenge 6 — Orchestrate the Multi-Agent Pipeline

**Goal:** Connect all three agents (detect → diagnose → remediate) into an end-to-end pipeline. Run it against a live incident scenario and verify the full cycle works.

**Requirements:**
1. Create a **fresh namespace** (e.g., `lab3-orchestrator`) and deploy the incident scenario from Challenge 2 into it
2. Start the detection agent — it should detect the issue
3. Feed the alert to the diagnosis agent — it should identify root cause
4. Feed the diagnosis to the remediation agent — it should propose and (with approval) execute a fix
5. Verify the fix resolved the issue

**Pipeline flow:**
```
[Incident Occurs]
       ↓
[Detection Agent] → structured alert (JSON)
       ↓
[Diagnosis Agent] → root cause analysis (JSON)
       ↓
[Remediation Agent] → fix plan → [Human Approval] → execute → verify
       ↓
[Incident Resolved]
```

**Bonus challenges:**
- Add a **notification step** (print to console or write to a file simulating Slack/Teams)
- Implement **feedback loop**: if remediation didn't fix the issue, re-run diagnosis with the new state
- Add **incident timeline**: log each step with timestamps for post-mortem review

**What to observe:**
- The full pipeline runs from detection to resolution
- Each agent passes structured data to the next
- Human-in-the-loop approval gates prevent unsafe actions
- The incident is resolved with a clear audit trail

**Hints:**
- Use a separate namespace so the orchestrator gets a clean, unpatched incident to work with — no leftovers from Challenge 5
- The manifest hardcodes `namespace: lab3`, so you'll need to replace it when deploying to the new namespace (e.g., with PowerShell string replacement piped to `kubectl apply`)
- The orchestrator script accepts `--namespace` to target any namespace
- With `--watch`, the orchestrator loops: after fixing one issue (e.g., OOMKill), it keeps monitoring and may detect the next one (e.g., readiness probe 503) — this is the iterative power of the multi-agent loop

> **Discussion:** How does this multi-agent pattern compare to the architecture in the Microsoft on-call Copilot blog? What would you add for production use? (persistence, retries, escalation policies, SLA tracking)

---

## Challenge 7 — Cleanup

Remove all lab resources:

```powershell
kubectl delete namespace lab3
kubectl delete namespace lab3-orchestrator
```

Also clean up any local Python/agent files you no longer need.

---

## Summary

| Concept | What You Should Have Learned |
|---------|------------------------------|
| **Observability** | Setting up metrics, logs, events for automated consumption |
| **Incident simulation** | Creating realistic degradation scenarios for testing |
| **Detection agent** | Polling cluster state and producing structured alerts |
| **Diagnosis agent** | AI-powered root cause analysis with context engineering |
| **Remediation agent** | Safe automated fixes with guardrails and approval gates |
| **Multi-agent orchestration** | Connecting agents into a detect → diagnose → remediate pipeline |

## Key Takeaways

1. **Agents need structured data**: Each agent in the pipeline produces structured output for the next
2. **Safety first**: Guardrails (dry-run, approval gates, blast radius checks) are non-negotiable for automated remediation
3. **Human-in-the-loop**: The best SRE automation augments humans, not replaces them — especially for high-risk actions
4. **Context engineering applies everywhere**: The quality of each agent's output depends on the quality of its input
5. **Start simple, iterate**: A basic detect → diagnose → remediate loop is more valuable than a complex system that doesn't work

---

> **Stuck?** Check the [solutions](solutions/) folder for reference implementations, scripts, and example agent code.
