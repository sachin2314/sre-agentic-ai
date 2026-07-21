# Runbook: RB-K8S-003 — Node Memory Pressure

**Severity:** P1 (Affects ALL pods on the node)  
**Last Updated:** 2024-01-15  
**Owner:** Platform SRE Team  
**Related Anomaly:** `AnomalyType.NODE_MEMORY_PRESSURE`

---

## What Is It?
When a node's total memory usage exceeds the `MemoryPressure` threshold,
Kubernetes marks the node as `MemoryPressure=True`. The scheduler stops
placing new pods on this node. Existing pods may be evicted (starting with
BestEffort pods, then Burstable).

## Quick Assessment

```bash
# Check node conditions
kubectl describe node <node-name> | grep -A10 "Conditions:"

# See which pods are consuming the most memory on the node
kubectl top pods -A --sort-by=memory | grep <node-name>

# Check eviction events
kubectl get events -A | grep -i evict
```

## Triage Steps

1. **Identify the memory hog:**
   ```bash
   kubectl top pods -A --sort-by=memory | head -20
   ```

2. **Check if it's transient (spike) or persistent (leak):**
   - Spike: recent deployment? traffic surge? batch job?
   - Persistent: memory leak in one or more pods

3. **Cordon the node** (prevent new pods being scheduled):
   ```bash
   kubectl cordon <node-name>
   ```

4. **Drain the node** (if eviction required):
   ```bash
   kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
   ```

## Prevention
- [ ] Set resource LIMITS on ALL pods (prevents runaway memory)
- [ ] Configure Cluster Autoscaler to add nodes before pressure occurs
- [ ] Set namespace ResourceQuotas
- [ ] Enable node-level memory alerting at 75% utilisation
