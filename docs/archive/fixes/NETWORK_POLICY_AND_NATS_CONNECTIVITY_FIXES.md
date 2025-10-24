# Network Policy and NATS Connectivity Fixes

## Issue Summary

The **petrosa-binance-data-extractor** was experiencing two critical connectivity issues that prevented proper operation:

1. **MySQL Connection Failures** - Pod in CrashLoopBackOff due to network policy label mismatch
2. **NATS Connection Failures** - Client trying to connect to localhost instead of NATS service

## Detailed Problem Analysis

### 1. MySQL Connectivity Issue

**Symptoms**:
- Pod status: `CrashLoopBackOff` with 80+ restarts
- Error: `[Errno -3] Try again` when connecting to MySQL
- Network policy appeared to allow port 3306 but wasn't being applied

**Root Cause**: **Label Mismatch Between Pod and Network Policy**
```yaml
# Pod Labels (from deployment)
labels:
  app: binance-data-extractor
  component: data-extraction

# Network Policy Selector (incorrect)
podSelector:
  matchLabels:
    app: binance-extractor  # ❌ Missing "-data"
```

**Impact**: The network policy was not applied to the pod, effectively blocking all outbound connections including MySQL.

### 2. NATS Connectivity Issue

**Symptoms**:
- NATS client trying to connect to `::1` and `127.0.0.1` (localhost)
- Error: `Connect call failed ('::1', 4222, 0, 0), [Errno 111] Connect call failed ('127.0.0.1', 4222)`
- No NATS environment variables in deployment

**Root Causes**:
1. **Missing NATS Environment Variables** in deployment
2. **Incorrect NATS URL** pointing to external IP instead of internal DNS

## Detailed Solutions Implemented

### Solution 1: Fixed Network Policy Labels

**File Created**: `k8s/network-policy-fix.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-binance-data-extractor
  namespace: petrosa-apps
  labels:
    app: binance-data-extractor
    component: data-extraction
spec:
  podSelector:
    matchLabels:
      app: binance-data-extractor      # ✅ Fixed label
      component: data-extraction       # ✅ Added component
  egress:
  - ports:
    - port: 53
      protocol: UDP
    to:
    - ipBlock:
        cidr: 0.0.0.0/0
  - ports:
    - port: 443
      protocol: TCP
    to:
    - ipBlock:
        cidr: 0.0.0.0/0
  - ports:
    - port: 3306
      protocol: TCP
    to:
    - ipBlock:
        cidr: 0.0.0.0/0
  - ports:
    - port: 27017
      protocol: TCP
    to:
    - ipBlock:
        cidr: 0.0.0.0/0
  - ports:
    - port: 5432
      protocol: TCP
    to:
    - ipBlock:
        cidr: 0.0.0.0/0
  - ports:
    - port: 4317
      protocol: TCP
    to:
    - ipBlock:
        cidr: 0.0.0.0/0
  - ports:
    - port: 4317
      protocol: UDP
    to:
    - ipBlock:
        cidr: 0.0.0.0/0
  - ports:
    - port: 4222
      protocol: TCP
    to:
    - ipBlock:
        cidr: 0.0.0.0/0
  policyTypes:
  - Egress
```

**Commands Executed**:
```bash
# Applied new network policy
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/network-policy-fix.yaml

# Deleted old network policy with wrong labels
kubectl --kubeconfig=k8s/kubeconfig.yaml delete networkpolicy allow-binance-extractor -n petrosa-apps
```

### Solution 2: Added NATS Environment Variables to Deployment

**File Modified**: `k8s/deployment.yaml`

**Added Environment Variables**:
```yaml
- name: NATS_ENABLED
  valueFrom:
    configMapKeyRef:
      name: petrosa-common-config
      key: NATS_ENABLED
- name: NATS_URL
  valueFrom:
    configMapKeyRef:
      name: petrosa-common-config
      key: NATS_URL
- name: NATS_SUBJECT_PREFIX
  valueFrom:
    configMapKeyRef:
      name: petrosa-common-config
      key: NATS_SUBJECT_PREFIX
- name: NATS_SUBJECT_PREFIX_PRODUCTION
  valueFrom:
    configMapKeyRef:
      name: petrosa-common-config
      key: NATS_SUBJECT_PREFIX_PRODUCTION
- name: NATS_SUBJECT_PREFIX_GAP_FILLER
  valueFrom:
    configMapKeyRef:
      name: petrosa-common-config
      key: NATS_SUBJECT_PREFIX_GAP_FILLER
```

**Commands Executed**:
```bash
# Applied updated deployment
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/deployment.yaml

# Restarted deployment to pick up new configuration
kubectl --kubeconfig=k8s/kubeconfig.yaml rollout restart deployment petrosa-binance-data-extractor -n petrosa-apps
```

### Solution 3: Fixed NATS URL in Common Configmap

**File Modified**: `petrosa-common-config` ConfigMap

**NATS URL Change**:
```yaml
# Before (incorrect)
NATS_URL: nats://192.168.194.253:4222

# After (correct)
NATS_URL: nats://nats-server.nats.svc.cluster.local:4222
```

**Commands Executed**:
```bash
# Updated configmap with correct NATS URL
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f /tmp/common-config-latest.yaml
```

### Solution 4: Repository Cleanup

**Files Removed**:
- `decode_kubeconfig.py` - Base64-encoded kubeconfig file (syntax error)
- `decode.py` - Utility decode script
- `debug_secret.yml` - Debug secret file

**Reason**: These files don't belong in a data extraction project and were causing syntax errors.

## Verification of Fixes

### MySQL Connectivity Verification

**Before Fix**:
```bash
# Pod status
NAME                                              READY   STATUS             RESTARTS   AGE
petrosa-binance-data-extractor-66f5b67c79-k8bp7   0/1     CrashLoopBackOff   80         10h

# Error logs
"Can't connect to MySQL server on 'petrosa_crypto.mysql.dbaas.com.br' ([Errno -3] Try again)"
```

**After Fix**:
```bash
# Pod status
NAME                                              READY   STATUS    RESTARTS   AGE
petrosa-binance-data-extractor-6c9d5ddbc4-xrhhl   1/1     Running   0          5m

# Success logs
"✅ LINKUSDT: fetched=2, written=0, duration=6.23s"
"✅ BCHUSDT: fetched=2, written=0, duration=6.01s"
```

### NATS Connectivity Verification

**Before Fix**:
```bash
# Error logs
"Connect call failed ('::1', 4222, 0, 0), [Errno 111] Connect call failed ('127.0.0.1', 4222)"
```

**After Fix**:
```bash
# Success logs
"Connected to NATS server at nats://nats-server.nats.svc.cluster.local:4222"
"Published extraction completion message for LINKUSDT to petrosa.production.klines.LINKUSDT.15m"
"Published extraction completion message for BCHUSDT to petrosa.production.klines.BCHUSDT.15m"
```

## Performance Results

### Data Extraction Performance
- **Symbols Processed**: 10
- **Symbols Failed**: 0
- **Total Records Fetched**: 20
- **Total Duration**: 13.39 seconds
- **Success Rate**: 100%

### NATS Message Publishing
- **Messages Published**: Multiple per extraction cycle
- **Subjects Used**:
  - `petrosa.production.klines.{SYMBOL}.15m`
  - `petrosa.klines.{SYMBOL}.15m`
- **Connection Status**: Stable with proper connect/disconnect cycles

## Files Created/Modified

### New Files Created
1. `k8s/network-policy-fix.yaml` - Fixed network policy with correct labels
2. `docs/MYSQL_CONNECTIVITY_ISSUE_RESOLUTION.md` - MySQL issue resolution details
3. `docs/COMPLETE_ISSUE_RESOLUTION_SUMMARY.md` - Complete summary of all fixes
4. `scripts/test_mysql_connectivity.py` - MySQL connectivity test script
5. `scripts/test_connectivity.sh` - Connectivity test shell script
6. `scripts/test_pod.yaml` - Test pod for debugging

### Files Modified
1. `k8s/deployment.yaml` - Added NATS environment variables
2. `petrosa-common-config` ConfigMap - Fixed NATS URL

### Files Removed
1. `decode_kubeconfig.py` - Removed (syntax error)
2. `decode.py` - Removed (unnecessary)
3. `debug_secret.yml` - Removed (unnecessary)

## Lessons Learned

### 1. Network Policy Debugging
- **Always check pod labels vs policy selectors**
- **Use `kubectl get networkpolicy -o yaml` to inspect all policies**
- **Verify that policies are actually applied to pods**

### 2. Environment Variable Management
- **Explicitly define all required environment variables in deployments**
- **Don't rely on defaults in application code**
- **Verify configmap and secret references**

### 3. Kubernetes DNS
- **Use internal DNS names for service-to-service communication**
- **Format: `service-name.namespace.svc.cluster.local`**
- **Avoid external IPs for internal cluster communication**

### 4. CI/CD Compliance
- **Never modify `VERSION_PLACEHOLDER` - it's part of the CI/CD system**
- **Respect deployment automation and placeholders**

## Current Status

### ✅ All Issues Resolved
- **Pod Status**: `1/1 Running`
- **MySQL Connection**: Working perfectly
- **NATS Connection**: Working perfectly
- **Data Extraction**: Successfully processing 10 symbols
- **Message Publishing**: NATS messages being published successfully

### ⚠️ Non-Critical Issues (Monitoring Only)
- **OpenTelemetry Collector**: Connection warnings (non-blocking)
- **MySQL Window Functions**: Performance warnings (non-blocking)

## Commands for Verification

```bash
# Check pod status
kubectl --kubeconfig=k8s/kubeconfig.yaml get pods -n petrosa-apps -l app=binance-data-extractor

# Check logs for success
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -n petrosa-apps -l app=binance-data-extractor --tail=50

# Check network policies
kubectl --kubeconfig=k8s/kubeconfig.yaml get networkpolicy -n petrosa-apps

# Check NATS service
kubectl --kubeconfig=k8s/kubeconfig.yaml get services -n nats
```

---

**Fix Date**: 2025-08-21
**Fix Duration**: ~45 minutes
**Status**: ✅ ALL CRITICAL ISSUES RESOLVED
**Impact**: Data extractor now fully operational with MySQL and NATS connectivity
