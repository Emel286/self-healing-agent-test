"""
Remediation Agent — Executes safe fixes based on diagnosis output.

Usage:
    python remediation_agent.py --diagnosis-file diagnosis.json [--dry-run] [--execute]

Safety guardrails:
    - Dry-run mode (default): shows plan without executing
    - Approval gate: prompts for confirmation on high-risk actions
    - Blast radius check: refuses actions affecting too many pods
    - Rollback state: saves current state before changes
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


MAX_BLAST_RADIUS = 5  # Max pods affected by a single action
PROTECTED_NAMESPACES = {"kube-system", "kube-public", "kube-node-lease", "default"}
ROLLBACK_DIR = "rollback"


def run_kubectl(args: list[str], check: bool = False) -> str:
    """Run a kubectl command and return stdout."""
    result = subprocess.run(
        ["kubectl"] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"kubectl failed: {result.stderr}")
    return result.stdout or result.stderr


def save_rollback_state(namespace: str, resource_type: str, resource_name: str) -> str:
    """Save current resource state for rollback."""
    os.makedirs(ROLLBACK_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{ROLLBACK_DIR}/{resource_name}-{timestamp}.yaml"

    state = run_kubectl(["get", resource_type, resource_name, "-n", namespace, "-o", "yaml"])
    with open(filename, "w") as f:
        f.write(state)

    print(f"[REMEDIATE] Rollback state saved to {filename}")
    return filename


def check_guardrails(action: dict, diagnosis: dict) -> tuple[str, str]:
    """Check safety guardrails. Returns (status, reason)."""
    namespace = action.get("namespace", "")

    # Namespace protection
    if namespace in PROTECTED_NAMESPACES:
        return "blocked", f"Cannot modify protected namespace '{namespace}'"

    # Blast radius
    affected = action.get("affected_pods", 1)
    if affected > MAX_BLAST_RADIUS:
        return "blocked", f"Affects {affected} pods (max {MAX_BLAST_RADIUS})"

    # Risk-based approval
    risk = diagnosis.get("risk_level", "medium")
    if risk == "high":
        return "needs_approval", "High-risk action requires human approval"

    confidence = diagnosis.get("confidence", "low")
    if confidence == "low":
        return "needs_approval", "Low confidence diagnosis — verify before proceeding"

    return "approved", "All guardrails passed"


def get_approval(plan: str) -> bool:
    """Prompt for human approval."""
    print(f"\n[APPROVAL] Proposed action:\n{plan}")
    response = input("\n[APPROVAL] Execute this remediation? [y/n]: ").strip().lower()
    return response == "y"


def determine_action(diagnosis: dict) -> dict | None:
    """Determine the remediation action from the diagnosis."""
    root_cause = diagnosis.get("root_cause", "").lower()
    steps = diagnosis.get("remediation_steps", [])

    # Pattern matching on root cause
    if "oom" in root_cause or "memory" in root_cause:
        return {
            "type": "patch_memory",
            "description": "Increase memory limits",
            "resource_type": "deployment",
            "field": "memory",
            "new_value": "256Mi",
        }
    elif "image" in root_cause and ("pull" in root_cause or "not found" in root_cause):
        return {
            "type": "patch_image",
            "description": "Fix image reference",
        }
    elif "command" in root_cause or "entrypoint" in root_cause or "not found" in root_cause:
        return {
            "type": "restart_pods",
            "description": "Restart pods after fixing the deployment spec",
        }
    elif "crash" in root_cause or "restart" in root_cause:
        return {
            "type": "restart_pods",
            "description": "Restart pods to recover from crash loop",
        }
    elif "pending" in root_cause or "schedul" in root_cause:
        return {
            "type": "patch_resources",
            "description": "Adjust resource requests to fit available nodes",
        }
    else:
        # Generic: try to extract from remediation steps
        if steps:
            return {
                "type": "manual",
                "description": f"Manual remediation needed: {steps[0]}",
            }
    return None


def execute_action(action: dict, namespace: str, pod_name: str, dry_run: bool) -> dict:
    """Execute a remediation action."""
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action["type"],
        "description": action["description"],
        "dry_run": dry_run,
    }

    # Find the deployment name from the pod
    pod_info = run_kubectl(["get", "pod", pod_name, "-n", namespace, "-o", "json"])
    if pod_info:
        try:
            pod_data = json.loads(pod_info)
            owner_refs = pod_data.get("metadata", {}).get("ownerReferences", [])
            rs_name = next((ref["name"] for ref in owner_refs if ref["kind"] == "ReplicaSet"), None)
            if rs_name:
                # Get deployment from ReplicaSet
                rs_info = run_kubectl(["get", "rs", rs_name, "-n", namespace, "-o", "json"])
                rs_data = json.loads(rs_info)
                rs_owners = rs_data.get("metadata", {}).get("ownerReferences", [])
                deploy_name = next((ref["name"] for ref in rs_owners if ref["kind"] == "Deployment"), None)
            else:
                deploy_name = None
        except (json.JSONDecodeError, StopIteration):
            deploy_name = None
    else:
        deploy_name = None

    if action["type"] == "patch_memory" and deploy_name:
        new_value = action.get("new_value", "256Mi")
        cmd = [
            "patch", "deployment", deploy_name, "-n", namespace,
            "--type=json",
            f'-p=[{{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"{new_value}"}},{{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"128Mi"}}]',
        ]

        if dry_run:
            result["plan"] = f"Would patch deployment/{deploy_name}: memory limit → {new_value}"
            print(f"[DRY RUN] {result['plan']}")
        else:
            rollback_file = save_rollback_state(namespace, "deployment", deploy_name)
            result["rollback_file"] = rollback_file
            output = run_kubectl(cmd)
            result["kubectl_output"] = output
            print(f"[REMEDIATE] Patched deployment/{deploy_name} memory → {new_value}")

    elif action["type"] == "restart_pods":
        if dry_run:
            result["plan"] = f"Would restart pod {pod_name} in {namespace}"
            print(f"[DRY RUN] {result['plan']}")
        else:
            if deploy_name:
                rollback_file = save_rollback_state(namespace, "deployment", deploy_name)
                result["rollback_file"] = rollback_file
            output = run_kubectl(["delete", "pod", pod_name, "-n", namespace])
            result["kubectl_output"] = output
            print(f"[REMEDIATE] Deleted pod {pod_name} (will be recreated by ReplicaSet)")

    elif action["type"] == "patch_resources" and deploy_name:
        cmd = [
            "patch", "deployment", deploy_name, "-n", namespace,
            "--type=json",
            '-p=[{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"128Mi"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"}]',
        ]

        if dry_run:
            result["plan"] = f"Would patch deployment/{deploy_name}: memory requests → 128Mi, limits → 256Mi"
            print(f"[DRY RUN] {result['plan']}")
        else:
            rollback_file = save_rollback_state(namespace, "deployment", deploy_name)
            result["rollback_file"] = rollback_file
            output = run_kubectl(cmd)
            result["kubectl_output"] = output
            print(f"[REMEDIATE] Patched deployment/{deploy_name} resources")

    else:
        result["plan"] = f"Manual action required: {action['description']}"
        print(f"[REMEDIATE] {result['plan']}")

    return result


def remediate(diagnosis_file: str, dry_run: bool, execute: bool):
    """Main remediation workflow."""
    with open(diagnosis_file) as f:
        diagnosis = json.load(f)

    print(f"[REMEDIATE] Root cause: {diagnosis.get('root_cause', 'Unknown')}")
    print(f"[REMEDIATE] Confidence: {diagnosis.get('confidence', 'Unknown')}")
    print(f"[REMEDIATE] Risk level: {diagnosis.get('risk_level', 'Unknown')}")

    # Determine action
    action = determine_action(diagnosis)
    if not action:
        print("[REMEDIATE] Could not determine automated remediation. Manual intervention needed.")
        print(f"[REMEDIATE] Suggested steps: {json.dumps(diagnosis.get('remediation_steps', []), indent=2)}")
        return

    # Get namespace and pod from the alert context embedded in diagnosis
    # (In a real pipeline, this would be passed through the chain)
    namespace = "lab3"
    pod_name = ""

    # Try to find a failing pod
    pods_output = run_kubectl(["get", "pods", "-n", namespace, "-o", "json"])
    if pods_output:
        pods_data = json.loads(pods_output)
        for pod in pods_data.get("items", []):
            for cs in pod.get("status", {}).get("containerStatuses", []):
                if cs.get("restartCount", 0) > 0 or not cs.get("ready", True):
                    pod_name = pod["metadata"]["name"]
                    break

    if not pod_name:
        print("[REMEDIATE] No failing pods found. Nothing to remediate.")
        return

    action["namespace"] = namespace
    action["affected_pods"] = 1

    # Check guardrails
    status, reason = check_guardrails(action, diagnosis)
    print(f"[GUARDRAIL] Status: {status} — {reason}")

    if status == "blocked":
        print(f"[REMEDIATE] Action BLOCKED: {reason}")
        return

    if status == "needs_approval" or not execute:
        if not get_approval(f"{action['description']} on pod {pod_name} in {namespace}"):
            print("[REMEDIATE] Action cancelled by user.")
            return

    # Execute
    result = execute_action(action, namespace, pod_name, dry_run)

    # Verify (if not dry run)
    if not dry_run:
        print("[REMEDIATE] Waiting 10s for pods to stabilize...")
        import time
        time.sleep(10)

        verify_output = run_kubectl(["get", "pods", "-n", namespace, "-l", f"app=degrading-app"])
        print(f"\n[VERIFY] Current pod status:\n{verify_output}")
        result["verification"] = verify_output

    # Output report
    print(f"\n[REMEDIATE] === Remediation Report ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remediation Agent for AKS")
    parser.add_argument("--diagnosis-file", required=True, help="Path to diagnosis JSON")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Show plan without executing (default)")
    parser.add_argument("--execute", action="store_true", help="Actually execute the remediation")
    args = parser.parse_args()

    is_dry_run = not args.execute
    remediate(args.diagnosis_file, is_dry_run, args.execute)
