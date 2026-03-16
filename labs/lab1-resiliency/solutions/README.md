# Lab 1 — Solutions

## Solution 1 — Deploy a Resilient Application with Health Probes

In this exercise you deploy a simple **Nginx web server** (2 replicas) that has all three Kubernetes health probes properly configured: startup, liveness, and readiness. This serves as a baseline to understand what a healthy, well-configured application looks like before we start breaking things in the next exercises.

### Step 1: Create the namespace

All Lab 1 resources live in a dedicated namespace so they are easy to inspect and clean up.

```bash
kubectl create namespace lab1
```

### Step 2: Deploy the application

This manifest creates a Deployment with 2 Nginx pods and a ClusterIP Service. Each pod has startup, liveness, and readiness probes that send HTTP GET requests to the Nginx root path (`/`).

```bash
kubectl apply -f labs/lab1-resiliency/solutions/manifests/01-healthy-app.yaml
```

### Step 3: Verify the deployment

Watch the pods come up. You should see both pods transition to `Running` with `1/1` in the READY column within a few seconds:

```bash
kubectl get pods -n lab1 -w
```

Expected output:
```
NAME                           READY   STATUS    RESTARTS   AGE
healthy-app-xxxxx-yyyyy        1/1     Running   0          5s
healthy-app-xxxxx-zzzzz        1/1     Running   0          5s
```

Press `Ctrl+C` to stop watching, then inspect one of the pods in detail:

```bash
kubectl describe pod -n lab1 -l app=healthy-app
```

In the output, look for the **Conditions** section — all four conditions (`Initialized`, `Ready`, `ContainersReady`, `PodScheduled`) should show `True`.

### Step 4: Inspect probe configurations

Use `jsonpath` to extract each probe's configuration directly from the pod spec. This confirms that all three probes are set and shows their parameters (path, port, intervals, thresholds).

```powershell
kubectl get pod -n lab1 -l app=healthy-app -o jsonpath='{.items[0].spec.containers[0].livenessProbe}' | ConvertFrom-Json
kubectl get pod -n lab1 -l app=healthy-app -o jsonpath='{.items[0].spec.containers[0].readinessProbe}' | ConvertFrom-Json
kubectl get pod -n lab1 -l app=healthy-app -o jsonpath='{.items[0].spec.containers[0].startupProbe}' | ConvertFrom-Json
```

You should see JSON objects with fields like `httpGet`, `periodSeconds`, `failureThreshold`, and `timeoutSeconds` for each probe.

### Discussion Answer

- **Liveness probe**: Tells Kubernetes whether the container is still alive. If it fails, kubelet **kills and restarts** the container. Use it to detect deadlocks or hung processes.
- **Readiness probe**: Tells Kubernetes whether the container is ready to accept traffic. If it fails, the pod is **removed from Service endpoints** but NOT restarted. Use it during startup or when the app temporarily can't serve requests.
- **Startup probe**: Runs only during container startup. Until it succeeds, liveness and readiness probes are disabled. Use it for **slow-starting applications** (e.g., Java apps loading large datasets) to avoid premature kills.

---

## Solution 2 — Simulate a Liveness Probe Failure

This exercise deploys a modified Nginx container that **starts healthy** (returns HTTP 200 on `/healthz`) but **becomes unhealthy after ~30 seconds** (switches to HTTP 500). This simulates an application crash or deadlock. Kubernetes detects the liveness failure and automatically restarts the container.

### Step 1: Deploy the failing application

This manifest uses a shell script inside the container that starts Nginx normally, then after 30 seconds reconfigures it to return 500 on the health endpoint.

```bash
kubectl apply -f labs/lab1-resiliency/solutions/manifests/02-liveness-failure.yaml
```

### Step 2: Watch the pod lifecycle

Keep this command running and observe. The pod starts as `Running` with 0 restarts. After ~45 seconds (30s healthy + 3 failed probes × 5s interval), you'll see the RESTARTS counter increment as Kubernetes kills and recreates the container.

```bash
kubectl get pods -n lab1 -l app=liveness-fail -w
```

Expected output over time:
```
NAME                             READY   STATUS    RESTARTS   AGE
liveness-fail-xxxxx-yyyyy        1/1     Running   0          10s
liveness-fail-xxxxx-yyyyy        1/1     Running   1 (2s ago) 50s
liveness-fail-xxxxx-yyyyy        1/1     Running   2 (2s ago) 1m40s
```

### Step 3: Check events

Use `describe` to see the full event history for the pod. This is the key debugging command — it shows exactly why Kubernetes restarted the container.

```bash
kubectl describe pod -n lab1 -l app=liveness-fail
```

In the **Events** section at the bottom, look for these two entries:
```
Warning  Unhealthy  Liveness probe failed: HTTP probe failed with statuscode: 500
Normal   Killing    Container liveness-fail failed liveness probe, will be restarted
```

### Step 4: Clean up

Remove this deployment before moving to the next exercise to keep the namespace clean.

```bash
kubectl delete -f labs/lab1-resiliency/solutions/manifests/02-liveness-failure.yaml
```

### Discussion Answer

- If a liveness probe keeps failing indefinitely, Kubernetes **keeps restarting** the container, eventually entering `CrashLoopBackOff` with exponentially increasing delays between restarts (10s, 20s, 40s... up to 5 minutes).
- **Liveness failure** = container is restarted. **Readiness failure** = container stays running but receives no traffic. A readiness failure is less disruptive because the pod stays alive and can recover without losing in-memory state.

---

## Solution 3 — Simulate a Readiness Probe Failure

This exercise deploys an Nginx container that **starts ready** (serves a file at `/ready`) but **becomes unready after ~20 seconds** (the file is deleted, causing 404 responses). Unlike the liveness failure in Solution 2, the pod is **NOT restarted** — instead, Kubernetes removes it from the Service endpoints so no new traffic reaches it. A ClusterIP Service is included so you can observe the endpoint changes.

### Step 1: Deploy the application and service

This manifest creates both a Deployment (with readiness + liveness probes) and a Service. The liveness probe always passes (checks `/`), so the pod stays alive. Only the readiness probe fails.

```bash
kubectl apply -f labs/lab1-resiliency/solutions/manifests/03-readiness-failure.yaml
```

### Step 2: Watch pods (Terminal 1)

In one terminal, watch the pods. After ~20 seconds, the READY column changes from `1/1` to `0/1` — the pod is still running but no longer ready to receive traffic.

```bash
kubectl get pods -n lab1 -l app=readiness-fail -w
```

Expected:
```
NAME                              READY   STATUS    RESTARTS   AGE
readiness-fail-xxxxx-yyyyy        1/1     Running   0          5s
readiness-fail-xxxxx-yyyyy        0/1     Running   0          25s    # <-- becomes unready
```

### Step 3: Watch endpoints (Terminal 2)

In a second terminal, watch the Service endpoints. You'll see the pod's IP appear initially, then disappear when readiness fails — proving that Kubernetes stops routing traffic to unready pods.

```bash
kubectl get endpoints -n lab1 readiness-fail-svc -w
```

Expected:
```
NAME                 ENDPOINTS         AGE
readiness-fail-svc   10.0.0.15:80      5s
readiness-fail-svc   <none>            25s    # <-- removed from endpoints
```

### Step 4: Verify Service endpoints

You can also inspect the Service directly. The `Endpoints` field confirms whether any pods are currently receiving traffic.

```bash
kubectl describe svc readiness-fail-svc -n lab1
```

The `Endpoints` field shows `<none>` — no traffic reaches this pod. Notice the pod is still `Running` (not restarted) — that's the key difference from liveness failures.

### Step 5: Clean up

Remove the deployment and service before the next exercise.

```bash
kubectl delete -f labs/lab1-resiliency/solutions/manifests/03-readiness-failure.yaml
```

### Discussion Answer

- **Rolling updates**: During an update, Kubernetes waits for the new pod to pass its readiness probe before terminating the old one. This ensures zero-downtime deployments — users never see an unready pod.
- **In-flight requests**: When a pod becomes unready, it is removed from the Service endpoints. New requests are not routed to it. However, **existing connections may still be active** depending on the `terminationGracePeriodSeconds` and application behavior. Use `preStop` hooks for graceful shutdown.

---

## Solution 4 — Self-Healing with ReplicaSets

This exercise demonstrates Kubernetes' **self-healing** capability. You deploy an Nginx Deployment with 3 replicas and a topology spread constraint (to distribute pods across nodes). Then you deliberately delete pods and watch Kubernetes instantly recreate them to maintain the desired count.

### Step 1: Deploy a replicated application

This manifest creates a 3-replica Nginx Deployment with a ClusterIP Service. The `topologySpreadConstraints` ensure pods are distributed across different nodes for better availability.

```bash
kubectl apply -f labs/lab1-resiliency/solutions/manifests/04-self-healing.yaml
```

### Step 2: Verify replicas

Check that all 3 pods are running. The `-o wide` flag shows which node each pod landed on.

```bash
kubectl get pods -n lab1 -l app=self-healing -o wide
```

You should see 3 pods in `Running` state. If you have multiple nodes, they should be on different nodes. With a single node, all 3 will be on the same node (the topology constraint uses `DoNotSchedule`, but Kubernetes still schedules when there's only one option).

### Step 3: Delete a single pod

Open two terminals. In the first, start watching pods so you can see the replacement appear in real time. In the second, delete one pod and observe how quickly the ReplicaSet controller creates a new one.

```powershell
# Terminal 1 — Watch
kubectl get pods -n lab1 -l app=self-healing -w

# Terminal 2 — Delete first pod
$POD_NAME = kubectl get pod -n lab1 -l app=self-healing -o jsonpath='{.items[0].metadata.name}'
kubectl delete pod -n lab1 $POD_NAME --grace-period=0 --force
```

A replacement pod appears almost instantly — you'll see a new pod name in the watch output within seconds. The total count never drops below 3 for long.

### Step 4: Delete ALL pods

Now try deleting all 3 pods at once. This is a more extreme scenario, but Kubernetes handles it the same way — the ReplicaSet controller immediately creates 3 new pods.

```bash
kubectl delete pods -n lab1 -l app=self-healing --grace-period=0 --force
kubectl get pods -n lab1 -l app=self-healing -w
```

All 3 pods are recreated immediately. Notice the new pods have different names — Kubernetes doesn't "repair" pods, it replaces them entirely.

### Discussion Answer

- **ReplicaSet controller**: Runs in the control plane and continuously reconciles the actual number of pods with the desired count. If pods are deleted, it creates new ones. If there are too many, it terminates extras.
- **Deployment vs ReplicaSet**: A Deployment manages ReplicaSets and adds **rolling update** capabilities (strategy, rollback, revision history). Never create bare ReplicaSets in production — always use Deployments.

---

## Solution 5 — Pod Disruption Budgets (PDB)

A PDB tells Kubernetes: "during voluntary disruptions (node drains, cluster upgrades), always keep at least N pods available." This exercise adds a PDB requiring **at least 2 of 3 pods** to remain running. You then drain a node and observe how Kubernetes respects this constraint.

### Step 1: Deploy app with PDB

First, clean up the previous exercise (the PDB manifest includes the same Deployment, so we avoid conflicts):

```powershell
kubectl delete -f labs/lab1-resiliency/solutions/manifests/04-self-healing.yaml 2>$null
```

Then deploy the same 3-replica Nginx Deployment, now with a PDB that enforces `minAvailable: 2`:

```bash
kubectl apply -f labs/lab1-resiliency/solutions/manifests/05-pdb.yaml
```

### Step 2: Check PDB status

Verify the PDB was created. The `ALLOWED DISRUPTIONS` column tells you how many pods can be evicted right now without violating the budget.

```bash
kubectl get pdb -n lab1
```

Expected output:
```
NAME               MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS   AGE
self-healing-pdb   2               N/A               1                     10s
```

### Step 3: Drain a node

```powershell
# Find a node running one of the pods
$NODE = kubectl get pods -n lab1 -l app=self-healing -o jsonpath='{.items[0].spec.nodeName}'
Write-Host "Draining node: $NODE"

# Drain it
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data --grace-period=30
```

### Step 4: Uncordon the node

After observing the drain behavior, uncordon the node to allow pods to be scheduled on it again. This is essential — a cordoned node rejects all new pods.

```powershell
kubectl uncordon $NODE
```

### Step 5: Clean up

Remove the Deployment, Service, and PDB.

```bash
kubectl delete -f labs/lab1-resiliency/solutions/manifests/05-pdb.yaml
```

### Discussion Answer

- **PDB violation**: If draining a node would cause available pods to drop below `minAvailable`, the drain command **blocks and waits**. It will keep retrying until a new pod is scheduled on another node and becomes ready, allowing the eviction to proceed.
- **PDB + Autoscaler**: The cluster autoscaler respects PDBs when scaling down nodes. If removing a node would violate a PDB, the autoscaler skips that node. This can sometimes prevent scale-down — make sure your PDB values make sense for your replica count.

---

## Solution 6 — Node Auto-Repair

AKS has built-in **node auto-repair**: it continuously monitors node health and automatically recovers unhealthy nodes through a graduated process (reboot → reimage → replace). In this exercise you don't break anything — you learn how to check node health and understand the auto-repair process.

### Step 1: Check node health

Inspect the node conditions. A healthy node has `Ready = True` and all pressure conditions (`MemoryPressure`, `DiskPressure`, `PIDPressure`) set to `False`.

```powershell
kubectl get nodes
kubectl describe nodes | Select-String -Pattern 'Conditions:' -Context 0,5
```

Healthy output:
```
Conditions:
  Type                 Status
  MemoryPressure       False
  DiskPressure         False
  PIDPressure          False
  Ready                True
```

### Step 2: Monitor in real-time

These commands let you watch for node status changes and `NodeNotReady` events. In a real incident, this is how you'd detect node failures as they happen.

```bash
kubectl get nodes -w
kubectl get events --field-selector reason=NodeNotReady
```

If all nodes are healthy, the events query returns nothing — that's a good sign!

### Step 3: Check from Azure CLI

You can also verify node pool health from the Azure side. This shows the pool's power state and node count, which is useful when nodes are being replaced and temporarily absent from `kubectl get nodes`.

```powershell
az aks show --resource-group rg-devai-hackathon --name devai-hackathon-aks --query "agentPoolProfiles[0].{name:name, count:count, powerState:powerState}" -o table
```

### Auto-repair process summary

| Check interval | 5 minutes |
|---|---|
| Trigger threshold | Node `NotReady` for 10+ consecutive minutes |
| Step 1 | **Reboot** — soft reboot of the VM |
| Step 2 | **Reimage** — reimage from OS image |
| Step 3 | **Replace** — delete VM and create a new one |

### Discussion Answer

- **Why not immediate replace?** Transient issues (network blips, temporary resource pressure) often resolve themselves. Immediately replacing a node causes unnecessary disruption — pods are evicted, data on local volumes is lost, and a new VM takes time to provision. The graduated approach (reboot → reimage → replace) minimizes disruption.
- **Manual node operations**: SSH-ing into nodes and manually killing processes (kubelet, container runtime) can trigger unnecessary auto-repair cycles, confuse the control plane, and cause unexpected pod rescheduling. Always use Kubernetes-native operations (cordon, drain) for maintenance.

---

## Solution 7 — Cleanup

Delete the entire `lab1` namespace. This removes all resources (Deployments, Services, PDBs, pods) created during this lab in one command.

```bash
kubectl delete namespace lab1
```

Verify everything is gone:

```bash
kubectl get all -n lab1
# Expected: No resources found in lab1 namespace.
```
