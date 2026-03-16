# Lab 1 — AKS Resiliency & Failure Basics

## Objective

Learn how AKS handles failures automatically and how to build resilient workloads using health probes, self-healing mechanisms, and node auto-repair.

By the end of this lab you will:

- Understand how AKS self-healing keeps workloads running
- Configure liveness, readiness, and startup probes
- Observe node auto-repair in action
- Test pod disruption budgets (PDBs)
- Simulate failures and verify recovery

## Prerequisites

- Completed infrastructure deployment (see root [README.md](../../README.md))
- `kubectl` connected to the AKS cluster
- Cluster is in **Running** power state

## Reference Documentation

- [AKS Automatic (self-healing baseline)](https://learn.microsoft.com/azure/aks/automatic/quick-automatic-managed-network)
- [AKS node auto-repair](https://learn.microsoft.com/azure/aks/node-auto-repair)
- [AKS health probes & workload resiliency](https://learn.microsoft.com/azure/aks/concepts-clusters-workloads#application-health)
- [Kubernetes Probes documentation](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Pod Disruption Budgets](https://kubernetes.io/docs/tasks/run-application/configure-pdb/)

---

## Challenge 1 — Deploy a Resilient Application with Health Probes

**Goal:** Create a Kubernetes Deployment for an Nginx-based application that includes all three probe types: **liveness**, **readiness**, and **startup**.

**Requirements:**
- Deploy to a dedicated namespace called `lab1`
- The application should run 2 replicas
- Configure an HTTP-based **startup probe** that gives the container time to initialize
- Configure an HTTP-based **liveness probe** that detects container crashes
- Configure an HTTP-based **readiness probe** that controls traffic routing
- Expose the application with a ClusterIP Service

**What to observe:**
- All pods should reach `Running` state with `READY 1/1`
- Use `kubectl describe` to see probe configurations and health check events
- Confirm that the `Ready` and `ContainersReady` conditions are `True`

> **Discussion:** What is the difference between liveness and readiness probes? When would you use a startup probe?

---

## Challenge 2 — Simulate a Liveness Probe Failure

**Goal:** Deploy an application that **becomes unhealthy** after a delay, causing the liveness probe to fail. Observe how Kubernetes automatically restarts the container.

**Requirements:**
- The application should start healthy and begin failing its liveness check after approximately 30 seconds
- Use an HTTP endpoint that returns different status codes over time

**What to observe:**
- The pod starts normally and passes initial health checks
- After ~30 seconds, the liveness probe starts failing
- Kubernetes kills and restarts the container (the `RESTARTS` count increases)
- The pod keeps cycling between healthy and unhealthy

**Hints:**
- You can use a shell command to modify Nginx's response after a delay
- Look at `kubectl describe pod` events for `Unhealthy` and `Killing` entries

> **Discussion:** What happens if a liveness probe keeps failing indefinitely? How does this differ from a readiness probe failure?

---

## Challenge 3 — Simulate a Readiness Probe Failure

**Goal:** Deploy an application where the **readiness probe fails** after a delay. Understand that unlike liveness failures, readiness failures **do not restart** the pod — they remove it from Service endpoints.

**Requirements:**
- The application should start ready, then become unready after ~20 seconds
- Include a Service so you can observe endpoint changes
- The liveness probe should continue passing (pod stays running)

**What to observe:**
- The pod stays `Running` but transitions to `READY 0/1`
- The Service endpoint list becomes empty — no traffic is routed to the pod
- The pod is **NOT restarted** (RESTARTS stays at 0)

**Hints:**
- Use a readiness probe that checks for the existence of a file served by Nginx
- Remove the file after a delay to trigger readiness failure
- Watch both `pods` and `endpoints` simultaneously in two terminals

> **Discussion:** Why is readiness useful for rolling updates? What happens to in-flight requests when a pod becomes unready?

---

## Challenge 4 — Self-Healing with ReplicaSets

**Goal:** Deploy a 3-replica application and test Kubernetes self-healing by deleting pods. Verify that the desired replica count is always maintained.

**Requirements:**
- Deploy 3 replicas of a simple application
- Spread pods across nodes using topology spread constraints
- Delete individual pods and observe automatic replacement
- Delete ALL pods at once and observe recovery

**What to observe:**
- When a pod is deleted, a replacement is immediately created
- The ReplicaSet controller always maintains 3 running pods
- Even when all pods are deleted simultaneously, Kubernetes recreates them all

> **Discussion:** What is the role of the ReplicaSet controller? How does a Deployment differ from a bare ReplicaSet?

---

## Challenge 5 — Pod Disruption Budgets (PDB)

**Goal:** Add a Pod Disruption Budget to your replicated application that ensures at least 2 pods remain available during voluntary disruptions. Test it by draining a node.

**Requirements:**
- Create a PDB with `minAvailable: 2` for your 3-replica application
- Simulate a voluntary disruption by draining a node
- Verify the PDB prevents too many pods from being evicted at once

**What to observe:**
- `kubectl get pdb` shows `ALLOWED DISRUPTIONS: 1`
- Node drain evicts pods one at a time, respecting the PDB
- At least 2 pods remain available at all times during the drain
- Don't forget to uncordon the node after testing!

> **Discussion:** What happens if you try to drain a node but the PDB would be violated? How do PDBs interact with cluster autoscaler?

---

## Challenge 6 — Node Auto-Repair

**Goal:** Understand the AKS node auto-repair mechanism. Inspect node health conditions and learn the auto-repair flow.

**Tasks:**
1. Check the health conditions of all nodes in the cluster
2. Identify what node conditions AKS monitors (Ready, MemoryPressure, DiskPressure, PIDPressure)
3. Understand the auto-repair process:
   - How often does AKS check node health?
   - How long must a node be `NotReady` before repair triggers?
   - What is the repair sequence? (Reboot → Reimage → Replace)
4. Check the AKS cluster health from Azure CLI

> **Note:** Node auto-repair is a managed AKS feature. In a production cluster, repair events can be observed in Azure Monitor or the Activity Log.

> **Discussion:** Why doesn't AKS immediately replace a NotReady node? What are the risks of manual node operations (e.g., SSH-ing and killing kubelet)?

---

## Challenge 7 — Cleanup

Remove all lab resources by deleting the namespace. Verify everything is cleaned up.

---

## Summary

| Concept | What You Should Have Learned |
|---------|------------------------------|
| **Liveness Probe** | Restarts containers that become unresponsive |
| **Readiness Probe** | Removes pods from Service endpoints when not ready to serve traffic |
| **Startup Probe** | Gives slow-starting containers time to initialize before liveness kicks in |
| **Self-Healing** | ReplicaSets automatically replace deleted/failed pods |
| **Pod Disruption Budget** | Enforces minimum availability during voluntary disruptions |
| **Node Auto-Repair** | AKS automatically detects and repairs unhealthy nodes |

## Key Takeaways

1. Always configure **all three probe types** for production workloads
2. Use **Pod Disruption Budgets** to protect availability during upgrades and maintenance
3. AKS node auto-repair is automatic — avoid manual node operations that could interfere
4. **Readiness ≠ Liveness**: readiness controls traffic routing; liveness controls container restarts
5. Design applications to be **stateless** when possible — this makes self-healing seamless

---

> **Stuck?** Check the [solutions](solutions/) folder for step-by-step walkthroughs and ready-to-use manifests.
