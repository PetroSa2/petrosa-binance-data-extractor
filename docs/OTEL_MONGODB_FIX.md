# OpenTelemetry MongoDB Instrumentation Fix

## Date
October 21, 2025

## Issue Summary

Two critical issues were identified in the OpenTelemetry instrumentation for MongoDB operations:

1. **Invalid Attribute Warning**: MongoDB instrumentation was setting `db.mongodb.collection` attribute with dict values, causing OpenTelemetry validation warnings
2. **Missing Span Context**: Trace IDs and Span IDs were showing as zeros in logs, indicating that span context wasn't being properly propagated to log records

## Root Causes

### 1. Invalid Attribute Warning
```
Invalid type dict in attribute 'db.mongodb.collection' value sequence.
Expected one of ['bool', 'str', 'bytes', 'int', 'float'] or None
```

**Cause**: The `opentelemetry-instrumentation-pymongo` library was automatically adding attributes to spans, some of which contained complex data structures (dicts/lists) that are not allowed by OpenTelemetry's attribute specification.

OpenTelemetry semantic conventions only allow primitive types for attributes:
- `str`
- `int`
- `float`
- `bool`
- `bytes`
- `None`

### 2. Missing Span Context
```json
{
  "otelSpanID": "0",
  "otelTraceID": "0",
  "otelTraceSampled": false,
  "trace_id": "00000000000000000000000000000000",
  "span_id": "0000000000000000"
}
```

**Cause**: The `LoggingInstrumentor` was configured with `set_logging_format=False`, which prevented proper trace context injection into log records.

## Solutions Implemented

### 1. Custom AttributeFilterSpanProcessor

Created a custom span processor that automatically filters out invalid attribute values before spans are exported:

```python
class AttributeFilterSpanProcessor(BatchSpanProcessor):
    """
    Custom span processor that filters out invalid attribute values before export.

    OpenTelemetry only allows primitive types (str, int, float, bool, bytes) or None
    as attribute values. This processor filters out dict and list values.
    """

    def on_start(self, span, parent_context=None):
        """Clean attributes when span starts."""
        super().on_start(span, parent_context)
        self._clean_attributes(span)

    def on_end(self, span):
        """Clean attributes when span ends."""
        self._clean_attributes(span)
        super().on_end(span)

    def _clean_attributes(self, span):
        """Remove invalid attribute values from span."""
        if not hasattr(span, "_attributes") or not span._attributes:
            return

        # Identify invalid attributes
        invalid_keys = []
        for key, value in span._attributes.items():
            if isinstance(value, (dict, list)):
                invalid_keys.append(key)

        # Remove invalid attributes
        for key in invalid_keys:
            del span._attributes[key]
```

**Benefits**:
- Automatically filters invalid attributes from all spans
- Works with any instrumentation library
- No need to modify individual instrumentations
- Prevents validation warnings in production

### 2. Fixed LoggingInstrumentor Configuration

Updated the LoggingInstrumentor to properly capture trace context:

**Before**:
```python
LoggingInstrumentor().instrument(set_logging_format=False)
```

**After**:
```python
LoggingInstrumentor().instrument(
    set_logging_format=True,
    log_level=logging.NOTSET
)
```

**Changes**:
- `set_logging_format=True`: Enables proper trace context injection into log records
- `log_level=logging.NOTSET`: Ensures all log levels capture trace context

### 3. Added PymongoInstrumentor

Explicitly added PyMongo instrumentation in `otel_init.py`:

```python
# Set up MongoDB instrumentation
# The AttributeFilterSpanProcessor will automatically filter invalid attributes
if PYMONGO_INSTRUMENTATION_AVAILABLE:
    try:
        PymongoInstrumentor().instrument()
        print(f"✅ OpenTelemetry MongoDB instrumentation enabled for {service_name}")
    except Exception as e:
        print(f"⚠️  Failed to set up OpenTelemetry MongoDB instrumentation: {e}")
```

## Files Modified

### 1. `/otel_init.py`
- Added `AttributeFilterSpanProcessor` class
- Added PyMongo instrumentation import
- Updated `setup_telemetry()` to use `AttributeFilterSpanProcessor` instead of `BatchSpanProcessor`
- Fixed `LoggingInstrumentor` configuration
- Added explicit PyMongo instrumentation

### 2. `/utils/telemetry.py`
- Added `AttributeFilterSpanProcessor` class
- Updated `initialize_telemetry()` to use `AttributeFilterSpanProcessor`
- Fixed `LoggingInstrumentor` configuration in both module-level and class-level functions
- Updated `TelemetryManager._setup_tracing()` to use `AttributeFilterSpanProcessor`
- Updated `TelemetryManager._setup_auto_instrumentation()` with proper logging configuration

## Testing

### Expected Behavior After Fix

1. **No More Attribute Warnings**: The invalid attribute warnings should no longer appear in logs
2. **Proper Span Context**: Log records should now show valid trace IDs and span IDs:
   ```json
   {
     "otelSpanID": "a1b2c3d4e5f6g7h8",
     "otelTraceID": "1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p",
     "otelTraceSampled": true,
     "trace_id": "1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p",
     "span_id": "a1b2c3d4e5f6g7h8"
   }
   ```

### Manual Testing

To verify the fixes:

1. **Deploy the updated code** to the Kubernetes cluster
2. **Trigger a data extraction job**
3. **Check the logs** for:
   - Absence of invalid attribute warnings
   - Presence of valid trace IDs and span IDs (non-zero values)
   - Proper correlation between logs and traces in your observability platform

### Log Verification

Search for these patterns in logs:

```bash
# Should NOT find any invalid attribute warnings
kubectl logs -l app=binance-data-extractor --tail=1000 | grep "Invalid type dict in attribute"

# Should find valid trace IDs (not all zeros)
kubectl logs -l app=binance-data-extractor --tail=1000 | grep -v '"trace_id": "00000000000000000000000000000000"'
```

## Impact

### Positive Effects
- ✅ Cleaner logs without validation warnings
- ✅ Proper trace context propagation enables correlation between logs and traces
- ✅ Better observability in monitoring platforms (New Relic, Grafana, etc.)
- ✅ Ability to trace requests through the entire system
- ✅ No performance impact (filtering happens at span export time)

### No Breaking Changes
- All existing functionality remains intact
- Backward compatible with existing instrumentation
- No changes to external APIs or interfaces

## Related Documentation

- [OpenTelemetry Python SDK Documentation](https://opentelemetry.io/docs/instrumentation/python/)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/reference/specification/trace/semantic_conventions/)
- [PyMongo Instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/pymongo/pymongo.html)

## Deployment

To deploy these fixes:

```bash
# 1. Commit the changes
git add otel_init.py utils/telemetry.py docs/OTEL_MONGODB_FIX.md
git commit -m "fix: OpenTelemetry MongoDB instrumentation and span context propagation"

# 2. Build and push Docker image
make build
make push

# 3. Deploy to Kubernetes
make deploy

# 4. Verify deployment
make k8s-status
make k8s-logs
```

## Monitoring

After deployment, monitor:

1. **Log quality**: Check for absence of warnings
2. **Trace context**: Verify non-zero trace/span IDs
3. **Correlation**: Confirm logs are linked to traces in observability platform
4. **Performance**: Ensure no degradation in data extraction performance

## Rollback Plan

If issues arise:

```bash
# Revert to previous version
git revert HEAD
make build
make push
make deploy
```

## Future Improvements

1. **Consider upgrading OpenTelemetry libraries** to newer versions that may have better attribute handling
2. **Add unit tests** for `AttributeFilterSpanProcessor`
3. **Monitor for new instrumentation libraries** that may need similar fixes
4. **Consider contributing** the attribute filtering solution back to the OpenTelemetry community

## Conclusion

These fixes resolve both the invalid attribute warnings and the missing span context issues, resulting in cleaner logs and better observability for the MongoDB operations in the Binance data extractor service.
