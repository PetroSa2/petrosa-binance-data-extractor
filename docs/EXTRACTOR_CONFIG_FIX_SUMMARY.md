# Binance Data Extractor Configuration Fix Summary

## Issue Identified

The Binance Data Extractor service had a configuration issue where the API URL mapping was incorrect in the Kubernetes deployment and cronjob configurations.

### Root Cause

1. **Incorrect Key Mapping**: The deployment was trying to read `BINANCE_API_URL` from the `BINANCE_FUTURES_API_URL` key in the configmap
2. **Service-Specific Requirements**: This service primarily works with futures data and should use the futures API
3. **Missing Environment Variables**: Several environment variables referenced in the code were not defined in the configmap

### Service Context

**Important**: The Binance Data Extractor service is specifically designed to work with **futures data**. It accesses endpoints like `/fapi/v1/klines` which are only available on the futures API. Therefore, both `BINANCE_API_URL` and `BINANCE_FUTURES_API_URL` should point to the futures API.

### Specific Problems

```yaml
# ❌ INCORRECT - Before Fix (Key mapping issue)
- name: BINANCE_API_URL
  valueFrom:
    configMapKeyRef:
      name: petrosa-binance-data-extractor-config
      key: BINANCE_FUTURES_API_URL  # Wrong key mapping!

# Configmap had inconsistent URLs
BINANCE_API_URL: "https://api.binance.com"  # Wrong for this service
BINANCE_FUTURES_API_URL: "https://fapi.binance.com"  # Correct
```

## Applied Fixes

### 1. Fixed Configmap Configuration

**File**: `k8s/configmap.yaml`

**Changes**:
- Set both API URLs to point to futures API (correct for this service)
- Added missing environment variables
- Ensured proper key naming

```yaml
# ✅ CORRECT - After Fix
data:
  # Binance API configuration - this service primarily works with futures data
  BINANCE_API_URL: "https://fapi.binance.com"           # Futures API (correct for this service)
  BINANCE_FUTURES_API_URL: "https://fapi.binance.com"   # Futures API

  # Added missing configuration keys
  API_RATE_LIMIT_PER_MINUTE: "1200"
  REQUEST_DELAY_SECONDS: "0.1"
  MIN_BATCH_SIZE: "100"
  MAX_BATCH_SIZE: "5000"
```

### 2. Fixed Deployment Configuration

**File**: `k8s/deployment.yaml`

**Changes**:
- Corrected key mapping for `BINANCE_API_URL` to use `BINANCE_FUTURES_API_URL` key
- Added missing environment variables from configmap

```yaml
# ✅ CORRECT - After Fix
- name: BINANCE_API_URL
  valueFrom:
    configMapKeyRef:
      name: petrosa-binance-data-extractor-config
      key: BINANCE_FUTURES_API_URL  # Correct key for this service!

# Added missing environment variables
- name: API_RATE_LIMIT_PER_MINUTE
  valueFrom:
    configMapKeyRef:
      name: petrosa-binance-data-extractor-config
      key: API_RATE_LIMIT_PER_MINUTE
- name: REQUEST_DELAY_SECONDS
  valueFrom:
    configMapKeyRef:
      name: petrosa-binance-data-extractor-config
      key: REQUEST_DELAY_SECONDS
- name: MIN_BATCH_SIZE
  valueFrom:
    configMapKeyRef:
      name: petrosa-binance-data-extractor-config
      key: MIN_BATCH_SIZE
- name: MAX_BATCH_SIZE
  valueFrom:
    configMapKeyRef:
      name: petrosa-binance-data-extractor-config
      key: MAX_BATCH_SIZE
```

### 3. Fixed Cronjob Configuration

**File**: `k8s/klines-mongodb-production.yaml`

**Changes**:
- Corrected key mapping for `BINANCE_API_URL` in cronjob

```yaml
# ✅ CORRECT - After Fix
- name: BINANCE_API_URL
  valueFrom:
    configMapKeyRef:
      name: petrosa-binance-data-extractor-config
      key: BINANCE_FUTURES_API_URL  # Correct key for this service!
```

## Configuration Architecture

### Service-Specific Configmap

The extractor now uses a dedicated configmap (`petrosa-binance-data-extractor-config`) that contains:

1. **API Configuration**: Both URLs point to futures API (correct for this service)
2. **Extraction Settings**: Worker limits, rate limits, timeouts
3. **Database Settings**: Batch sizes and adapter configuration
4. **Performance Settings**: Memory limits, request delays
5. **Health Check Settings**: Intervals and timeouts

### Environment Variable Hierarchy

1. **Service-Specific Configmap**: `petrosa-binance-data-extractor-config`
   - Binance API URLs (both futures)
   - Extraction parameters
   - Performance settings

2. **Common Configmap**: `petrosa-common-config`
   - NATS configuration
   - OpenTelemetry settings
   - Environment settings

3. **Secrets**: `petrosa-sensitive-credentials`
   - Database URIs
   - API keys
   - Sensitive configuration

## API URL Usage for This Service

### Why Both URLs Point to Futures API

This service is specifically designed for **futures data extraction**:

1. **Primary Endpoints**: `/fapi/v1/klines`, `/fapi/v1/fundingRate`
2. **Data Type**: Futures klines, funding rates, perpetual contracts
3. **Service Purpose**: Historical futures data extraction and gap filling

### Service-Specific Requirements

- **Klines Extraction**: Uses `/fapi/v1/klines` endpoint
- **Funding Rates**: Uses `/fapi/v1/fundingRate` endpoint
- **Gap Filling**: Works with futures data patterns
- **Database Storage**: Stores futures-specific data structures

## Validation

### Configuration Validation

To validate the configuration is correct:

```bash
# Check configmap
kubectl --kubeconfig=k8s/kubeconfig.yaml get configmap petrosa-binance-data-extractor-config -n petrosa-apps -o yaml

# Check deployment environment variables
kubectl --kubeconfig=k8s/kubeconfig.yaml describe deployment petrosa-binance-data-extractor -n petrosa-apps

# Check cronjob environment variables
kubectl --kubeconfig=k8s/kubeconfig.yaml describe cronjob klines-mongodb-production -n petrosa-apps
```

### Expected Environment Variables

The deployment should now have these environment variables correctly set:

```bash
BINANCE_API_URL=https://fapi.binance.com
BINANCE_FUTURES_API_URL=https://fapi.binance.com
API_RATE_LIMIT_PER_MINUTE=1200
REQUEST_DELAY_SECONDS=0.1
MIN_BATCH_SIZE=100
MAX_BATCH_SIZE=5000
```

## Deployment Commands

### Apply Configuration Changes

```bash
# Apply the updated configmap
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/configmap.yaml

# Apply the updated deployment
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/deployment.yaml

# Apply the updated cronjob
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/klines-mongodb-production.yaml
```

### Restart Deployment

```bash
# Restart the deployment to pick up new configuration
kubectl --kubeconfig=k8s/kubeconfig.yaml rollout restart deployment petrosa-binance-data-extractor -n petrosa-apps

# Check rollout status
kubectl --kubeconfig=k8s/kubeconfig.yaml rollout status deployment petrosa-binance-data-extractor -n petrosa-apps
```

## Benefits of This Fix

1. **Correct API Access**: Service now accesses the correct futures API endpoints
2. **Service Isolation**: Dedicated configmap for extractor-specific settings
3. **Configuration Completeness**: All required environment variables are properly defined
4. **Maintainability**: Clear separation between service-specific and common configuration
5. **Consistency**: All deployments and cronjobs use the same configuration pattern
6. **No Breaking Changes**: Other services are not affected by this configuration

## Service-Specific Considerations

### Why This Service Uses Futures API

1. **Data Type**: Extracts futures klines and funding rates
2. **Endpoints**: Uses `/fapi/v1/*` endpoints exclusively
3. **Market Type**: Works with perpetual contracts and futures data
4. **Integration**: Feeds data to trading strategies that operate on futures

### Other Services Configuration

**Note**: Other services in the Petrosa ecosystem may use different API configurations:

- **Trade Engine**: May use spot API for certain operations
- **Socket Client**: Uses WebSocket endpoints for real-time data
- **TA Bot**: Consumes extracted data, doesn't directly access Binance API

## Future Considerations

1. **Configuration Validation**: Consider adding validation scripts to check configuration consistency
2. **Environment-Specific Configs**: May need different configs for staging/production
3. **Configuration Monitoring**: Monitor for configuration drift or inconsistencies
4. **Documentation**: Keep this documentation updated as configuration evolves
5. **Service Isolation**: Ensure each service has its own specific configuration

## Related Files

- `k8s/configmap.yaml` - Service-specific configuration
- `k8s/deployment.yaml` - Deployment with corrected environment variables
- `k8s/klines-mongodb-production.yaml` - Cronjob with corrected configuration
- `constants.py` - Application constants and defaults
- `fetchers/client.py` - Binance API client implementation
