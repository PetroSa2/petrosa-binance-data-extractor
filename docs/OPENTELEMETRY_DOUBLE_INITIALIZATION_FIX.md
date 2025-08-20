# OpenTelemetry Double Initialization Fix

## Problem

The pipeline was failing with the error:
```
ValueError: I/O operation on closed file.
```

This error occurred during OpenTelemetry span export, specifically with the `ConsoleSpanExporter`. The root cause was **double initialization** of OpenTelemetry:

1. **Kubernetes jobs** use `opentelemetry-instrument` wrapper to launch applications
2. **Application code** also calls `setup_telemetry()` to initialize OpenTelemetry
3. Both try to initialize tracing/exporters, causing conflicts
4. During shutdown, one exporter (e.g., `ConsoleSpanExporter`) is already closed by the first shutdown, so the second attempt fails

## Solution

Implemented a **conditional initialization strategy** using the `OTEL_NO_AUTO_INIT` environment variable:

### 1. Modified Job Scripts

All job scripts now check for `OTEL_NO_AUTO_INIT` before calling `setup_telemetry()`:

```python
# Only initialize OpenTelemetry if not already initialized by opentelemetry-instrument
if not os.getenv("OTEL_NO_AUTO_INIT"):
    import constants
    from otel_init import setup_telemetry
    setup_telemetry(service_name=constants.OTEL_SERVICE_NAME_KLINES)
```

**Modified files:**
- `jobs/extract_klines.py`
- `jobs/extract_klines_production.py`
- `jobs/extract_klines_gap_filler.py`
- `jobs/extract_funding.py`
- `jobs/extract_trades.py`

### 2. Updated Kubernetes Manifests

Added `OTEL_NO_AUTO_INIT=1` environment variable to all CronJob templates:

```yaml
env:
- name: OTEL_NO_AUTO_INIT
  value: "1"
```

**Modified files:**
- `k8s/klines-gap-filler-cronjob.yaml`
- `k8s/klines-all-timeframes-cronjobs.yaml`

### 3. Updated Test Environment

Modified Makefile to set `OTEL_NO_AUTO_INIT=1` for test runs:

```makefile
run_unit_tests:
	@echo "🧪 Running unit tests..."
	OTEL_NO_AUTO_INIT=1 pytest tests/ -v --tb=short

coverage: install-dev
	@echo "📊 Running tests with coverage..."
	OTEL_NO_AUTO_INIT=1 pytest tests/ -v --cov=. --cov-report=xml --cov-report=term
```

## Initialization Modes

### Local Development (without `OTEL_NO_AUTO_INIT`)
```bash
python -m jobs.extract_klines --symbols BTCUSDT --period 1m
```
- Uses in-code initialization via `setup_telemetry()`
- Provides telemetry for local development and testing

### Production/Kubernetes (with `OTEL_NO_AUTO_INIT=1`)
```bash
opentelemetry-instrument python -m jobs.extract_klines --symbols BTCUSDT --period 1m
```
- Uses `opentelemetry-instrument` initialization only
- Prevents double initialization conflicts

### Testing (with `OTEL_NO_AUTO_INIT=1`)
```bash
OTEL_NO_AUTO_INIT=1 pytest tests/ -v
```
- Prevents double initialization during test runs
- Ensures tests run without OpenTelemetry conflicts

## Benefits

1. **Eliminates Pipeline Failures**: No more "I/O operation on closed file" errors
2. **Maintains Observability**: Both local and production environments have proper telemetry
3. **Follows Best Practices**: Aligns with OpenTelemetry recommendations for `opentelemetry-instrument`
4. **Backward Compatible**: Existing local development workflows continue to work
5. **Test Stability**: Tests run reliably without OpenTelemetry conflicts

## Verification

The fix has been verified by:

1. **Pipeline Tests**: `make run_pipeline` now completes successfully
2. **Unit Tests**: All 70 tests pass without OpenTelemetry errors
3. **Job Execution**: Gap filler and other jobs run correctly with `OTEL_NO_AUTO_INIT=1`
4. **Local Development**: Jobs still work for local development without the environment variable

## Related Documentation

- [OpenTelemetry Instrumentation Update](OPENTELEMETRY_INSTRUMENTATION_UPDATE.md)
- [README.md](../README.md#opentelemetry-configuration)
