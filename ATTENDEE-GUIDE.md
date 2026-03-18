# DevAI Hackathon — Attendee Guide

## What Is This Hackathon About?

A hands-on workshop where you'll learn to operate, troubleshoot, and automate Azure Kubernetes Service (AKS) workloads using AI-powered tools. You'll progress from understanding Kubernetes resiliency basics, to AI-assisted diagnosis of broken workloads, to building a multi-agent SRE automation pipeline.

---

## Topics Covered

| Area | What You'll Learn |
|------|-------------------|
| **Kubernetes Resiliency** | Health probes (startup, liveness, readiness), self-healing, Pod Disruption Budgets, node auto-repair |
| **AI-Assisted Troubleshooting** | Context engineering, prompt structuring, using GitHub Copilot and Azure Copilot to diagnose broken workloads |
| **SRE Automation** | Building detection, diagnosis, and remediation agents; orchestrating them into a production-inspired pipeline with safety guardrails |
| **Observability** | Deploying Prometheus + Grafana, interpreting metrics, correlating events with failures |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Cloud Platform | Microsoft Azure |
| Container Orchestration | Azure Kubernetes Service (AKS) 1.34 |
| Infrastructure as Code | Bicep |
| AI / LLM | Azure OpenAI (GPT-4o-mini) |
| Authentication | Microsoft Entra ID (passwordless, no API keys) |
| Observability | Prometheus + Grafana (kube-prometheus-stack) |
| Agent Scripts | Python 3.10+ (kubernetes, openai, azure-identity) |
| Networking | Azure Virtual Network + Azure CNI |

---

## Lab Breakdown

### Lab 1 — AKS Resiliency & Failure Basics
Deploy healthy apps, simulate probe failures, observe self-healing in action, and protect workloads with Pod Disruption Budgets. _7 challenges._

### Lab 2 — AI-Assisted Diagnosis (DevAI Foundations)
Deploy intentionally broken workloads (CrashLoopBackOff, ImagePullBackOff, resource constraints) and use AI tools to diagnose and fix them. Practice context engineering and YAML generation. _7 challenges._

### Lab 3 — End-to-End SRE Agent Flow
Build a multi-agent pipeline in Python: a **Detection Agent** that monitors pods, a **Diagnosis Agent** that calls Azure OpenAI for root-cause analysis, and a **Remediation Agent** that applies fixes with approval gates, blast-radius checks, and rollback capability. Tie it all together with an **Orchestrator**. _7 challenges._

---

## Learning Outcomes

By the end of this hackathon, you will be able to:

- Configure Kubernetes health probes and explain when to use each type
- Diagnose common Kubernetes failure patterns (CrashLoopBackOff, ImagePullBackOff, Pending)
- Use AI tools effectively by applying context engineering principles
- Build Python-based agents that interact with the Kubernetes API
- Integrate Azure OpenAI (with Entra ID authentication) into operational workflows
- Design safe automation with dry-run modes, approval gates, and escalation policies
- Deploy and query a Prometheus + Grafana observability stack

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Azure Subscription** | With Contributor role access |
| **Azure CLI** | v2.60 or later |
| **kubectl** | Kubernetes CLI |
| **kubelogin** | For Azure RBAC-based cluster access |
| **Helm** | v3.0 or later |
| **Python** | 3.10 or later |
| **GitHub Copilot** | Recommended for Lab 2 |

---

## What to Expect

- **Format**: Hands-on, challenge-based — each lab has step-by-step instructions with solutions available if needed
- **Pace**: Progressive difficulty — Lab 1 builds foundations, Lab 2 introduces AI tooling, Lab 3 ties everything together
- **Environment**: Simplified for learning (public endpoints, no private cluster) — production hardening guidance is provided
- **Collaboration**: Solutions are included, but try each challenge on your own first

---

*Happy hacking!*
