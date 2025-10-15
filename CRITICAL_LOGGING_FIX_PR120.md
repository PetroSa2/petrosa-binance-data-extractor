# Critical Logging Fix - PR #120

## Problem Discovered

After deploying PR #119 (OTLP log export), logs from binance-data-extractor were **still not appearing** in Grafana Loki.

## Root Cause Analysis

### Investigation

Checked job execution logs and found:
- ✅ OTEL trace context present (`otelSpanID`, `otelTraceID` in JSON logs)
- ❌ But all trace IDs were zeros: `"trace_id": "00000000000000000000000000000000"`
- ❌ No "OTLP logging handler attached" message visible
- ❌ Logs not reaching Grafana Loki

### Root Cause Found

The `setup_logging()` function in `utils/logger.py` **removes ALL handlers** unconditionally:

```python
# Lines 116-118 (PROBLEM)
# Remove existing handlers
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
```

**Execution Order**:
1. `otel_init.py` auto-imported on module load
2. `attach_logging_handler_simple()` attaches OTLP handler ✅
3. Job calls `setup_logging()` in main()
4. `setup_logging()` **removes ALL handlers** including OTLP ❌
5. Only console handler remains
6. Logs go to stdout but NOT to Grafana Loki

## Solution Implemented (PR #120)

Modified `setup_logging()` to **preserve OTLP handlers**:

```python
# Preserve OTLP handlers before clearing
from opentelemetry.sdk._logs import LoggingHandler as OTELLoggingHandler
otlp_handlers = [h for h in root_logger.handlers if isinstance(h, OTELLoggingHandler)]

# Remove existing handlers (except OTLP)
for handler in root_logger.handlers[:]:
    if not isinstance(handler, OTELLoggingHandler):
        root_logger.removeHandler(handler)

# ... add console handler ...

# Re-attach preserved OTLP handlers
for otlp_handler in otlp_handlers:
    if otlp_handler not in root_logger.handlers:
        root_logger.addHandler(otlp_handler)
```

Also changed:
- `LoggingInstrumentor().instrument(set_logging_format=True)` → `False`
- This prevents LoggingInstrumentor from clearing handlers

## Expected Outcome

After PR #120 deployment:
- ✅ OTLP handler survives `setup_logging()` reconfiguration
- ✅ Both console handler (stdout) AND OTLP handler (Loki export) active
- ✅ Logs visible in both places simultaneously
- ✅ All job execution logs flow to Grafana Cloud Loki

## Verification Steps

### 1. Check Handler Count in New Job
```bash
kubectl logs <NEW_JOB_POD> | grep "handler"
```

Expected to see handler preservation messages.

### 2. Query Grafana Loki
```logql
{service_name="binance-data-extractor"} |= ""
```

Should now see job execution logs.

### 3. Verify Dual Output
- ✅ Logs in stdout (kubectl logs) - JSON format
- ✅ Logs in Grafana Loki - same content via OTLP export

## Timeline

- **PR #119**: Initial OTLP log export (deployed v1.0.84)
- **Issue Found**: Logs not reaching Grafana Loki
- **Root Cause**: `setup_logging()` clearing all handlers
- **PR #120**: Handler preservation fix
- **Status**: Merged, deploying v1.0.85

## Key Learning

**For services with custom logging setup functions**:
- Always check if they clear/replace handlers
- Preserve OTLP handlers before reconfiguration
- Re-attach after custom setup completes
- Or modify custom setup to skip OTLP handlers

This pattern may apply to other services with similar logging setup!
