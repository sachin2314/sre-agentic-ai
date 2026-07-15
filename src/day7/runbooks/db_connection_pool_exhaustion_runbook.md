# Runbook: Database Connection Pool Exhaustion

**Severity:** P1 (Critical)
**Typical Duration:** 5–20 minutes if actioned quickly
**Services Affected:** All application services that use the primary database
**Related Anomaly Types:** threshold, keyword, statistical

---

## 1. Symptoms

- Application logs: `Connection pool exhausted. active=10 waiting=N`
- Database logs: `Connection limit reached. active=200 max=200`
- Nginx logs: HTTP 500 errors with 5s response times, followed by 502 errors
- Kubernetes: Liveness probe failures on application pods
- End users: 500/502 errors on all API endpoints

---

## 2. Immediate Diagnosis (do this first)

**Step 1 — Confirm the issue is the connection pool:**
```bash
# Check active DB connections
psql -h <DB_HOST> -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# See what queries are running / waiting
psql -h <DB_HOST> -U postgres -c "
  SELECT pid, state, wait_event_type, wait_event, query_start, query
  FROM pg_stat_activity
  WHERE state != 'idle'
  ORDER BY query_start;"
```

**Step 2 — Check for slow queries or locks:**
```bash
psql -h <DB_HOST> -U postgres -c "
  SELECT pid, now() - pg_stat_activity.query_start AS duration, query
  FROM pg_stat_activity
  WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '5 seconds'
  ORDER BY duration DESC;"
```

**Step 3 — Check if autovacuum is running:**
```bash
psql -h <DB_HOST> -U postgres -c "
  SELECT relname, last_autovacuum, last_autoanalyze
  FROM pg_stat_user_tables
  ORDER BY last_autovacuum DESC NULLS LAST
  LIMIT 10;"
```

---

## 3. Immediate Resolution Steps

### Option A — Kill long-running queries (fastest, ~2 min)
```bash
# Terminate queries running longer than 30 seconds
psql -h <DB_HOST> -U postgres -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE now() - query_start > interval '30 seconds'
    AND state = 'active'
    AND pid != pg_backend_pid();"
```
> ⚠️ WARNING: This kills in-flight transactions. Only do this if the service is already down.

### Option B — Cancel autovacuum (if it's causing the lock)
```bash
# Find the autovacuum PID
psql -h <DB_HOST> -U postgres -c "
  SELECT pid, query FROM pg_stat_activity WHERE query LIKE 'autovacuum%';"

# Cancel it (gentler than TERMINATE)
psql -h <DB_HOST> -U postgres -c "SELECT pg_cancel_backend(<PID>);"
```

### Option C — Temporarily increase max_connections (requires restart)
```bash
# Edit postgresql.conf — only if absolutely necessary, requires restart
echo "max_connections = 300" >> /etc/postgresql/14/main/postgresql.conf
systemctl restart postgresql
```

---

## 4. Recovery Verification

After taking action, confirm recovery:

```bash
# Connection count should drop below 80% of max
psql -h <DB_HOST> -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Application health check
curl -f http://localhost:8080/health

# Check Kubernetes pod status
kubectl get pods -n <NAMESPACE>
```

Wait 2–3 minutes. If pods are still in CrashLoopBackOff, check:
```bash
kubectl describe pod <POD_NAME> -n <NAMESPACE>
kubectl logs <POD_NAME> -n <NAMESPACE> --previous
```

---

## 5. Root Cause Investigation (after service is restored)

1. Pull the log analysis report from `reports/` folder
2. Check the timeline: did a slow query → lock → pool exhaustion?
3. Check autovacuum schedule vs traffic peak times
4. Review if a recent deploy changed query patterns

---

## 6. Long-term Prevention

| Action | Priority | Owner |
|--------|----------|-------|
| Deploy PgBouncer connection pooling | HIGH | Platform team |
| Set autovacuum to run 02:00–04:00 UTC | MEDIUM | DBA |
| Add alert: DB connections > 80% of max | HIGH | SRE |
| Implement circuit breaker in application | MEDIUM | App team |
| Add query timeout: `statement_timeout = 10s` | HIGH | DBA |

---

## 7. Escalation

| Condition | Action |
|-----------|--------|
| DB process crashed (FATAL in logs) | Page DBA on-call immediately |
| Pod quota prevents new pods starting | Page Platform/Infra team |
| Service still down after 15 min | Escalate to P0, all hands |

---

*Runbook owner: SRE Team | Last updated: 2024-01-15 | Review: Quarterly*
