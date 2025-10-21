# Network Policy Fix for Klines Gap Filler CronJobs

## Issue Summary
**Date:** October 21, 2025
**Severity:** Critical
**Status:** Fixed

### Problem Description
All klines-gap-filler cronjobs were failing with DNS resolution errors:
```
Failed to resolve 'fapi.binance.com' ([Errno -3] Temporary failure in name resolution)
```

### Root Cause
The network policy `allow-binance-extractor-cronjobs` was targeting pods with label `component: klines-extractor`, but the klines-gap-filler cronjobs use the label `component: klines-gap-filler`. This mismatch meant:
- The gap-filler pods had no network policy explicitly allowing egress traffic
- The default-deny-all policy blocked all outbound connections
- DNS queries and HTTPS connections to Binance API failed

### Affected CronJobs
- `binance-klines-gap-filler` (all timeframes)
- `binance-klines-gap-filler-m5`
- `binance-klines-gap-filler-m15`
- `binance-klines-gap-filler-m30`
- `binance-klines-gap-filler-h1`
- `binance-klines-gap-filler-d1`

### Solution
Created a new network policy specifically for gap-filler pods:

**File:** `k8s/network-policy-gap-filler.yaml`

**Key Features:**
- Targets pods with labels: `app=binance-extractor` AND `component=klines-gap-filler`
- Allows egress to:
  - DNS (port 53, UDP and TCP)
  - HTTPS (port 443)
  - HTTP (port 80)
  - MySQL (port 3306)
  - MongoDB (port 27017)
  - PostgreSQL (port 5432)
  - OpenTelemetry (ports 4317, 4318)
  - NATS (port 4222)

### Verification
Tested with manual job trigger:
```bash
kubectl create job --from=cronjob/binance-klines-gap-filler-m5 test-gap-filler-m5 -n petrosa-apps
```

**Results:**
- ✅ Successfully connected to Binance API
- ✅ Successfully fetched and filled gaps for BTCUSDT (2479 records)
- ✅ Successfully fetched and filled gaps for ETHUSDT (2482 records)
- ✅ Connected to MySQL database
- ✅ Published completion messages to NATS

### Deployment
```bash
kubectl apply -f k8s/network-policy-gap-filler.yaml
```

### Prevention
To prevent similar issues in the future:
1. Always ensure network policies match the actual pod labels
2. Test new cronjobs immediately after deployment
3. Monitor cronjob failure rates in observability dashboards
4. Document all pod label conventions in the repository

### Related Files
- `k8s/network-policy-gap-filler.yaml` (new)
- `k8s/network-policy-cronjobs.yaml` (existing, for klines-extractor)
- `k8s/klines-gap-filler-cronjob.yaml` (all gap-filler cronjobs)

### Monitoring
After the next scheduled run (2 AM UTC daily), verify:
- CronJob success rate returns to normal
- No DNS resolution errors in logs
- Gap detection and filling completes successfully
- NATS messages are published correctly
