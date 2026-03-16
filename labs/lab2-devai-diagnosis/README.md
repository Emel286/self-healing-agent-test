# Lab 2 — Agent-Assisted Diagnosis (DevAI Foundations)

## Objective

Learn how to leverage AI-powered tools to diagnose, troubleshoot, and fix Kubernetes workloads on AKS. This lab introduces the concept of **DevAI** — using AI agents as a co-pilot for infrastructure operations.

By the end of this lab you will:

- Use Azure Copilot to diagnose AKS cluster issues
- Generate and validate Kubernetes YAML using Copilot
- Apply context engineering principles for effective AI-assisted troubleshooting
- Diagnose intentionally broken workloads using AI-assisted workflows
- Understand how SRE agents approach complex multi-step diagnostics

## Prerequisites

- Completed infrastructure deployment (see root [README.md](../../README.md))
- `kubectl` connected to the AKS cluster
- Access to [Azure Portal](https://portal.azure.com) with Copilot enabled
- GitHub Copilot available in your IDE (VS Code recommended)

## Reference Documentation

- [Azure Copilot for AKS troubleshooting](https://learn.microsoft.com/azure/copilot/work-aks-clusters)
- [Copilot for Kubernetes YAML & config analysis](https://learn.microsoft.com/azure/copilot/generate-kubernetes-yaml)
- [Context engineering lessons from the Azure SRE Agent](https://techcommunity.microsoft.com/blog/appsonazureblog/context-engineering-lessons-from-building-azure-sre-agent/4481200)

---

## Challenge 1 — Diagnose a CrashLoopBackOff

**Goal:** A deployment has been applied to the cluster but pods are stuck in `CrashLoopBackOff`. Use your AI tools and kubectl skills to identify the root cause and fix it.

**Setup:**
```powershell
kubectl create namespace lab2
kubectl apply -f labs/lab2-devai-diagnosis/solutions/manifests/01-crashloop.yaml
```

**Requirements:**
- Identify **why** the pods are crash-looping
- Use Azure Copilot in the Azure Portal: navigate to your AKS cluster and ask Copilot to help diagnose the issue
- Alternatively, paste the pod logs and events into GitHub Copilot Chat and ask for analysis
- Fix the issue by creating a corrected YAML manifest and applying it

**What to observe:**
- Pod status shows `CrashLoopBackOff` with increasing restart counts
- The events and logs contain clues about the root cause
- AI tools can quickly identify the problem pattern

**Hints:**
- Start with `kubectl describe pod` and `kubectl logs`
- Ask Copilot: *"Why is my pod in CrashLoopBackOff? Here are the logs: ..."*
- Context matters — provide Copilot with relevant pod events and container logs

> **Discussion:** How does providing more context (logs, events, YAML) to an AI agent improve diagnosis accuracy? What is the minimum context needed for a useful diagnosis?

---

## Challenge 2 — Fix an ImagePullBackOff

**Goal:** A deployment references an image that cannot be pulled. Diagnose the issue and determine the correct fix.

**Setup:**
```powershell
kubectl apply -f labs/lab2-devai-diagnosis/solutions/manifests/02-imagepull.yaml
```

**Requirements:**
- Identify why the image cannot be pulled
- Use AI tools to suggest possible causes (wrong image name, tag, registry auth, etc.)
- Fix the manifest with the correct image reference and redeploy

**What to observe:**
- Pod status shows `ImagePullBackOff` or `ErrImagePull`
- Events show the specific pull error
- AI tools can distinguish between different ImagePull failure types

**Hints:**
- Look at the image reference in the spec carefully
- Ask Copilot: *"What causes ImagePullBackOff and how do I fix it?"*
- Try using Copilot to generate a corrected YAML from the broken one

> **Discussion:** What are the common categories of ImagePull failures? (wrong name, wrong tag, private registry, rate limiting) How would you automate detecting these in a CI/CD pipeline?

---

## Challenge 3 — Diagnose Resource Constraint Issues

**Goal:** A deployment has pods stuck in `Pending` state because of resource constraints. Investigate and resolve the scheduling issue.

**Setup:**
```powershell
kubectl apply -f labs/lab2-devai-diagnosis/solutions/manifests/03-resource-constraint.yaml
```

**Requirements:**
- Identify why pods are not being scheduled
- Use AI tools to analyze the scheduling failure
- Determine if the issue is insufficient node resources, wrong resource requests, or missing node affinity
- Fix the manifest to allow pods to be scheduled

**What to observe:**
- Pods stay in `Pending` state indefinitely
- `kubectl describe pod` shows scheduling failure events
- The cluster node resources vs. pod requests tell the story

**Hints:**
- Check `kubectl describe pod` for the `Events` section — look for `FailedScheduling`
- Compare `kubectl top nodes` with the resource requests in the manifest
- Ask Copilot: *"This pod is pending with this event: [paste event]. What's wrong?"*

> **Discussion:** How does the Kubernetes scheduler decide where to place pods? What's the difference between resource `requests` and `limits`? How can AI help right-size resource requests?

---

## Challenge 4 — Generate Kubernetes YAML with Copilot

**Goal:** Use AI to generate Kubernetes manifests from natural language descriptions. Validate and refine the generated YAML.

**Requirements:**
1. Use Azure Copilot or GitHub Copilot to generate a Deployment manifest for:
   - A Node.js application (`node:20-alpine` image)
   - 3 replicas
   - Exposed on port 3000
   - Resource requests: 100m CPU, 128Mi memory
   - Resource limits: 200m CPU, 256Mi memory
   - All three probe types (liveness, readiness, startup)
   - A ClusterIP Service

2. Review the generated YAML for:
   - Correct API versions
   - Proper label selectors
   - Security best practices (non-root, read-only filesystem, drop capabilities)
   - Resource management

3. Ask Copilot to improve the manifest with security hardening

**What to observe:**
- How accurately does AI generate correct K8s YAML from a description?
- What does the AI miss on the first pass? (security context, PDB, topology spread)
- How does iterative prompting improve the output?

> **Discussion:** What are the risks of blindly applying AI-generated YAML to production? What validation steps should be part of a GitOps pipeline?

---

## Challenge 5 — Context Engineering for Effective Diagnosis

**Goal:** Practice the art of **context engineering** — structuring your prompts and providing the right information to get the best results from AI diagnostic tools.

**Scenario:** A multi-container pod is failing. You need to provide the right context to an AI agent to diagnose the issue efficiently.

**Setup:**
```powershell
kubectl apply -f labs/lab2-devai-diagnosis/solutions/manifests/05-multi-container.yaml
```

**Requirements:**
1. Gather diagnostic context from the failing pod:
   - Pod description (`kubectl describe pod`)
   - Logs from each container
   - Events from the namespace
   - Node status and resource usage

2. Structure a prompt for Copilot that includes:
   - **What you're seeing** (symptoms)
   - **What you expected** (desired state)
   - **Relevant context** (logs, events, YAML)
   - **What you've already tried**

3. Compare results from:
   - A vague prompt: *"My pod is broken, fix it"*
   - A well-structured prompt with full context

**What to observe:**
- Vague prompts produce generic, unhelpful advice
- Structured prompts with specific logs and events yield precise diagnoses
- The quality of AI output is directly proportional to the quality of input context

**Key context engineering principles** (from the Azure SRE Agent blog):
- **Gather before concluding**: Collect all relevant signals before forming a hypothesis
- **Structured context**: Organize information (symptoms, logs, timeline) rather than dumping raw data
- **Iterative refinement**: Start broad, then narrow down based on initial analysis
- **Domain-specific framing**: Use Kubernetes-specific language and concepts in prompts

> **Discussion:** How does the "context engineering" approach from the Azure SRE Agent apply to daily DevOps work? What makes a good prompt for infrastructure troubleshooting vs. code generation?

---

## Challenge 6 — End-to-End AI-Assisted Troubleshooting

**Goal:** Combine everything you've learned. A broken application has been deployed with **multiple issues**. Use AI-assisted workflows to diagnose and fix all problems.

**Setup:**
```powershell
kubectl apply -f labs/lab2-devai-diagnosis/solutions/manifests/06-broken-app.yaml
```

**Requirements:**
- The application has at least 3 different issues
- Use a systematic approach: gather context → diagnose → fix → verify
- Document each issue found, the diagnosis method, and the fix applied
- Use AI tools for at least 2 of the diagnoses

**What to observe:**
- Real-world issues rarely come alone — multiple problems may stack
- A systematic approach (triage → context → diagnose → fix → verify) is more effective than random debugging
- AI tools are most helpful when you provide structured context at each step

> **Discussion:** How would you build an automated diagnosis pipeline that combines AI agents with observability tools (logs, metrics, traces)? What are the limitations of AI-assisted troubleshooting?

---

## Challenge 7 — Cleanup

Remove all lab resources:

```powershell
kubectl delete namespace lab2
```

---

## Summary

| Concept | What You Should Have Learned |
|---------|------------------------------|
| **CrashLoopBackOff diagnosis** | Using logs, events, and AI to identify container start failures |
| **ImagePull troubleshooting** | Differentiating image name, tag, auth, and registry issues |
| **Resource constraints** | Understanding scheduling failures and resource requests/limits |
| **YAML generation** | Using AI to scaffold manifests and iteratively improve them |
| **Context engineering** | Structuring prompts for precise AI-assisted diagnosis |
| **Systematic troubleshooting** | Combining AI tools with a methodical debugging workflow |

## Key Takeaways

1. **Context is king**: The quality of AI assistance depends entirely on the quality of context you provide
2. **Gather first, conclude later**: Collect logs, events, and pod descriptions before asking for a diagnosis
3. **AI is a co-pilot, not autopilot**: Always validate AI suggestions before applying to production
4. **Structure your prompts**: Symptoms → Expected behavior → Context → What you've tried
5. **Iterate**: Use AI output to refine your next question — diagnosis is a conversation

---

> **Stuck?** Check the [solutions](solutions/) folder for step-by-step walkthroughs, fixed manifests, and example Copilot prompts.
