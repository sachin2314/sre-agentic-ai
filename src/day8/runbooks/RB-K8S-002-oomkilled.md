# Runbook: RB-K8S-002 — OOMKilled (Out of Memory)

**Severity:** P1–P2 (depends on service criticality)  
**Last Updated:** 2024-01-15  
**Owner:** Platform SRE Team  
**Related Anomaly:** `AnomalyType.OOMKILLED`, `AnomalyType.MEMORY_LEAK`

---

## What Is It?
The Linux kernel OOM Killer terminates a container because it exceeded its
memory `limit` set in the pod spec. Exit code is always **137**.

## Decision Tree

```
Container OOMKilled?
│
├─ Is memory GROWING steadily? (memory_trend=GROWING)
│  └─ YES → Memory LEAK → Fix the application (see "Memory Leak" below)
│
├─ Is memory STABLE but near limit?
│  └─ YES → Limit too LOW → Increase resources.limits.memory
│
└─ Did it spike suddenly?
   └─ YES → Traffic spike / large payload → Add HPA or increase limit
```

## Immediate Fix (stop the bleeding)

```bash
# Option 1: Increase memory limit (fastest)
kubectl patch deployment <name> -n <namespace> \
  --patch '{"spec":{"template":{"spec":{"containers":[{"name":"<container>","resources":{"limits":{"memory":"1Gi"},"requests":{"memory":"512Mi"}}}]}}}}'

# Option 2: Force reschedule to a node with more available memory
kubectl delete pod <pod-name> -n <namespace>

# Option 3: Scale down to reduce node memory pressure
kubectl scale deployment <name> -n <namespace> --replicas=1
```

## Root Cause Investigation

```bash
# Get memory metrics over time (requires metrics-server)
kubectl top pod <pod-name> -n <namespace>

# Check VPA recommendation (if VPA is installed)
kubectl describe vpa <vpa-name> -n <namespace>

# Get heap dump (Java services)
kubectl exec <pod-name> -n <namespace> -- jmap -dump:format=b,file=/tmp/heap.hprof <pid>
```

## Memory Leak Fix Checklist
- [ ] Review connection pool settings (ensure connections are released)
- [ ] Check for thread local storage leaks
- [ ] Enable GC logging: `-XX:+PrintGCDetails -XX:+PrintGCDateStamps`
- [ ] Use memory profiler (VisualVM, YourKit, async-profiler)
- [ ] Set max heap: `-Xmx400m` (below K8s limit of 512Mi — leave headroom)

## Permanent Fix
```yaml
# In your deployment spec — ALWAYS set both request and limit
resources:
  requests:
    memory: "512Mi"   # Guaranteed allocation
    cpu: "250m"
  limits:
    memory: "1Gi"     # Maximum (was 512Mi — caused OOMKilled)
    cpu: "1000m"
```

## Prevention
- [ ] Set up CloudWatch Container Insights memory alerts at 80% of limit
- [ ] Configure VPA (Vertical Pod Autoscaler) for automatic right-sizing
- [ ] Add memory profiling to CI pipeline
- [ ] Load test before production releases

## SLO Impact
Typical OOMKilled impact: 30-90 seconds of 503s per pod before restart completes.
With 3 replicas and proper PDB: < 5% user-visible errors.
