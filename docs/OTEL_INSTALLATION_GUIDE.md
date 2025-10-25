# OpenTelemetry Requirements Installation Guide

## ✅ Fixed Issues

The following issues have been resolved in the OpenTelemetry integration:

### 🔧 **Problematic Packages Removed**
- `opentelemetry-instrumentation-psutil` - **NOT AVAILABLE** in PyPI
- `opentelemetry-instrumentation-system-metrics` - **NOT AVAILABLE** in stable version
- `opentelemetry-instrumentation-aiohttp-client` - **NOT REQUIRED** for this project
- `opentelemetry-instrumentation-runtime-metrics` - **NOT AVAILABLE** in stable version
- `aiohttp` and `asyncio` dependencies - **NOT REQUIRED** for this synchronous project

### 🎯 **Working Packages Verified**
All packages in `requirements.txt` have been tested and verified to install correctly:

- ✅ `opentelemetry-api>=1.20.0`
- ✅ `opentelemetry-sdk>=1.20.0`
- ✅ `opentelemetry-exporter-otlp-proto-grpc>=1.20.0`
- ✅ `opentelemetry-exporter-otlp-proto-http>=1.20.0`
- ✅ `opentelemetry-distro>=0.41b0`
- ✅ `opentelemetry-instrumentation>=0.41b0`
- ✅ `opentelemetry-instrumentation-requests>=0.41b0`
- ✅ `opentelemetry-instrumentation-pymongo>=0.41b0`
- ✅ `opentelemetry-instrumentation-sqlalchemy>=0.41b0`
- ✅ `opentelemetry-instrumentation-logging>=0.41b0`
- ✅ `opentelemetry-instrumentation-urllib3>=0.41b0`
- ✅ `opentelemetry-semantic-conventions>=0.41b0`
- ✅ `opentelemetry-instrumentation-pymysql>=0.41b0` (via `petrosa-otel[mysql]`)

### 🔍 **MySQL Database Query Tracing**

This service now includes **PyMySQL instrumentation** for complete database observability:

**What's Instrumented:**
- All MySQL queries (SELECT, INSERT, UPDATE, DELETE)
- Query latency and execution time
- Database connection lifecycle
- Query parameters and statements
- Table names and operations

**Span Attributes:**
- `db.system`: "mysql"
- `db.statement`: SQL query text
- `db.name`: Database name
- `db.user`: Database user
- `net.peer.name`: Database host
- `net.peer.port`: Database port

**How to Enable:**

1. **For new jobs** (using `petrosa-otel` package):
```python
from petrosa_otel import initialize_telemetry_standard

initialize_telemetry_standard(
    service_name=constants.OTEL_SERVICE_NAME_KLINES,
    service_type="cronjob",
    enable_mysql=True,  # ← Enable MySQL instrumentation
    enable_mongodb=True,
)
```

2. **For legacy jobs** (using `utils.telemetry`):
MySQL instrumentation is **automatically enabled** in `utils/telemetry.py`. No additional configuration needed.

**Verification:**

To verify MySQL queries are being traced:

```bash
# Run any extraction job
python jobs/extract_klines.py --symbol BTCUSDT --interval 1h --limit 10

# Check trace output for MySQL spans in your OTLP backend (Grafana, Jaeger, etc.)
# Look for spans with:
# - operation: "query"
# - db.system: "mysql"
# - db.statement: "INSERT INTO klines_1h ..."
```

**Performance Impact:**

MySQL instrumentation has minimal overhead:
- < 1ms per query for span creation
- Asynchronous export (non-blocking)
- Automatic batching for efficiency

**Troubleshooting:**

If MySQL queries are not appearing in traces:

1. Verify `petrosa-otel[mysql]` is installed:
```bash
pip show opentelemetry-instrumentation-pymysql
```

2. Check instrumentation is enabled:
```bash
python -c "from opentelemetry.instrumentation.pymysql import PyMySQLInstrumentor; print(PyMySQLInstrumentor().is_instrumented_by_opentelemetry)"
```

3. Verify OTLP endpoint is configured:
```bash
echo $OTEL_EXPORTER_OTLP_ENDPOINT
```

## 🚀 **Installation Instructions**

### **Option 1: Virtual Environment (Recommended)**
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows

# Install requirements
pip install -r requirements.txt
```

### **Option 2: Direct Installation**
```bash
pip install -r requirements.txt
```

## 🧪 **Testing the Installation**

Run the test script to verify everything is working:
```bash
python test_otel_setup.py
```

Expected output:
```
🚀 OpenTelemetry Setup Test
==================================================
🔍 Testing imports...
✅ Constants imported successfully
✅ otel_init imported successfully
✅ TelemetryManager imported successfully

🔧 Testing OpenTelemetry setup...
✅ setup_telemetry completed with result: False
ℹ️  Telemetry setup returned False (expected without OTLP endpoint)

📦 Testing instrumentation packages...
✅ All packages imported successfully

==================================================
🎉 All tests passed! OpenTelemetry setup is working correctly.
```

## 🛠️ **Service Name Configuration**

The service names are now configurable via environment variables:

```bash
# Default values (if not set)
OTEL_SERVICE_NAME_KLINES=petrosa-binance-extractor
OTEL_SERVICE_NAME_FUNDING=petrosa-binance-extractor
OTEL_SERVICE_NAME_TRADES=petrosa-binance-extractor

# Custom values
export OTEL_SERVICE_NAME_KLINES="prod-klines-extractor"
export OTEL_SERVICE_NAME_FUNDING="prod-funding-extractor"
export OTEL_SERVICE_NAME_TRADES="prod-trades-extractor"
```

## 🏃‍♂️ **Running the Jobs**

All jobs now work correctly with OpenTelemetry:

```bash
# Production klines extractor
python jobs/extract_klines_production.py --help

# Manual klines extractor
python jobs/extract_klines.py --help

# Funding rates extractor
python jobs/extract_funding.py --help

# Trades extractor
python jobs/extract_trades.py --help
```

## 🐛 **Troubleshooting**

### **Issue: Package not found**
If you encounter missing package errors, ensure you're using the correct Python environment:
```bash
which python
pip list | grep opentelemetry
```

### **Issue: Import errors**
Make sure the project root is in your Python path:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### **Issue: OpenTelemetry not working**
Check that OpenTelemetry is properly configured:
```bash
python -c "from otel_init import setup_telemetry; print(setup_telemetry())"
```

## 📋 **Summary**

- ✅ **Requirements.txt fixed** - removed non-existent packages
- ✅ **All packages verified** - tested installation in clean virtual environment
- ✅ **Service names configurable** - via environment variables in constants.py
- ✅ **Jobs tested** - all extraction jobs work correctly
- ✅ **Test script provided** - verify installation with `test_otel_setup.py`
- ✅ **Graceful fallbacks** - application works with or without OpenTelemetry
