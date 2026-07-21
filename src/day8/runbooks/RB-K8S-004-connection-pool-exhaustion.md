# Runbook: RB-K8S-004 — Database Connection Pool Exhaustion

**Severity:** P1 (causes 503s for all users)  
**Last Updated:** 2024-01-15  
**Owner:** Platform SRE Team  
**Related Anomaly:** `AnomalyType.CONNECTION_EXHAUSTION`

---

## What Is It?
The application's database connection pool is full. New requests cannot
get a DB connection and fail with 503. This often ALSO causes memory
pressure because unreleased connections accumulate.

## Symptoms
- Logs: `Connection pool exhausted - active=20/20 waiting=15`
- Requests failing with 503 or long timeouts (>30s)
- Memory growing (connections not released = memory leak)
- Error: `com.amazonaws.AmazonClientException: Connection pool exhausted`

## Immediate Fix

```bash
# 1. Rolling restart to flush leaked connections
kubectl rollout restart deployment/<name> -n <namespace>

# 2. Scale up temporarily (more pods = more pool capacity)
kubectl scale deployment <name> -n <namespace> --replicas=5

# 3. Check RDS connection count
aws rds describe-db-instances --query 'DBInstances[*].[DBInstanceIdentifier,DBInstanceStatus]'
```

## Root Cause Investigation

The pattern of connections never decreasing (connections_opened grows,
connections_closed stays at 0) points to a **connection leak** in the code.

Common causes:
1. Not using `try-with-resources` / `using` blocks
2. Exception path that skips `connection.close()`
3. Long-running transactions holding connections
4. Batch processing without connection return

## Code Fix Pattern (Java example)
```java
// WRONG — connection never released if exception thrown
Connection conn = pool.borrowConnection();
doQuery(conn);
pool.returnConnection(conn);  // Never reached on exception!

// CORRECT — connection always returned
try (Connection conn = pool.borrowConnection()) {
    doQuery(conn);
}  // Auto-released even on exception
```

## Connection Pool Tuning
```yaml
# Application config
db:
  pool:
    max-size: 20          # Match RDS max_connections / pod_count
    min-idle: 5
    connection-timeout: 3000   # Fail fast (3s) rather than wait 30s
    idle-timeout: 600000       # Release idle connections after 10min
    max-lifetime: 1800000      # Recycle connections every 30min
    leak-detection-threshold: 5000  # Warn if connection held >5s
```
