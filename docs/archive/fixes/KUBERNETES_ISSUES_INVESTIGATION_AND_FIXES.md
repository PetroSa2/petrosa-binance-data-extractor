# Petrosa Binance Data Extractor - Kubernetes Issues Investigation and Fixes

## Executive Summary

The petrosa-binance-data-extractor had **incorrect architecture** with both a Deployment and CronJobs running simultaneously. The correct architecture is **CronJobs only** for periodic data extraction. The deployment has been removed and the cronjobs are working correctly. **Network connectivity issues have been resolved**, but there's still an **API configuration issue** causing 404 errors.

## Issues Identified and Resolved

### 1. **Incorrect Architecture (CRITICAL) - ✅ RESOLVED**
**Problem**: Both Deployment and CronJobs were running simultaneously
- **Before**:
  - Deployment with 2 replicas running continuously
  - CronJobs running periodically
  - **Redundant and incorrect architecture**
- **After**:
  - Removed Deployment completely
  - Only CronJobs for periodic data extraction
  - **Correct architecture for batch data processing**

### 2. **Network Policy Issue (CRITICAL) - ✅ RESOLVED**
**Problem**: CronJob pods were blocked by network policies
- **Before**:
  - Network policy `allow-binance-data-extractor` targeted wrong labels
  - CronJob pods had labels `app=binance-extractor,component=klines-extractor`
  - Network policy looked for `app=binance-data-extractor,component=data-extraction`
  - **Result**: All outbound traffic blocked by `default-deny-all` policy
- **After**:
  - Created new network policy `allow-binance-extractor-cronjobs` with correct labels
  - **Result**: DNS resolution and outbound connectivity working

### 3. **API Configuration Error (CRITICAL) - ❌ STILL NEEDS FIX**
**Problem**: Application is using wrong API endpoint for futures data
- **Current**: Using spot API `https://api.binance.com` for futures data
- **Required**: Should use futures API `https://fapi.binance.com`
- **Impact**: 404 errors when trying to access `/fapi/v1/klines` on spot API

### 4. **Image Architecture Mismatch (CRITICAL) - ✅ RESOLVED**
**Problem**: Docker image was built for arm64 (Apple Silicon) but Kubernetes cluster runs on amd64 (x86_64)
- **Before**: `exec format error` when trying to run the container
- **After**: Built multi-architecture image supporting both arm64 and amd64
- **Solution**: Used `docker buildx` to create multi-architecture image

### 5. **Image Naming Inconsistency (CRITICAL) - ✅ RESOLVED**
**Problem**: Inconsistent Docker image names between deployment and cronjobs
- **Before**:
  - Deployment: `yurisa2/petrosa-binance-extractor:v1.0.71`
  - Cronjobs: `yurisa2/petrosa-binance-data-extractor:v1.0.71`
- **After**: Standardized to `yurisa2/petrosa-binance-data-extractor:VERSION_PLACEHOLDER`

## Current Status

### ✅ Architecture Corrected
- **Removed**: Deployment, Service, and HPA
- **Kept**: Only CronJobs for periodic data extraction
- **Result**: Correct architecture for batch data processing

### ✅ Network Connectivity Fixed
- **Created**: Network policy `allow-binance-extractor-cronjobs`
- **Targets**: Correct labels `app=binance-extractor,component=klines-extractor`
- **Result**: DNS resolution and outbound connectivity working
- **Test**: DNS resolution successful from cronjob-labeled pods

### ✅ CronJobs Status
```bash
# All cronjobs are properly configured and running
binance-klines-m5-production            */5 * * * *    <none>     False     1        2m2s            42d
binance-klines-m15-production           2 */15 * * *   <none>     False     0        110m            55d
binance-klines-h1-production            10 * * * *     <none>     False     0        42m             55d
# ... and more
```

### ❌ API Configuration Issue (Current Problem)
**Problem**: Application using wrong API endpoint
```
API request failed: <html>
<head><title>404 Not Found</title></head>
<body>
<center><h1>404 Not Found</h1></center>
<hr><center>nginx</center>
</body>
</html>
```

**Root Cause**:
- Configmap has `BINANCE_API_URL: https://api.binance.com` (spot API)
- Application tries to access `/fapi/v1/klines` on spot API
- Should use `BINANCE_FUTURES_API_URL: https://fapi.binance.com`

## Applied Fixes

### Fix 1: Removed Incorrect Deployment Architecture
**Actions**:
```bash
kubectl delete deployment petrosa-binance-data-extractor -n petrosa-apps
kubectl delete service petrosa-binance-data-extractor-service -n petrosa-apps
kubectl delete hpa petrosa-binance-data-extractor-hpa -n petrosa-apps
```

### Fix 2: Created Network Policy for CronJobs
**File**: `k8s/network-policy-cronjobs.yaml`
**Targets**: `app=binance-extractor,component=klines-extractor`
**Allows**: DNS (53/UDP), HTTPS (443/TCP), MySQL (3306/TCP), MongoDB (27017/TCP), etc.

### Fix 3: Built Multi-Architecture Docker Image
**Command**:
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t yurisa2/petrosa-binance-data-extractor:v1.0.71 --push .
```

### Fix 4: Standardized Image Naming
**File**: CronJob configurations
**Changes**: All cronjobs now use consistent image naming

## Remaining Issue: API Configuration

### Problem Analysis
The cronjobs are now running successfully but getting 404 errors because:
1. **Network connectivity**: ✅ Working (DNS resolution successful)
2. **API endpoint**: ❌ Wrong (using spot API instead of futures API)
3. **Application logic**: Trying to access `/fapi/v1/klines` on spot API

### Solution Required
Update the cronjob configurations to explicitly set the correct API environment variables:
```yaml
env:
- name: BINANCE_API_URL
  valueFrom:
    configMapKeyRef:
      name: petrosa-binance-data-extractor-config
      key: BINANCE_FUTURES_API_URL
- name: BINANCE_FUTURES_API_URL
  valueFrom:
    configMapKeyRef:
      name: petrosa-binance-data-extractor-config
      key: BINANCE_FUTURES_API_URL
```

## CI/CD Configuration

### ✅ VERSION_PLACEHOLDER Ready
The cronjob configurations use `VERSION_PLACEHOLDER` for CI/CD automation:
```yaml
image: yurisa2/petrosa-binance-data-extractor:VERSION_PLACEHOLDER
```

## Summary

**Status**: ✅ **ARCHITECTURE CORRECTED, NETWORK FIXED, API CONFIGURATION NEEDS UPDATE**

The petrosa-binance-data-extractor now has:
- ✅ **Correct Architecture**: Only CronJobs, no redundant Deployment
- ✅ **Network Connectivity**: Fixed with proper network policy
- ✅ **Image Architecture**: Multi-architecture support
- ✅ **Image Naming**: Consistent across all resources
- ✅ **CI/CD Ready**: VERSION_PLACEHOLDER configured
- ❌ **API Configuration**: Still using wrong API endpoint

**Current Status**: CronJobs are running successfully with network connectivity, but getting 404 errors due to wrong API endpoint configuration.

**Next Steps**:
1. Update cronjob configurations to use correct API endpoints
2. Test API connectivity after configuration update
3. Monitor cronjob success after API fix
