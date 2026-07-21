# Runbook: RB-K8S-001 — CrashLoopBackOff

**Severity:** P2 (Production Impact)  
**Last Updated:** 2024-01-15  
**Owner:** Platform SRE Team  
**Related Anomaly:** `AnomalyType.CRASHLOOPBACKOFF`

---

## What Is It?
A pod enters `CrashLoopBackOff` when its container keeps crashing on startup.
Kubernetes backs off exponentially (10s → 20s → 40s → … max 5 min) before each restart.

## Immediate Triage (< 5 min)

```bash
# 1. Check pod status and restart count
kubectl get pod <pod-name> -n <namespace>

# 2. Get last termination reason
kubectl describe pod <pod-name> -n <namespace> | grep -A5 "Last State"

# 3. Read crash logs (previous container)
kubectl logs <pod-name> -n <namespace> --previous

# 4. Check recent events
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <pod-name>
```

## Common Root Causes

| Last State Exit Code | Likely Cause | Action |
|---------------------|--------------|--------|
| 137 | OOMKilled (memory limit) | → See RB-K8S-002 |
| 1 | Application error (check logs) | Fix application bug |
| 139 | Segmentation fault | Check for null pointer / C extension issues |
| 0 | Clean exit (job completed) | Correct — not a crash |

## Escalation
- 3+ restarts in 10 min → page on-call
- 5+ restarts → escalate to service owner
