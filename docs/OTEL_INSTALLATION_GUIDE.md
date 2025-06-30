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
