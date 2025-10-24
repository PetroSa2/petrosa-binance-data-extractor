# Issue #20 Resolution Summary

**Issue**: [Remove orphaned HPA for non-existent binance-data-extractor deployment](https://github.com/PetroSa2/petrosa_k8s/issues/20)
**Date Resolved**: October 24, 2025
**Status**: ✅ **COMPLETE**

---

## Quick Summary

Successfully removed orphaned HPA that was generating **57,952+ warning events** over 10 days. The HPA was incompatible with the service's CronJob-based architecture.

---

## What Was Done

### 1. Files Removed
- ✅ `/Users/yurisa2/petrosa/petrosa-binance-data-extractor/k8s/hpa.yaml` - Deleted manifest

### 2. Cluster Resources Deleted
- ✅ `petrosa-binance-data-extractor-hpa` HPA in `petrosa-apps` namespace

### 3. Documentation Updated
- ✅ Created `docs/HPA_REMOVAL.md` - Comprehensive documentation
- ✅ Updated `README.md` - Added scaling note
- ✅ Updated `petrosa_k8s/docs/REMAINING_ISSUES_CHECKLIST.md` - Marked issue as resolved

### 4. Verification Completed
- ✅ Confirmed no deployment exists for binance-data-extractor
- ✅ Confirmed HPA successfully deleted
- ✅ Confirmed no new FailedGetScale events

---

## Results

### Before
```
Warning: FailedGetScale (57,952+ events in 10 days)
Message: deployments/scale.apps "petrosa-binance-data-extractor" not found
Frequency: ~240 events/hour (every 15 seconds)
```

### After
```
✅ Zero FailedGetScale events
✅ Clean event logs
✅ Correct architecture documented
```

---

## Commands Used

```bash
# 1. Verified no deployment exists
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml \
  get deployments -n petrosa-apps | grep "binance-data-extractor"
# Result: No binance-data-extractor deployment found ✅

# 2. Confirmed HPA exists and generating errors
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml \
  get hpa -n petrosa-apps | grep "binance-data-extractor"
# Result: HPA exists with <unknown> metrics ✅

# 3. Checked FailedGetScale events
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml \
  get events -n petrosa-apps \
  --field-selector involvedObject.name=petrosa-binance-data-extractor-hpa
# Result: Continuous FailedGetScale warnings ✅

# 4. Deleted HPA manifest
rm /Users/yurisa2/petrosa/petrosa-binance-data-extractor/k8s/hpa.yaml

# 5. Deleted HPA from cluster
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml \
  delete hpa petrosa-binance-data-extractor-hpa -n petrosa-apps
# Result: horizontalpodautoscaler.autoscaling "petrosa-binance-data-extractor-hpa" deleted ✅

# 6. Verified HPA removal
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml \
  get hpa -n petrosa-apps | grep "binance-data-extractor"
# Result: ✅ HPA successfully removed

# 7. Confirmed no new events
kubectl --kubeconfig=/Users/yurisa2/petrosa/petrosa_k8s/k8s/kubeconfig.yaml \
  get events -n petrosa-apps \
  --field-selector involvedObject.name=petrosa-binance-data-extractor-hpa
# Result: Last event from before deletion, no new events ✅
```

---

## Why This Happened

The **Binance Data Extractor** uses **CronJobs** for scheduled batch processing:
- Jobs run on schedule (5m, 15m, 30m, 1h, 1d)
- Pods are ephemeral (created, complete, terminate)
- No continuous pods to scale

**HPA (HorizontalPodAutoscaler)** only works with:
- Deployments (continuous pods)
- StatefulSets
- ReplicaSets

**HPA does NOT work with CronJobs** because:
- No continuous pods to scale
- Scaling is done via schedule frequency
- Job parallelism is used for concurrent execution

---

## Correct Scaling Approach

### ❌ Wrong: HPA (removed)
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: petrosa-binance-data-extractor-hpa
spec:
  scaleTargetRef:
    kind: Deployment
    name: petrosa-binance-data-extractor  # Doesn't exist!
```

### ✅ Correct: Schedule Frequency
```yaml
# More frequent = more data ingestion
binance-klines-m5-production:
  schedule: "*/5 * * * *"    # Every 5 minutes

# Less frequent = less data ingestion
binance-klines-d1-production:
  schedule: "15 0 * * *"     # Daily at 00:15
```

### ✅ Correct: Job Parallelism (if needed)
```yaml
spec:
  parallelism: 3           # Run 3 pods simultaneously
  completions: 3           # All 3 must complete
  backoffLimit: 2          # Retry failed pods
```

---

## Acceptance Criteria

All criteria from issue #20 met:

- [x] Identified the orphaned HPA resource ✅
- [x] Verified no deployment exists with that name ✅
- [x] Removed the orphaned HPA (manifest + cluster) ✅
- [x] Verified no new FailedGetScale events appear ✅
- [x] Documented why HPA was removed ✅
- [x] Updated documentation that references this HPA ✅

---

## Files Changed

```
Modified:
  petrosa-binance-data-extractor/README.md
  petrosa_k8s/docs/REMAINING_ISSUES_CHECKLIST.md

Deleted:
  petrosa-binance-data-extractor/k8s/hpa.yaml

Created:
  petrosa-binance-data-extractor/docs/HPA_REMOVAL.md
  petrosa-binance-data-extractor/docs/ISSUE_20_RESOLUTION_SUMMARY.md (this file)
```

---

## Lessons Learned

1. **Architecture Alignment**: Always ensure Kubernetes resources match workload type
2. **Manifest Cleanup**: Remove dependent resources when changing architectures
3. **Regular Audits**: Check for orphaned resources periodically
4. **Documentation**: Document scaling approaches for each service type

---

## Prevention

### Check for orphaned HPAs
```bash
kubectl get hpa -A -o json | \
  jq '.items[] | select(.status.currentReplicas == null) |
      {name: .metadata.name, namespace: .metadata.namespace}'
```

### Document in .cursorrules
```markdown
## CronJob Scaling Approach
- ❌ Do NOT use HPA (no continuous pods)
- ✅ Use schedule frequency for scaling
- ✅ Use job parallelism if needed
```

---

## Next Steps

1. **Monitor for 24 hours** - Ensure no new events appear
2. **Archive old docs** - Move HPA references to archive/
3. **Update runbooks** - Remove HPA troubleshooting steps
4. **Close GitHub issue** - Mark issue #20 as resolved

---

## References

- **Detailed Documentation**: [HPA_REMOVAL.md](HPA_REMOVAL.md)
- **GitHub Issue**: https://github.com/PetroSa2/petrosa_k8s/issues/20
- **Service README**: [../README.md](../README.md)
- **CronJob Patterns**: [../.cursorrules](../.cursorrules)

---

**Status**: ✅ **ISSUE #20 COMPLETELY RESOLVED**
