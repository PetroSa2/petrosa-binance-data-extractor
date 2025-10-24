# HPA Removal for Binance Data Extractor

**Date**: October 24, 2025
**Issue**: [#20 - Remove orphaned HPA for non-existent binance-data-extractor deployment](https://github.com/PetroSa2/petrosa_k8s/issues/20)
**Status**: ✅ **RESOLVED**

---

## Problem Statement

An orphaned HorizontalPodAutoscaler (HPA) resource `petrosa-binance-data-extractor-hpa` was generating **57,952+ warning events** over 10 days by attempting to manage a non-existent deployment.

### Impact

```
Warning: FailedGetScale
Message: deployments/scale.apps "petrosa-binance-data-extractor" not found
Count: 57,952+ events (from Oct 14 to Oct 24)
Frequency: ~240 events/hour (every 15 seconds)
```

**Issues Caused**:
- Cluster event log pollution (made debugging harder)
- Unnecessary controller reconciliation overhead
- Confusion about intended cluster state
- Wasted API server resources

---

## Root Cause

The **Binance Data Extractor** architecture uses **CronJobs**, not **Deployments**:

- **CronJobs**: Schedule-based batch jobs (1m, 5m, 15m, 1h, 4h, 1d)
- **No Continuous Pods**: Jobs run on schedule, complete, and terminate
- **HPA Incompatibility**: HPA only works with Deployments/StatefulSets/ReplicaSets

The HPA manifest was likely:
1. Created during initial development when considering a deployment-based architecture
2. Left over from an architectural change to CronJobs
3. Never cleaned up when the deployment was removed

---

## Solution Implemented

### 1. Verified the Problem

```bash
# Confirmed no deployment exists
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml get deployments -n petrosa-apps | grep "binance-data-extractor"
# Result: No binance-data-extractor deployment found ✅

# Confirmed HPA exists and generating errors
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml get hpa -n petrosa-apps | grep "binance-data-extractor"
# Result: HPA exists with <unknown> metrics and 0 replicas ✅

# Confirmed FailedGetScale events
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml get events -n petrosa-apps --field-selector involvedObject.name=petrosa-binance-data-extractor-hpa
# Result: Continuous FailedGetScale warnings ✅
```

### 2. Removed HPA Manifest

**File Deleted**: `/Users/yurisa2/petrosa/petrosa-binance-data-extractor/k8s/hpa.yaml`

**Previous Content** (for reference):
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: petrosa-binance-data-extractor-hpa
  namespace: petrosa-apps
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: petrosa-binance-data-extractor  # ❌ This deployment doesn't exist
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 3. Deleted HPA from Cluster

```bash
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml delete hpa petrosa-binance-data-extractor-hpa -n petrosa-apps
# Result: horizontalpodautoscaler.autoscaling "petrosa-binance-data-extractor-hpa" deleted ✅
```

### 4. Verified Resolution

```bash
# Confirmed HPA removed
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml get hpa -n petrosa-apps | grep "binance-data-extractor"
# Result: ✅ HPA successfully removed

# Confirmed no new events
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml get events -n petrosa-apps --field-selector involvedObject.name=petrosa-binance-data-extractor-hpa
# Result: Last event from before deletion, no new events ✅
```

---

## Why CronJobs Don't Need HPA

### CronJob Scaling Approach

**CronJobs scale differently** than Deployments:

| Aspect | Deployment + HPA | CronJob |
|--------|------------------|---------|
| **Pods** | Continuous, long-running | Ephemeral, schedule-based |
| **Scaling** | Horizontal (add/remove pods) | Vertical (adjust schedule frequency) |
| **Resources** | Adjusted dynamically | Set per job execution |
| **Use Case** | Continuous services | Batch processing |

### Correct Scaling for Data Extractor

**Schedule Frequency** (already implemented):
```yaml
# High-frequency jobs (more data ingestion)
binance-klines-m5-production:  "*/5 * * * *"    # Every 5 minutes
binance-klines-m15-production: "*/15 * * * *"   # Every 15 minutes
binance-klines-m30-production: "*/30 * * * *"   # Every 30 minutes

# Low-frequency jobs (less data ingestion)
binance-klines-h1-production:  "2 * * * *"      # Every hour
binance-klines-d1-production:  "15 0 * * *"     # Daily at 00:15
```

**Job Parallelism** (if needed):
```yaml
spec:
  parallelism: 3           # Run 3 pods simultaneously
  completions: 3           # All 3 must complete
  backoffLimit: 2          # Retry failed pods 2 times
```

**Resource Limits** (already configured):
```yaml
resources:
  requests:
    cpu: "200m"
    memory: "256Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

---

## Results

### Before Fix
- ❌ 57,952+ warning events over 10 days
- ❌ ~240 events/hour (every 15 seconds)
- ❌ Cluttered event logs
- ❌ Wasted controller cycles
- ❌ Confusion about cluster state

### After Fix
- ✅ Zero FailedGetScale events
- ✅ Clean event logs
- ✅ No unnecessary reconciliation
- ✅ Clear cluster state
- ✅ Correct architecture documented

---

## Lessons Learned

### 1. Architecture Alignment
**Always ensure Kubernetes resources match the workload type**:
- Use HPA for: Deployments, StatefulSets, ReplicaSets (continuous workloads)
- Don't use HPA for: CronJobs, Jobs, DaemonSets

### 2. Manifest Cleanup
**When changing architectures, clean up old resources**:
```bash
# Before removing a deployment, check for dependent resources
kubectl get hpa -n petrosa-apps
kubectl get pdb -n petrosa-apps  # PodDisruptionBudgets
kubectl get svc -n petrosa-apps  # Services
kubectl get ingress -n petrosa-apps
```

### 3. Regular Audits
**Implement periodic resource audits**:
```bash
# Find HPAs with no targets
kubectl get hpa -A -o json | jq '.items[] | select(.status.currentReplicas == null) | {name: .metadata.name, namespace: .metadata.namespace}'

# Find services with no endpoints
kubectl get svc -A -o json | jq '.items[] | select(.spec.selector != null) | {name: .metadata.name, namespace: .metadata.namespace, selector: .spec.selector}'
```

### 4. Documentation
**Document architectural decisions**:
- Why CronJobs instead of Deployments
- How to scale CronJobs (schedule frequency, not HPA)
- Resource planning for batch jobs

---

## Prevention

### Pre-Commit Checklist

Before removing any Kubernetes resource, check for:

```bash
# 1. Find all resources referencing a name
kubectl get all,hpa,pdb,networkpolicy -n petrosa-apps -o yaml | grep "petrosa-binance-data-extractor"

# 2. Check HPA targets
kubectl get hpa -n petrosa-apps -o json | jq '.items[] | {name: .metadata.name, target: .spec.scaleTargetRef}'

# 3. Verify manifest cleanup
grep -r "hpa.yaml" /Users/yurisa2/petrosa/petrosa-binance-data-extractor/k8s/
```

### Architecture Documentation

**Document in `.cursorrules` or `README.md`**:
```markdown
## Binance Data Extractor Architecture

**Workload Type**: CronJobs (batch processing)
**Scaling**: Schedule frequency, not HPA
**Resources**: Per-job limits (200m-500m CPU, 256Mi-512Mi memory)

❌ Do NOT use HPA (no continuous pods)
✅ Use schedule frequency for scaling
✅ Use job parallelism if needed
```

---

## Verification Commands

### Check HPA Status
```bash
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml get hpa -n petrosa-apps
# Should NOT show petrosa-binance-data-extractor-hpa
```

### Check Events
```bash
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml get events -n petrosa-apps --sort-by='.lastTimestamp' | grep "FailedGetScale"
# Should NOT show any recent FailedGetScale for binance-data-extractor-hpa
```

### Verify CronJobs Running
```bash
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml get cronjobs -n petrosa-apps | grep "binance"
# Should show all binance CronJobs as expected
```

### Monitor for 24 Hours
```bash
# Check events after 24 hours to ensure no new HPA appears
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml get events -n petrosa-apps --field-selector involvedObject.name=petrosa-binance-data-extractor-hpa
# Should show: "No resources found in petrosa-apps namespace."
```

---

## Related Documentation

- [Service README](../README.md) - Service overview and architecture
- [CronJob Patterns](.cursorrules) - CronJob best practices
- [Binance API Integration](.cursorrules) - Rate limiting and scheduling
- [Gap Filling Strategy](.cursorrules) - Data completeness approach

---

## Success Criteria

- [x] Identified the orphaned HPA resource
- [x] Verified no deployment exists with that name
- [x] Removed the orphaned HPA (manifest + cluster)
- [x] Verified no new FailedGetScale events appear
- [x] Documented why HPA was removed
- [x] Updated documentation with correct scaling approach

**Status**: ✅ **ALL CRITERIA MET**

---

## Contact

**Issue**: https://github.com/PetroSa2/petrosa_k8s/issues/20
**Date Resolved**: October 24, 2025
**Resolved By**: AI Assistant (Claude)
