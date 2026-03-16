"""
Diagnosis Agent — Takes a structured alert and performs AI-powered root cause analysis.

Usage:
    python diagnosis_agent.py --alert-file alert.json [--output diagnosis.json]

Requires:
    pip install kubernetes openai azure-identity

Authentication (tried in order):
    1. Azure OpenAI + Entra ID  — AZURE_OPENAI_ENDPOINT set, uses DefaultAzureCredential (az login)
    2. Azure OpenAI + API key   — AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_KEY set
    3. OpenAI (direct)          — OPENAI_API_KEY set
"""

import argparse
import json
import os
import subprocess
import sys


SYSTEM_PROMPT = """You are an expert Kubernetes SRE performing root cause analysis for an AKS cluster incident.

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
Do not guess — if you're uncertain, say so and suggest additional data to collect."""


def run_kubectl(args: list[str]) -> str:
    """Run a kubectl command and return stdout."""
    result = subprocess.run(
        ["kubectl"] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout or result.stderr


def gather_context(alert: dict) -> dict:
    """Gather diagnostic context based on the alert type."""
    where = alert.get("where", {})
    namespace = where.get("namespace", "default")
    pod_name = where.get("pod", "")
    container = where.get("container", "")

    print(f"[DIAGNOSE] Gathering context for {pod_name} in {namespace}...")

    context = {"alert": alert}

    # Pod description
    print("[DIAGNOSE]   -> pod describe")
    context["pod_describe"] = run_kubectl(["describe", "pod", pod_name, "-n", namespace])

    # Current logs
    print("[DIAGNOSE]   -> container logs")
    log_args = ["logs", pod_name, "-n", namespace, "--tail=50"]
    if container:
        log_args.extend(["-c", container])
    context["logs_current"] = run_kubectl(log_args)

    # Previous logs (if container restarted)
    print("[DIAGNOSE]   -> previous logs")
    context["logs_previous"] = run_kubectl(log_args + ["--previous"])

    # Namespace events
    print("[DIAGNOSE]   -> namespace events")
    context["events"] = run_kubectl([
        "get", "events", "-n", namespace,
        "--sort-by=.lastTimestamp",
        "--field-selector", f"involvedObject.name={pod_name}",
    ])

    # Pod YAML spec
    print("[DIAGNOSE]   -> pod spec")
    context["pod_yaml"] = run_kubectl(["get", "pod", pod_name, "-n", namespace, "-o", "yaml"])

    return context


def build_prompt(context: dict) -> str:
    """Build a user prompt from the gathered context."""
    alert = context["alert"]
    prompt = f"""## Incident Alert
- **Type**: {alert.get('type')}
- **Severity**: {alert.get('severity')}
- **What**: {alert.get('what')}
- **Where**: namespace={alert['where'].get('namespace')}, pod={alert['where'].get('pod')}, node={alert['where'].get('node')}
- **Additional context**: {json.dumps(alert.get('context', {}), indent=2)}

## Pod Description
```
{context.get('pod_describe', 'N/A')[:3000]}
```

## Current Logs (last 50 lines)
```
{context.get('logs_current', 'N/A')[:2000]}
```

## Previous Container Logs
```
{context.get('logs_previous', 'N/A')[:2000]}
```

## Related Events
```
{context.get('events', 'N/A')[:2000]}
```

Please analyze this incident and provide your diagnosis as JSON."""
    return prompt


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call the LLM for diagnosis. Supports Azure OpenAI (Entra ID or key) and OpenAI."""

    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    azure_key = os.environ.get("AZURE_OPENAI_KEY")
    azure_deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

    # Option 1: Azure OpenAI with Entra ID (AzureCliCredential — uses az login session)
    if azure_endpoint and not azure_key:
        try:
            from azure.identity import AzureCliCredential, get_bearer_token_provider
            from openai import AzureOpenAI

            credential = AzureCliCredential()
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2024-10-21",
            )
            print(f"[DIAGNOSE] Using Azure OpenAI (Entra ID) — {azure_endpoint}")
            response = client.chat.completions.create(
                model=azure_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[DIAGNOSE] Entra ID auth failed: {e}")
            print("[DIAGNOSE] Ensure you have run 'az login' and have 'Cognitive Services OpenAI User' role.")

    # Option 2: Azure OpenAI with API key
    if azure_endpoint and azure_key:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_key,
            api_version="2024-10-21",
        )
        print(f"[DIAGNOSE] Using Azure OpenAI (API key) — {azure_endpoint}")
        response = client.chat.completions.create(
            model=azure_deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return response.choices[0].message.content

    # Option 3: OpenAI (direct)
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        print("[DIAGNOSE] Using OpenAI (direct API key)")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return response.choices[0].message.content

    # No LLM available — return a placeholder
    print("[DIAGNOSE] WARNING: No LLM configured.")
    print("[DIAGNOSE] Set AZURE_OPENAI_ENDPOINT (for Entra ID auth) or OPENAI_API_KEY.")
    return json.dumps({
        "root_cause": "LLM not configured. Set AZURE_OPENAI_ENDPOINT or OPENAI_API_KEY to enable AI diagnosis.",
        "evidence": ["No LLM analysis performed"],
        "remediation_steps": ["Configure Azure OpenAI endpoint or OpenAI API key", "Re-run the diagnosis agent"],
        "confidence": "low",
        "risk_level": "low",
    })


def diagnose(alert_file: str, output_file: str | None):
    """Main diagnosis workflow."""
    # Load alert
    with open(alert_file) as f:
        alert = json.load(f)

    print(f"[DIAGNOSE] Received alert: {alert.get('type')} — {alert.get('what')}")

    # Gather context
    context = gather_context(alert)

    # Build prompt
    user_prompt = build_prompt(context)

    # Call LLM
    print("[DIAGNOSE] Sending to LLM for analysis...")
    llm_response = call_llm(SYSTEM_PROMPT, user_prompt)

    try:
        diagnosis = json.loads(llm_response)
    except json.JSONDecodeError:
        diagnosis = {"raw_response": llm_response, "confidence": "low"}

    # Output
    print(f"\n[DIAGNOSE] === Diagnosis ===")
    print(f"  Root cause:  {diagnosis.get('root_cause', 'Unknown')}")
    print(f"  Confidence:  {diagnosis.get('confidence', 'Unknown')}")
    print(f"  Risk level:  {diagnosis.get('risk_level', 'Unknown')}")
    print(f"  Evidence:    {json.dumps(diagnosis.get('evidence', []), indent=4)}")
    print(f"  Remediation: {json.dumps(diagnosis.get('remediation_steps', []), indent=4)}")

    if output_file:
        with open(output_file, "w") as f:
            json.dump(diagnosis, f, indent=2)
        print(f"\n[DIAGNOSE] Diagnosis written to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnosis Agent for AKS")
    parser.add_argument("--alert-file", required=True, help="Path to alert JSON from detection agent")
    parser.add_argument("--output", default=None, help="Output file for the diagnosis JSON")
    args = parser.parse_args()

    diagnose(args.alert_file, args.output)
