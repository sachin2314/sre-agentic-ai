# Runbook: OOM Kill Recovery
**Runbook ID:** RB-OOM-001  
**Severity:** P1  
**Time to follow:** ~15 minutes  

---

## What is an OOM Kill?

OOM = Out Of Memory.

When a container uses more memory than its limit allows, the Linux kernel kills it.
The exit code is **137** (which means SIGKILL — a forced kill, not a clean shutdown).

You will see it in logs as:
- `exit code 137`
- `OOMKilling` in Kubernetes events
- `FATAL Process killed by OOM killer`

---

## How to Know You Have This Problem

Look for ALL of these together:
- [ ] Nginx returning 502 Bad Gateway
- [ ] Kubernetes event: `OOMKilling`
- [ ] Pod restart loop / `BackOff` events
- [ ] App log: `exit code 137` or `OutOfMemoryError`

---

## Step-by-Step Fix

### Step 1 — Confirm the OOM Kill (2 minutes)

```bash
# Check Kubernetes events for OOMKilling
kubectl get events -n production --sort-by='.lastTimestamp' | grep OOM

# Check pod exit code (137 = OOM killed)
kubectl describe pod <pod-name> -n production | grep "Exit Code"
```

What you should see:
```
Warning  OOMKilling   node-01  Memory cgroup out of memory: Kill process
Exit Code: 137
```

---

### Step 2 — Check If Pods Are Restarting (1 minute)

```bash
# See pod status
kubectl get pods -n production

# Look for these statuses:
# CrashLoopBackOff = pod is crashing and Kubernetes is retrying
# OOMKilled        = pod was killed by memory limit
```

---

### Step 3 — Free Up Database Connections (2 minutes)

If the app crashed and DB connections were not released, the restart will fail too.

```bash
# Connect to Postgres and kill idle connections
psql -h your-db-host -U admin -d your-database -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE state = 'idle'
  AND query_start < now() - interval '5 minutes';
"

# Check how many connections remain
psql -h your-db-host -U admin -c "SELECT count(*) FROM pg_stat_activity;"
```

Normal count is under 20. If it's 100+, you have a connection leak.

---

### Step 4 — Check and Fix Pod Quota (if needed) (2 minutes)

```bash
# Check current quota usage
kubectl describe resourcequota -n production

# If pods=10/10 (quota full), temporarily raise it
kubectl patch resourcequota resource-quota -n production \
  --patch '{"spec":{"hard":{"pods":"20"}}}'
```

---

### Step 5 — Restart the Deployment (3 minutes)

```bash
# Force a rolling restart (new pods get fresh memory)
kubectl rollout restart deployment/app -n production

# Watch the rollout - wait for "successfully rolled out"
kubectl rollout status deployment/app -n production --timeout=120s
```

---

### Step 6 — Verify Recovery (2 minutes)

```bash
# Check pods are Running (not CrashLoopBackOff)
kubectl get pods -n production

# Check nginx is getting 200s again (not 502s)
curl -s -o /dev/null -w "%{http_code}" https://your-service.com/api/health
# Should return: 200
```

---

## After the Incident — Permanent Fixes

These should go into Jira tickets and be fixed before the next deploy:

| Fix | Why | Priority |
|-----|-----|----------|
| Add memory limit = normal_usage + 30% headroom | Container limit too tight | P1 |
| Implement LRU cache with max size | Unbounded cache caused OOM | P1 |
| Add PgBouncer connection pooler | DB connections exhausted on restart | P2 |
| Raise pod quota to 2× current replicas | HPA blocked during recovery | P1 |
| Add memory alert at 80% usage | Catch it before OOM happens | P2 |

---

## Related Runbooks

- `RB-502-001`: Nginx 502 Recovery
- `RB-DB-001`: Database Connection Exhaustion
- `RB-K8S-001`: Kubernetes Quota Management

---

## Escalation

- If pods don't recover after 10 minutes → page `#oncall-sre`
- If DB connections won't clear → page `#oncall-dba`
- If quota raise requires approval → contact `platform-leads` on Slack
