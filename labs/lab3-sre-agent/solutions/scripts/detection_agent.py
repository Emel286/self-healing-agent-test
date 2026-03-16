"""
Detection Agent — Monitors AKS cluster for anomalies and produces structured alerts.

Usage:
    python detection_agent.py [--namespace lab3] [--interval 15] [--output alert.json]
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone


def run_kubectl(args: list[str]) -> str:
    """Run a kubectl command and return stdout."""
    result = subprocess.run(
        ["kubectl"] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout


def get_pods(namespace: str) -> list[dict]:
    """Get pod status information."""
    output = run_kubectl(["get", "pods", "-n", namespace, "-o", "json"])
    if not output:
        return []
    data = json.loads(output)
    return data.get("items", [])


def get_events(namespace: str) -> list[dict]:
    """Get recent events from the namespace."""
    output = run_kubectl([
        "get", "events", "-n", namespace,
        "--sort-by=.lastTimestamp",
        "-o", "json",
    ])
    if not output:
        return []
    data = json.loads(output)
    return data.get("items", [])


def check_pod_status(pod: dict) -> list[dict]:
    """Check a single pod for anomalies. Returns a list of alerts."""
    alerts = []
    metadata = pod.get("metadata", {})
    status = pod.get("status", {})
    pod_name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace", "unknown")
    node = status.get("nodeName", "unknown") if "nodeName" in (status or {}) else "unscheduled"
    phase = status.get("phase", "Unknown")

    # Check for Pending pods
    if phase == "Pending":
        alerts.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": "warning",
            "type": "pod_pending",
            "what": f"Pod {pod_name} is stuck in Pending state",
            "where": {"namespace": namespace, "pod": pod_name, "node": node},
            "context": {"phase": phase},
        })

    # Check container statuses
    for cs in status.get("containerStatuses", []):
        container_name = cs.get("name", "unknown")
        restart_count = cs.get("restartCount", 0)
        ready = cs.get("ready", False)
        waiting = cs.get("state", {}).get("waiting", {})
        last_terminated = cs.get("lastState", {}).get("terminated", {})

        # CrashLoopBackOff
        if waiting.get("reason") == "CrashLoopBackOff":
            alerts.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": "critical",
                "type": "pod_crash_loop",
                "what": f"Pod {pod_name} container {container_name} is in CrashLoopBackOff ({restart_count} restarts)",
                "where": {"namespace": namespace, "pod": pod_name, "node": node, "container": container_name},
                "context": {
                    "restart_count": restart_count,
                    "last_exit_code": last_terminated.get("exitCode"),
                    "last_reason": last_terminated.get("reason"),
                },
            })

        # ImagePullBackOff
        elif waiting.get("reason") in ("ImagePullBackOff", "ErrImagePull"):
            alerts.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": "critical",
                "type": "pod_image_pull",
                "what": f"Pod {pod_name} container {container_name} has ImagePullBackOff",
                "where": {"namespace": namespace, "pod": pod_name, "node": node, "container": container_name},
                "context": {"reason": waiting.get("reason"), "message": waiting.get("message", "")},
            })

        # High restart count
        elif restart_count >= 3 and ready:
            alerts.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": "warning",
                "type": "pod_high_restarts",
                "what": f"Pod {pod_name} container {container_name} has {restart_count} restarts",
                "where": {"namespace": namespace, "pod": pod_name, "node": node, "container": container_name},
                "context": {
                    "restart_count": restart_count,
                    "last_exit_code": last_terminated.get("exitCode"),
                    "last_reason": last_terminated.get("reason"),
                },
            })

        # Not ready
        if not ready and phase == "Running" and not waiting:
            alerts.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": "warning",
                "type": "pod_not_ready",
                "what": f"Pod {pod_name} container {container_name} is Running but not Ready",
                "where": {"namespace": namespace, "pod": pod_name, "node": node, "container": container_name},
                "context": {"ready": ready, "restart_count": restart_count},
            })

    return alerts


def monitor(namespace: str, interval: int, output_file: str | None):
    """Main monitoring loop."""
    print(f"[DETECT] Monitoring namespace '{namespace}' every {interval}s...")
    print(f"[DETECT] Press Ctrl+C to stop.\n")

    while True:
        try:
            pods = get_pods(namespace)
            all_alerts = []

            for pod in pods:
                alerts = check_pod_status(pod)
                all_alerts.extend(alerts)

            if all_alerts:
                for alert in all_alerts:
                    severity_icon = {"critical": "!!!", "warning": "! ", "info": "  "}.get(alert["severity"], "  ")
                    print(f"[{severity_icon}] [{alert['severity'].upper()}] {alert['what']}")

                if output_file:
                    # Write the most severe alert to the output file
                    most_severe = sorted(all_alerts, key=lambda a: {"critical": 0, "warning": 1, "info": 2}[a["severity"]])[0]
                    with open(output_file, "w") as f:
                        json.dump(most_severe, f, indent=2)
                    print(f"\n[DETECT] Alert written to {output_file}")
                    return  # Exit after first alert for pipeline mode
            else:
                now = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"[{now}] No anomalies detected. {len(pods)} pods healthy.")

            time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[DETECT] Stopped.")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detection Agent for AKS")
    parser.add_argument("--namespace", default="lab3", help="Namespace to monitor")
    parser.add_argument("--interval", type=int, default=15, help="Polling interval in seconds")
    parser.add_argument("--output", default=None, help="Output file for the alert JSON")
    args = parser.parse_args()

    monitor(args.namespace, args.interval, args.output)
