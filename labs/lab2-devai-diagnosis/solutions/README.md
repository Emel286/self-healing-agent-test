# Lab 2 — Solutions

## Solution 1 — Diagnose a CrashLoopBackOff

This exercise deploys an Nginx container with a **broken startup command** (`/bin/start-app`) that doesn't exist in the image. The container fails to start (exit code 128 = start error), and Kubernetes keeps restarting it — creating the classic CrashLoopBackOff cycle.

### Step 1: Observe the problem

Watch the pod status. You'll see RESTARTS incrementing and the status cycling between `Running`, `Error`, and `CrashLoopBackOff`.

```powershell
kubectl get pods -n lab2 -l app=crashloop-app -w
```

Expected:
```
NAME                              READY   STATUS             RESTARTS   AGE
crashloop-app-xxxxx-yyyyy         0/1     CrashLoopBackOff   3          2m
```

### Step 2: Check events

Use `describe` to see the event history. The key clue is the `BackOff` event and the container's exit code.

```powershell
kubectl describe pod -n lab2 -l app=crashloop-app
```

Look in the Events section for:
```
Warning  BackOff  Back-off restarting failed container
```

### Step 3: Check logs

The `--previous` flag shows logs from the last terminated container. Use the specific pod name (from `kubectl get pods`) rather than a label selector, as `-l` with `--previous` can silently return nothing.

```powershell
# Get the pod name
$POD = kubectl get pods -n lab2 -l app=crashloop-app -o jsonpath='{.items[0].metadata.name}'

# Check previous container logs
kubectl logs -n lab2 $POD --previous
```

> **Note:** If the logs are empty, the container crashes too fast to produce output. In that case, use `kubectl describe pod` and look at the **Last State** section — the `Exit Code` and `Reason` are the key clues. Exit code **128** with reason **StartError** means the command could not be executed.

```powershell
kubectl describe pod -n lab2 $POD | Select-String -Pattern 'State:|Reason:|Exit Code:|Command:'
```

Expected output:
```
    Command:
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       StartError
      Exit Code:    128
```

The `StartError` reason with exit code 128 combined with the `Command` field in the pod spec tells us it's trying to execute `/bin/start-app` which doesn't exist in the nginx image.

### Step 4: Ask Copilot

**Prompt example:**
> My pod is in CrashLoopBackOff. Here are the events and describe output:
> - Event: "Back-off restarting failed container"
> - Last State: Terminated, Reason: StartError, Exit Code: 128
> - The pod spec has `command: ["/bin/start-app"]`
>
> The pod uses `nginx:1.27-alpine` as the base image. What's wrong and how do I fix it?

**Expected Copilot response:** The container command `/bin/start-app` doesn't exist in the nginx image. Exit code 128 with StartError means the runtime could not execute the specified command. Remove the custom command or change it to the correct entrypoint.

### Step 5: Apply the fix

The fix removes the custom command and lets the image's default entrypoint (`nginx -g 'daemon off;'`) run.

```powershell
kubectl apply -f labs/lab2-devai-diagnosis/solutions/manifests/01-crashloop-fix.yaml
```

### Step 6: Verify the fix

Confirm the pod is now running healthy — no more CrashLoopBackOff, no restarts, and READY `1/1`.

```powershell
kubectl get pods -n lab2 -l app=crashloop-app
```

Expected output:
```
NAME                              READY   STATUS    RESTARTS   AGE
crashloop-app-xxxxx-yyyyy         1/1     Running   0          15s
```

You can also verify the root cause is gone by comparing the broken vs fixed pod spec. The original had `command: ["/bin/start-app"]` — the fix should show the default nginx image command instead:

```powershell
$POD = kubectl get pods -n lab2 -l app=crashloop-app -o jsonpath='{.items[0].metadata.name}'
kubectl get pod -n lab2 $POD -o yaml | Select-String -Pattern 'command|image:'
```

Expected output — only the `image:` lines appear, with **no `command:` line**:
```
  - image: nginx:1.27-alpine
    image: docker.io/library/nginx:1.27-alpine
```

If you saw `- /bin/start-app` in this output, the fix wasn't applied correctly.

### Root cause

The Deployment specifies `command: ["/bin/start-app"]` which doesn't exist in the nginx image. The fix is to remove the custom command and let the image's default entrypoint (`nginx -g 'daemon off;'`) run.

### Discussion Answer

- **More context = better diagnosis**: Providing the exit code (128 = start error), the container image, and the describe output lets AI immediately pinpoint the issue. Without this, AI would list 10+ generic CrashLoopBackOff causes.
- **Minimum context**: Container image, exit code, reason, and the command from the pod spec. This is usually enough for common failures.

---

## Solution 2 — Fix an ImagePullBackOff

This exercise deploys a pod referencing a **misspelled image** (`nginxxx:latest` instead of `nginx:latest`). Kubernetes can't pull it from any registry and the pod enters ImagePullBackOff.

### Step 1: Observe the problem

The pod status shows `ErrImagePull` or `ImagePullBackOff`. The events describe exactly which image failed.

```powershell
kubectl get pods -n lab2 -l app=imagepull-app
kubectl describe pod -n lab2 -l app=imagepull-app
```

Events show:
```
Warning  Failed   Failed to pull image "nginxxx:latest": rpc error ... not found
Warning  Failed   Error: ImagePullBackOff
```

### Step 2: Identify the issue

The image name is `nginxxx:latest` — a typo. The correct image is `nginx:latest`.

### Step 3: Ask Copilot

**Prompt example:**
> My pod has ImagePullBackOff with this event: "Failed to pull image nginxxx:latest: not found". What's wrong?

**Expected Copilot response:** The image name `nginxxx` is likely a typo. The correct image name for the popular web server is `nginx`. Change your image reference to `nginx:latest` or a specific tag like `nginx:1.27-alpine`.

### Step 4: Apply the fix

The fix changes the image from `nginxxx:latest` to `nginx:1.27-alpine`.

```powershell
kubectl apply -f labs/lab2-devai-diagnosis/solutions/manifests/02-imagepull-fix.yaml
```

### Step 5: Verify the fix

Confirm the pod is now running healthy — no more ImagePullBackOff, no restarts, and READY `1/1`.

```powershell
kubectl get pods -n lab2 -l app=imagepull-app
```

Expected output:
```
NAME                              READY   STATUS    RESTARTS   AGE
imagepull-app-xxxxx-yyyyy         1/1     Running   0          15s
```

You can also verify the root cause is gone by checking the image reference in the running pod. The original had `nginxxx:latest` — the fix should show the correct `nginx:1.27-alpine` image:

```powershell
kubectl get pod -n lab2 -l app=imagepull-app -o yaml | Select-String -Pattern 'image:'
```

Expected output — the correct `nginx:1.27-alpine` image, **not** `nginxxx:latest`:
```
    - image: nginx:1.27-alpine
      image: docker.io/library/nginx:1.27-alpine
```

If you still see `nginxxx:latest` in this output, the fix wasn't applied correctly.

### Root cause

The Deployment specifies `image: nginxxx:latest` — a typo. The correct image name is `nginx`. The fix changes it to `nginx:1.27-alpine`, a pinned tag that's deterministic and avoids the pitfalls of `latest`.

### Discussion Answer

Common ImagePull failure categories:
1. **Wrong image name** (typo) — `nginxxx` instead of `nginx`
2. **Wrong tag** — `nginx:v99` doesn't exist
3. **Private registry auth** — missing `imagePullSecrets`
4. **Rate limiting** — Docker Hub rate limits for anonymous pulls
5. **Registry unavailable** — network issues or registry downtime

In CI/CD, you can automate detection by: validating image references against a registry before deploy, using image scanning tools, and implementing admission controllers that reject unknown images.

---

## Solution 3 — Diagnose Resource Constraint Issues

This exercise deploys a pod requesting **64Gi of memory** — far more than the 8 GiB available on our Standard_D2s_v3 nodes. The pod stays in `Pending` forever because no node can satisfy the request.

### Step 1: Observe the problem

The pod shows `Pending` status. Unlike CrashLoopBackOff or ImagePullBackOff, this pod never even starts — the scheduler can't find a node for it.

```powershell
kubectl get pods -n lab2 -l app=resource-hog
```

Expected output — notice `Pending` status and `0/1` READY with **0 restarts** (it never ran):
```
NAME                            READY   STATUS    RESTARTS   AGE
resource-hog-xxxxx-yyyyy        0/1     Pending   0          7m
```

Now check the events to understand **why** it's Pending. The `describe` output contains the scheduler's reasoning.

```powershell
kubectl describe pod -n lab2 -l app=resource-hog
```

Look at two sections — the **resource requests** and the **Events**:

Resource requests (in the Containers section):
```
    Requests:
      cpu:        100m
      memory:     64Gi
```

Events:
```
Warning  FailedScheduling   0/1 nodes are available: 1 Insufficient memory. preemption: 0/1 nodes are available: 1 Preemption is not helpful for scheduling.
Normal   NotTriggerScaleUp  pod didn't trigger scale-up: 1 Insufficient memory
```

> **Key insight:** The `FailedScheduling` event tells you exactly what resource is missing and how many nodes were evaluated. The `NotTriggerScaleUp` event means even the cluster autoscaler couldn't help — the VM size itself is too small for 64Gi.

### Step 2: Check node resources

Compare what the pod requests (64Gi) with what the nodes actually have. Two commands give you the full picture:

**`kubectl top nodes`** shows real-time CPU and memory **utilization** (what's actively being used right now):

```powershell
kubectl top nodes
```

Expected output:
```
NAME                                 CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)
aks-systempool-xxxxx-vmssXXXXXX      217m         11%      1556Mi          21%
```

> The node has ~7.2 GiB total memory (Standard_D2s_v3 = 8 GiB, minus OS/system overhead). Only ~1.5 GiB is currently **in use** — but that's not what matters for scheduling. The scheduler looks at **requests**, not actual usage.

**`kubectl describe nodes`** shows committed resource **requests** — what pods have reserved, whether they're using it or not:

```powershell
kubectl describe nodes | Select-String -Pattern 'Allocated resources:' -Context 0,8
```

Expected output:
```
Allocated resources:
  (Total limits may be over 100 percent, i.e., overcommitted.)
  Resource           Requests      Limits
  --------           --------      ------
  cpu                1252m (65%)   10682m (562%)
  memory             1474Mi (20%)  13904160Ki (188%)
  ephemeral-storage  0 (0%)        0 (0%)
  hugepages-1Gi      0 (0%)        0 (0%)
  hugepages-2Mi      0 (0%)        0 (0%)
```

> The node has ~7.2 GiB allocatable memory with ~1.4 GiB already requested by other pods. Even if **nothing else** was running, 64Gi far exceeds the node's total 8 GiB physical memory.

### Step 3: Identify the issue

The pod requests 64Gi of memory — far more than the ~7.2 GiB allocatable on a Standard_D2s_v3 node. No amount of freeing up existing pods would help — the request exceeds the physical memory of the VM.

### Step 4: Ask Copilot

**Prompt example:**
> My pod is Pending with: "0/1 nodes are available: 1 Insufficient memory." The pod requests 64Gi memory. My node is Standard_D2s_v3 (8 GiB). What should I do?

**Expected Copilot response:** Standard_D2s_v3 VMs have 8 GiB of memory. Your pod requests 64Gi which exceeds the node's capacity. Reduce the memory request to fit within available resources (e.g., 256Mi–1Gi for most workloads) or scale up to larger VM sizes.

### Step 5: Apply the fix

The fix reduces the memory request from 64Gi to 128Mi and limits to 256Mi — realistic values for an Nginx container.

```powershell
kubectl apply -f labs/lab2-devai-diagnosis/solutions/manifests/03-resource-constraint-fix.yaml
```

### Step 6: Verify the fix

Confirm the pod is no longer `Pending` — it should now be `Running` with READY `1/1` and 0 restarts.

```powershell
kubectl get pods -n lab2 -l app=resource-hog
```

Expected output:
```
NAME                            READY   STATUS    RESTARTS   AGE
resource-hog-xxxxx-yyyyy        1/1     Running   0          55s
```

Verify the root cause is gone by checking the resource requests/limits in the running pod. The original had `memory: 64Gi` — the fix should show realistic values:

```powershell
kubectl get pod -n lab2 -l app=resource-hog -o yaml | Select-String -Pattern 'memory:|cpu:'
```

Expected output — you should see `128Mi` requests and `256Mi` limits, **not** `64Gi`:
```
          cpu: 200m
          memory: 256Mi
          cpu: 100m
          memory: 128Mi
```

> The first pair (`200m`/`256Mi`) is the **limits**, the second pair (`100m`/`128Mi`) is the **requests**. These values fit comfortably on a Standard_D2s_v3 node, so the scheduler can place the pod.

If you still see `64Gi` in this output, the fix wasn't applied correctly.

### Root cause

The Deployment requests `64Gi` of memory — 8x more than the node's total 8 GiB physical memory. The scheduler cannot place the pod on any node, so it stays `Pending` indefinitely. The fix reduces the request to `128Mi` and limit to `256Mi`, which are realistic for an Nginx container.

### Discussion Answer

- **Scheduler logic**: The scheduler filters nodes that meet resource requests (Filtering phase), then ranks remaining nodes by score (Scoring phase). If no node passes filtering, the pod stays Pending.
- **Requests vs Limits**: `requests` = guaranteed minimum resources (used for scheduling). `limits` = maximum the container can use (enforced at runtime). If a container exceeds its memory limit, it's OOM-killed. If it exceeds CPU limit, it's throttled.
- **AI for right-sizing**: AI can analyze historical resource usage from metrics (Prometheus/Insights) and recommend optimal requests/limits — tools like Kubernetes VPA (Vertical Pod Autoscaler) do this automatically.

---

## Solution 4 — Generate Kubernetes YAML with Copilot

### Sample prompt for Copilot

> Generate a Kubernetes Deployment and Service manifest for a Node.js application with these requirements:
> - Image: node:20-alpine
> - 3 replicas
> - Container port 3000
> - CPU request 100m, limit 200m
> - Memory request 128Mi, limit 256Mi
> - Liveness probe on /healthz port 3000
> - Readiness probe on /ready port 3000
> - Startup probe on /healthz port 3000
> - ClusterIP Service on port 80 targeting 3000
> - Security hardened: non-root user, read-only root filesystem, drop all capabilities

### Expected output review

A good AI-generated manifest should include:
- Correct `apiVersion: apps/v1` for Deployment
- Matching label selectors (`spec.selector.matchLabels` = `spec.template.metadata.labels`)
- All three probes with appropriate thresholds
- `securityContext` with `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, and `capabilities: { drop: [ALL] }`
- Resource requests and limits

### Common AI misses on first pass

1. **Security context** — often omitted unless explicitly asked
2. **Pod Disruption Budget** — almost never auto-generated
3. **Topology spread constraints** — rarely included
4. **Image pull policy** — defaults may not be ideal
5. **Service account** — often uses default, which may have too many permissions

### Follow-up prompt

> Now add a PodDisruptionBudget with minAvailable 2, add topology spread constraints across nodes, and ensure the pod uses a dedicated ServiceAccount with automountServiceAccountToken: false.

### Reference solution

See `labs/lab2-devai-diagnosis/solutions/manifests/04-generated-app.yaml` for a complete, security-hardened manifest.

### Discussion Answer

**Risks of blindly applying AI-generated YAML:**
- May use deprecated API versions
- Default security settings are often too permissive
- Resource values may be unrealistic for the workload
- Image tags like `latest` are non-deterministic

**Validation steps for GitOps:**
1. Schema validation (`kubectl --dry-run=server`)
2. Policy enforcement (OPA/Gatekeeper, Kyverno)
3. Security scanning (Trivy, Kubescape)
4. Peer review in pull request

---

## Solution 5 — Context Engineering for Effective Diagnosis

This exercise deploys a **multi-container pod** (main Nginx app + busybox sidecar) where the sidecar crashes because it expects a config file at `/shared-data/config.yaml` that doesn't exist. The main container runs fine — only the sidecar fails, making this a subtler issue that requires inspecting logs from the right container.

### Step 1: Observe the problem

The pod shows `1/2` READY — meaning one container is running but the other is failing. This is different from previous exercises where the entire pod was broken. Here, you need to figure out **which** container is crashing.

```powershell
kubectl get pods -n lab2 -l app=multi-container-app
```

Expected output — notice `1/2` READY and the sidecar's restarts incrementing:
```
NAME                                   READY   STATUS             RESTARTS        AGE
multi-container-app-xxxxx-yyyyy        1/2     CrashLoopBackOff   6 (102s ago)    7m
```

> **Key insight:** `1/2` means one of two containers is ready. The pod isn't in `Error` — the main container (`main-app`) is running fine. Only the `sidecar` container keeps crashing. This is a subtler bug that requires inspecting **each container separately**.

### Step 2: Gather context

With multi-container pods, you need to check logs for **each container separately** using the `-c` flag. Also gather events and node status for a complete picture.

**Pod description** — shows the state of each container individually:

```powershell
kubectl describe pod -n lab2 -l app=multi-container-app
```

Look at the container states in the describe output:
```
  main-app:
    State:          Running
    Ready:          True
    Restart Count:  0
  sidecar:
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       Error
      Exit Code:    1
    Ready:          False
    Restart Count:  7
```

> The `main-app` is `Running` with 0 restarts — it's healthy. The `sidecar` has exit code **1** (generic error) and keeps restarting. Exit code 1 means the script failed — we need to check its logs to find out why.

**Logs from main container** — confirm it's running fine:

```powershell
kubectl logs -n lab2 -l app=multi-container-app -c main-app
```

Expected output — normal nginx startup:
```
/docker-entrypoint.sh: Configuration complete; ready for start up
```

**Logs from sidecar container** — this is where the clue is:

```powershell
kubectl logs -n lab2 -l app=multi-container-app -c sidecar --previous
```

Expected output — the actual error:
```
Starting sidecar...
cat: can't open '/shared-data/config.yaml': No such file or directory
```

> The sidecar tries to `cat /shared-data/config.yaml` but the file doesn't exist. The volume is an `emptyDir` which starts empty — nobody creates the config file.

**Namespace events** — confirm the BackOff pattern:

```powershell
kubectl get events -n lab2 --sort-by='.lastTimestamp'
```

**Node status** — rule out resource issues:

```powershell
kubectl top nodes
```

### Step 3: Compare prompt quality

**Bad prompt:**
> My pod is broken, fix it.

**AI response:** Generic list of 10+ possible issues with no specificity.

**Good prompt:**
> I have a multi-container pod in namespace lab2 with two containers: `main-app` (nginx) and `sidecar` (busybox).
>
> **Symptoms:** Pod is Running but only 1/2 containers are ready. The sidecar container keeps restarting.
>
> **Sidecar logs:**
> ```
> Starting sidecar...
> cat: can't open '/shared-data/config.yaml': No such file or directory
> ```
>
> **Pod events:**
> ```
> Warning  BackOff  Back-off restarting failed container sidecar
> ```
>
> **Pod spec** uses an emptyDir volume mounted at /shared-data in both containers. The sidecar expects a config file that neither container creates.
>
> What's the root cause and how do I fix it?

**AI response:** Precise diagnosis — the sidecar depends on a config file that should be provided via a ConfigMap or init container, not an empty emptyDir volume. Suggests creating a ConfigMap with the expected config.yaml and mounting it.

### Step 4: Apply the fix

The fix adds a ConfigMap with the expected `config.yaml` content and mounts it into the sidecar's `/shared-data` path.

```powershell
kubectl apply -f labs/lab2-devai-diagnosis/solutions/manifests/05-multi-container-fix.yaml
```

### Step 5: Verify the fix

Confirm **both** containers are now running — READY should show `2/2` with 0 restarts.

```powershell
kubectl get pods -n lab2 -l app=multi-container-app
```

Expected output:
```
NAME                                   READY   STATUS    RESTARTS   AGE
multi-container-app-xxxxx-yyyyy        2/2     Running   0          30s
```

Verify the sidecar can now read the config file:

```powershell
kubectl logs -n lab2 -l app=multi-container-app -c sidecar | Select-Object -First 3
```

Expected output — the sidecar successfully reads the config:
```
Starting sidecar...
Config loaded, entering monitoring loop...
```

If you still see `can't open '/shared-data/config.yaml'`, the fix wasn't applied correctly.

### Root cause

The sidecar container expects `/shared-data/config.yaml` to exist, but it's mounted from an `emptyDir` volume which starts empty. The fix is to use a ConfigMap to provide the expected configuration file.

### Context engineering principles applied

| Principle | How it was applied |
|-----------|-------------------|
| **Gather before concluding** | Collected logs from both containers and events before hypothesizing |
| **Structured context** | Organized into Symptoms → Logs → Events → Spec |
| **Domain-specific framing** | Used K8s terminology (sidecar, emptyDir, container names) |
| **Iterative refinement** | Started with describe, then targeted specific container logs |

---

## Solution 6 — End-to-End AI-Assisted Troubleshooting

This is the capstone challenge. The deployed application has **three different issues stacked together**: wrong container port, invalid readiness probe path, and memory limits too low (causing OOM kills). You need to find and fix all of them.

### Step 1: Observe all problems

Start with a broad survey. Check pod status, events, logs, and the Service configuration. With multiple issues, the first error you see may mask others underneath.

**Check pod status** — as expected, the pods are stuck in `CrashLoopBackOff` / `OOMKilled` with `0/1` READY:

```powershell
kubectl get pods -n lab2 -l app=broken-app
```

Expected output — both replicas are failing, cycling between `OOMKilled` and `CrashLoopBackOff`:
```
NAME                          READY   STATUS             RESTARTS        AGE
broken-app-xxxxx-yyyyy        0/1     CrashLoopBackOff   3 (47s ago)     3m
broken-app-xxxxx-zzzzz        0/1     OOMKilled          0               3m
```

> **Key insight:** `OOMKilled` tells you the container exceeded its memory limit and was killed by the kernel. `CrashLoopBackOff` follows because K8s keeps restarting it. This is a strong clue that the memory limit is too low.

**Check describe** — reveals all three issues at once: wrong port, wrong probe path, and tiny memory limit:

```powershell
kubectl describe pod -n lab2 -l app=broken-app
```

Look at these key sections in the describe output:
```
    Port:           8080/TCP
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
      memory:  4Mi
    Liveness:     http-get http://:8080/ delay=0s timeout=1s period=10s #success=1 #failure=3
    Readiness:    http-get http://:8080/healthcheck delay=0s timeout=1s period=5s #success=1 #failure=2
```

> Three problems are visible: **Port 8080** (nginx listens on 80), **readiness probe path `/healthcheck`** (returns 404 on nginx), and **memory limit 4Mi** (OOMKilled with exit code 137).

**Check logs** — nginx starts fine (when it has enough memory), confirming the image itself is correct:

```powershell
kubectl logs -n lab2 -l app=broken-app
```

Expected output — normal nginx startup (before it gets OOMKilled):
```
/docker-entrypoint.sh: Configuration complete; ready for start up
```

**Check the Service** — the service exists but targets port 8080, which nginx doesn't listen on:

```powershell
kubectl get svc -n lab2
```

Expected output:
```
NAME             TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)   AGE
broken-app-svc   ClusterIP   172.16.x.x       <none>        80/TCP    5m
```

> The Service itself is on port 80 (correct), but check the `targetPort` — it targets 8080 which means traffic would never reach nginx even if the pod was healthy.

**Check events** — shows the readiness probe failure and the OOM pattern:

```powershell
kubectl get events -n lab2 --sort-by='.lastTimestamp'
```

Key events to look for:
```
Warning  Unhealthy  Readiness probe failed: Get "http://10.0.0.x:8080/healthcheck": dial tcp ... connection refused
Warning  BackOff    Back-off restarting failed container web
```

> The readiness probe fails with `connection refused` on port 8080 — because nginx is listening on port 80, not 8080. The BackOff event confirms the OOMKill → restart cycle.

### Step 2: Ask Copilot — feed all context in one prompt

This is the capstone payoff: instead of diagnosing issues one at a time, you feed **all** the context from Step 1 into a single, structured prompt. The AI should identify all three issues at once.

**Prompt example:**

> I have a broken Deployment called `broken-app` in namespace `lab2` using `nginx:1.27-alpine`. Two replicas are both failing. Here's everything I gathered:
>
> **Pod status:**
> ```
> broken-app-xxxxx-yyyyy   0/1   CrashLoopBackOff   3 (47s ago)   3m
> broken-app-xxxxx-zzzzz   0/1   OOMKilled           0             3m
> ```
>
> **From `kubectl describe pod`:**
> ```
> Port:        8080/TCP
> Last State:  Terminated
>   Reason:    OOMKilled
>   Exit Code: 137
> Limits:
>   memory: 4Mi
> Liveness:  http-get http://:8080/ delay=0s
> Readiness: http-get http://:8080/healthcheck delay=0s
> ```
>
> **Logs** (when the container survives long enough):
> ```
> /docker-entrypoint.sh: Configuration complete; ready for start up
> ```
>
> **Service:**
> ```
> broken-app-svc   ClusterIP   172.16.x.x   <none>   80/TCP
> ```
> The service `targetPort` is 8080.
>
> **Events:**
> ```
> Warning  Unhealthy  Readiness probe failed: dial tcp 10.0.0.x:8080: connection refused
> Warning  BackOff    Back-off restarting failed container web
> ```
>
> nginx listens on port 80 by default. What are ALL the issues and how do I fix each one?

**Expected Copilot response** — should identify all three issues:

**Issue 1: Wrong container port**
- The Deployment specifies `containerPort: 8080` but nginx listens on port 80
- The Service `broken-app-svc` targets port 8080
- Both probes (liveness and readiness) check port 8080 — always failing with `connection refused`
- **Fix:** Change containerPort, Service targetPort, and probe ports to 80

**Issue 2: Invalid readiness probe path**
- Readiness probe checks `/healthcheck` which returns 404 on nginx (even on the correct port)
- Pod stays in `READY 0/1` — no traffic routed
- **Fix:** Change probe path to `/` or a valid endpoint

**Issue 3: Memory limit too low (4Mi)**
- Memory limit of `4Mi` causes OOM kills — nginx needs at least ~30Mi to start
- Container starts, gets OOM-killed (exit code **137**), restarts
- The `OOMKilled` status and exit code 137 are the clearest signals
- **Fix:** Increase memory limit to at least 64Mi (128Mi is a safe choice)

> **Why this works:** The prompt follows the context engineering principles from Solution 5 — structured sections (Status / Describe / Logs / Service / Events), concrete output pasted in, domain-specific framing (port, OOMKilled, probe path), and a clear ask ("What are ALL the issues"). Without this structure, the AI might only catch the most obvious issue (OOMKilled) and miss the port mismatch or the readiness path.

### Step 3: Apply the fix

The corrected manifest fixes all three issues: port 80, valid probe path, and reasonable memory limits.

```powershell
kubectl apply -f labs/lab2-devai-diagnosis/solutions/manifests/06-broken-app-fix.yaml
```

### Step 4: Verify

Confirm both replicas are now `Running` with READY `1/1` and 0 restarts — all three issues resolved at once.

```powershell
kubectl get pods -n lab2 -l app=broken-app
```

Expected output:
```
NAME                          READY   STATUS    RESTARTS   AGE
broken-app-xxxxx-yyyyy        1/1     Running   0          16s
broken-app-xxxxx-zzzzz        1/1     Running   0          13s
```

Verify all three fixes took effect — port, probe path, and memory:

```powershell
kubectl get pod -n lab2 -l app=broken-app -o yaml | Select-String -Pattern 'containerPort:|path: /|memory:|cpu:' | Select-String -NotMatch 'termination|serviceaccount|token|ca.crt|namespace|fieldPath'
```

Expected output — should show port `80`, probe path `/`, and realistic memory values:
```
          path: /
      - containerPort: 80
          path: /
          cpu: 100m
          memory: 128Mi
          cpu: 50m
          memory: 64Mi
```

Verify the Service now targets port 80 (was 8080):

```powershell
kubectl get svc -n lab2 broken-app-svc -o jsonpath='{.spec.ports[0].port}{" -> "}{.spec.ports[0].targetPort}'
```

Expected output:
```
80 -> 80
```

> All three fixes confirmed: `containerPort: 80` (was 8080), probe path `/` (was `/healthcheck`), memory `64Mi/128Mi` (was 4Mi). The Service correctly routes port 80 → targetPort 80.

### Root cause

Three stacked issues: (1) `containerPort: 8080` and Service `targetPort: 8080` but nginx listens on 80, (2) readiness probe path `/healthcheck` returns 404 on nginx, (3) memory limit `4Mi` causes OOMKill. The fix corrects all three in a single manifest update.

### Discussion Answer

**Automated diagnosis pipeline:**
1. **Observability layer**: Prometheus metrics, Loki logs, Tempo traces
2. **Anomaly detection**: AI monitors baseline metrics and alerts on deviations
3. **Context gathering**: Automated collection of pod events, logs, resource usage
4. **AI diagnosis**: Feed structured context to LLM for root cause analysis
5. **Suggested remediation**: AI proposes fix, human approves (or auto-approve with guardrails)
6. **Verification**: Automated checks confirm fix resolved the issue

**Limitations of AI-assisted troubleshooting:**
- Can't access runtime state directly (needs kubectl output as input)
- May suggest fixes that work in isolation but break dependencies
- Doesn't have knowledge of your specific architecture or business logic
- Hallucinations — may confidently suggest wrong solutions
- Works best as a **co-pilot** augmenting human expertise, not replacing it

---

## Solution 7 — Cleanup

Delete the entire `lab2` namespace. This removes all broken and fixed deployments created during this lab.

```powershell
kubectl delete namespace lab2
```

Verify everything is gone:

```powershell
kubectl get all -n lab2
# Expected: No resources found in lab2 namespace.
```
