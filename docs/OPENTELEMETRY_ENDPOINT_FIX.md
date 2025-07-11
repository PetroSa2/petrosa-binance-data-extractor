# OpenTelemetry Endpoint Fix

## Issue
The binance extractor jobs were showing OpenTelemetry errors at the end of successful runs:

```
Failed to export metrics to , error code: StatusCode.UNKNOWN
Failed to export traces to , error code: StatusCode.UNKNOWN
```

The error details indicated:
```
Failed to create channel to '':the target uri is not valid: dns:///
```

## Root Cause
The `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable in the `petrosa-common-config` ConfigMap was empty (`""`), causing the OpenTelemetry exporter to fail when trying to send metrics and traces.

## Solution
Updated the ConfigMap to point to the correct OpenTelemetry collector endpoint:

```bash
kubectl patch configmap petrosa-common-config -n petrosa-apps \
  --type='merge' \
  -p='{"data":{"OTEL_EXPORTER_OTLP_ENDPOINT":"http://otel-collector-opentelemetry-collector.petrosa-system.svc.cluster.local:4317"}}'
```

## Verification
- OpenTelemetry collector is running in `petrosa-system` namespace
- Service endpoint: `otel-collector-opentelemetry-collector.petrosa-system.svc.cluster.local:4317`
- Jobs now complete without telemetry errors

## Date Applied
2025-07-11

## Affected Components
- `petrosa-common-config` ConfigMap in `petrosa-apps` namespace
- All binance extractor jobs using OpenTelemetry instrumentation 