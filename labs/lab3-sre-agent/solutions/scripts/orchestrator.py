"""
Orchestrator — Connects Detection → Diagnosis → Remediation agents
into an end-to-end SRE pipeline.

Usage:
    python orchestrator.py [--namespace lab3] [--watch]

Requires:
    pip install kubernetes openai
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

# Import the agent modules (from same directory)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from detection_agent import get_pods, check_pod_status
from diagnosis_agent import gather_context, build_prompt, call_llm, SYSTEM_PROMPT


def log(stage: str, message: str):
    """Print a timestamped log message."""
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{now}] {stage:12s}| {message}")


def run_kubectl(args: list[str], timeout: int = 60) -> str:
    result = subprocess.run(
        ["kubectl"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout or result.stderr


def detect(namespace: str) -> dict | None:
    """Run detection and return the most severe alert, or None."""
    pods = get_pods(namespace)
    all_alerts = []

    for pod in pods:
        alerts = check_pod_status(pod)
        all_alerts.extend(alerts)

    if not all_alerts:
        return None

    # Return the most severe
    return sorted(
        all_alerts,
        key=lambda a: {"critical": 0, "warning": 1, "info": 2}[a["severity"]],
    )[0]


def diagnose(alert: dict) -> dict:
    """Run diagnosis on an alert."""
    context = gather_context(alert)
    user_prompt = build_prompt(context)
    llm_response = call_llm(SYSTEM_PROMPT, user_prompt)

    try:
        return json.loads(llm_response)
    except json.JSONDecodeError:
        return {"raw_response": llm_response, "confidence": "low", "risk_level": "high"}


def remediate_simple(diagnosis: dict, namespace: str, pod_name: str, dry_run: bool = True, alert_type: str = "") -> dict:
    """Simple remediation based on diagnosis."""
    root_cause = diagnosis.get("root_cause", "").lower()
    remediation_steps = " ".join(diagnosis.get("remediation_steps", [])).lower()
    result = {"action": "none", "dry_run": dry_run}

    # Check readiness/probe issues FIRST — the root cause often mentions "memory"
    # from the previous OOM context, which would incorrectly match the memory branch
    is_readiness_issue = (
        alert_type == "pod_not_ready"
        or "readiness" in root_cause
        or "ready" in root_cause
        or ("probe" in root_cause and "oom" not in root_cause)
    )

    if is_readiness_issue:
        result["action"] = "restart_pod"
        result["description"] = f"Restart pod {pod_name} (readiness probe failure)"
        if not dry_run:
            run_kubectl(["delete", "pod", pod_name, "-n", namespace, "--grace-period=5"])
            result["status"] = "applied"
        else:
            result["plan"] = f"Would delete pod {pod_name} to reset readiness state"

    elif "oom" in root_cause or "memory" in remediation_steps:
        result["action"] = "patch_memory"
        result["description"] = "Increase memory limit to 256Mi"

        # Find deployment by traversing pod → replicaset → deployment
        deploy_name = None
        pod_json = run_kubectl(["get", "pod", pod_name, "-n", namespace, "-o", "json"])
        try:
            pod_info = json.loads(pod_json)
            owner_refs = pod_info.get("metadata", {}).get("ownerReferences", [])
            rs_name = next((ref["name"] for ref in owner_refs if ref["kind"] == "ReplicaSet"), None)
        except (json.JSONDecodeError, KeyError):
            # Pod may have been replaced — find deployment from app label instead
            rs_name = None
            app_label = pod_name.rsplit("-", 2)[0] if "-" in pod_name else pod_name
            deploy_json = run_kubectl(["get", "deployment", app_label, "-n", namespace, "-o", "name"])
            if deploy_json.strip().startswith("deployment.apps/"):
                deploy_name = deploy_json.strip().split("/", 1)[1]

        if rs_name and not deploy_name:
            rs_json = run_kubectl(["get", "rs", rs_name, "-n", namespace, "-o", "json"])
            try:
                rs_info = json.loads(rs_json)
                deploy_name = next(
                    (ref["name"] for ref in rs_info.get("metadata", {}).get("ownerReferences", [])
                     if ref["kind"] == "Deployment"),
                    None,
                )
            except (json.JSONDecodeError, KeyError):
                pass

        if deploy_name and not dry_run:
            run_kubectl([
                "patch", "deployment", deploy_name, "-n", namespace,
                "--type=json",
                '-p=[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"}]',
            ])
            result["status"] = "applied"
        elif deploy_name:
            result["plan"] = f"Would patch deployment/{deploy_name} memory → 256Mi"

    elif "crash" in root_cause or "command" in root_cause:
        result["action"] = "restart_pod"
        result["description"] = f"Restart pod {pod_name}"
        if not dry_run:
            run_kubectl(["delete", "pod", pod_name, "-n", namespace, "--grace-period=5"])
            result["status"] = "applied"
        else:
            result["plan"] = f"Would delete pod {pod_name} for restart"

    return result


def run_pipeline(namespace: str, watch: bool = False):
    """Run the full detect → diagnose → remediate pipeline."""
    log("PIPELINE", f"Starting SRE agent pipeline for namespace '{namespace}'")
    log("PIPELINE", "-" * 60)

    MAX_RETRIES_PER_ISSUE = 2
    issue_attempts: dict[str, int] = {}  # track repeated issues by alert type
    action_log: list[dict] = []  # track actions taken for summary

    iteration = 0
    while True:
        try:
            iteration += 1
            log("DETECT", f"Scanning namespace (iteration {iteration})...")

            # Step 1: Detect
            alert = detect(namespace)

            if not alert:
                log("DETECT", "No anomalies detected. All pods healthy.")
                if not watch:
                    break
                time.sleep(15)
                continue

            log("ALERT", f"[{alert['severity'].upper()}] {alert['what']}")

            # Dedup: track how many times we've seen this alert type
            issue_key = alert.get("type", "unknown")
            issue_attempts[issue_key] = issue_attempts.get(issue_key, 0) + 1
            if issue_attempts[issue_key] > MAX_RETRIES_PER_ISSUE:
                log("ESCALATE", f"Issue '{issue_key}' persists after {MAX_RETRIES_PER_ISSUE} remediation attempts.")
                log("ESCALATE", "Automated remediation cannot resolve this — escalating to human operator.")
                log("ESCALATE", f"Root cause requires application-level fix (not infrastructure). Exiting watch loop.")
                break

            # Step 2: Diagnose
            log("DIAGNOSE", "Gathering context...")
            diagnosis = diagnose(alert)
            log("DIAGNOSE", f"Root cause: {diagnosis.get('root_cause', 'Unknown')[:100]}")
            log("DIAGNOSE", f"Confidence: {diagnosis.get('confidence', '?')} | Risk: {diagnosis.get('risk_level', '?')}")

            # Step 3: Remediate (dry run first)
            pod_name = alert["where"].get("pod", "")
            alert_type = alert.get("type", "")
            log("REMEDIATE", "Generating remediation plan (dry run)...")
            plan = remediate_simple(diagnosis, namespace, pod_name, dry_run=True, alert_type=alert_type)
            log("REMEDIATE", f"Plan: {plan.get('description', plan.get('plan', 'No action'))}")

            # Step 4: Human approval
            if plan["action"] != "none":
                response = input(f"\n[APPROVAL] Execute: {plan.get('description', '?')}? [y/n]: ").strip().lower()
                if response == "y":
                    log("REMEDIATE", "Executing...")
                    result = remediate_simple(diagnosis, namespace, pod_name, dry_run=False, alert_type=alert_type)
                    log("REMEDIATE", f"Result: {result.get('status', 'unknown')}")

                    action_log.append({
                        "iteration": iteration,
                        "alert": alert["what"],
                        "action": plan.get("description", plan["action"]),
                        "result": result.get("status", "unknown"),
                    })

                    # Step 5: Verify
                    log("VERIFY", "Waiting 15s for stabilization...")
                    time.sleep(15)
                    pods_status = run_kubectl(["get", "pods", "-n", namespace])
                    log("VERIFY", f"Pod status:\n{pods_status}")

                    # Check if resolved
                    new_alert = detect(namespace)
                    if new_alert:
                        log("VERIFY", "Issue persists. Consider manual intervention or re-running.")
                    else:
                        log("RESOLVED", "Incident resolved successfully!")
                        issue_attempts.pop(issue_key, None)  # reset on success
                else:
                    log("REMEDIATE", "Cancelled by user.")

            if not watch:
                break

            log("PIPELINE", "Returning to monitoring...")
            time.sleep(15)

        except KeyboardInterrupt:
            print()
            try:
                response = input("[INTERRUPT] Do you want to exit? [y/n]: ").strip().lower()
            except KeyboardInterrupt:
                response = "y"
            if response == "y":
                break
            log("PIPELINE", "Resuming monitoring...")
            continue

    # Print summary
    print()
    log("SUMMARY", "=" * 60)
    log("SUMMARY", f"Pipeline ran {iteration} iteration(s) on namespace '{namespace}'")
    if action_log:
        log("SUMMARY", f"Actions taken ({len(action_log)}):")
        for entry in action_log:
            log("SUMMARY", f"  [{entry['iteration']}] {entry['action']} → {entry['result']}")
            log("SUMMARY", f"       Alert: {entry['alert']}")
    else:
        log("SUMMARY", "No remediation actions were executed.")
    log("SUMMARY", "=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SRE Agent Orchestrator")
    parser.add_argument("--namespace", default="lab3", help="Namespace to monitor")
    parser.add_argument("--watch", action="store_true", help="Continuously monitor (loop)")
    args = parser.parse_args()

    run_pipeline(args.namespace, args.watch)
