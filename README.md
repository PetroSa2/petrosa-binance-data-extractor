# Petrosa Binance Data Extractor

A comprehensive historical data extraction system for Binance cryptocurrency exchange, designed to collect, process, and store market data including klines (candlesticks), funding rates, and trades data for analysis and trading strategies.

## 🚀 Features

- **Historical Data Extraction**: Extract klines, funding rates, and trades data from Binance API
- **Multiple Database Support**: Store data in MongoDB, MySQL, or PostgreSQL
- **Gap Detection & Filling**: Automatically detect and fill missing data gaps
- **Production-Ready Jobs**: Kubernetes-compatible batch processing jobs
- **Parallel Processing**: Multi-threaded extraction for high performance
- **Data Validation**: Pydantic-based data models with comprehensive validation
- **OpenTelemetry Integration**: Full observability with traces, metrics, and logs
- **Flexible Configuration**: Environment-based configuration with command-line overrides

## 📋 Requirements

- **Python 3.11+**: Required for development and runtime
- **Docker**: Required for containerization and local testing
- **kubectl**: Required for Kubernetes deployment (remote cluster)
- **Make**: Required for using the Makefile commands

## 🛠️ Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/petrosa/petrosa-binance-data-extractor.git
cd petrosa-binance-data-extractor

# Complete setup
make setup

# Run extraction jobs
python -m jobs.extract_klines_production --period 15m
python -m jobs.extract_funding
python -m jobs.extract_trades

# Run complete pipeline
make pipeline
```

### Docker

```bash
# Build image
make build

# Run container
make run-docker

# Test container
make container
```

### Kubernetes Deployment

```bash
# Deploy to Kubernetes
make deploy

# Check status
make k8s-status

# View logs
make k8s-logs
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BINANCE_API_URL` | `https://api.binance.com` | Binance REST API URL |
| `BINANCE_FUTURES_API_URL` | `https://fapi.binance.com` | Binance Futures API URL |
| `DEFAULT_SYMBOLS` | `BTCUSDT,ETHUSDT,BNBUSDT` | Default trading symbols |
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection URI |
| `MYSQL_URI` | `mysql://user:pass@localhost:3306` | MySQL connection URI |
| `POSTGRESQL_URI` | `postgresql://user:pass@localhost:5432` | PostgreSQL connection URI |
| `DB_ADAPTER` | `mysql` | Default database adapter |
| `DB_BATCH_SIZE` | `1000` | Database batch size for writes |
| `LOG_LEVEL` | `INFO` | Logging level |
| `MAX_WORKERS` | `4` | Maximum parallel workers |
| `LOOKBACK_HOURS` | `24` | Default lookback period in hours |

### Supported Data Types

The extractor supports the following Binance data types:

- **Klines (Candlesticks)**: OHLCV data for various time intervals
- **Funding Rates**: Perpetual contract funding rates
- **Trades**: Individual trade data
- **Gap Filling**: Automatic detection and filling of missing data

### Supported Intervals

- **1m, 3m, 5m, 15m, 30m**: Short-term intervals
- **1h, 2h, 4h, 6h, 8h, 12h**: Medium-term intervals
- **1d, 3d**: Long-term intervals
- **1w, 1M**: Weekly and monthly intervals

## 🏗️ Architecture

### Components

1. **Extraction Jobs**: Batch processing jobs for different data types
2. **Fetchers**: API clients for Binance REST endpoints
3. **Database Adapters**: Abstraction layer for multiple databases
4. **Data Models**: Pydantic models for data validation
5. **Pipeline Runner**: Orchestration for running multiple jobs

### Data Flow

```
Binance API → Fetchers → Data Models → Database Adapters → Storage
```

### Job Types

- **Production Klines Extractor**: Automated klines extraction with gap detection
- **Gap Filler**: Detect and fill missing data periods
- **Funding Rates Extractor**: Extract funding rate data
- **Trades Extractor**: Extract individual trade data

## 🧪 Testing

### Test Categories

- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **End-to-End Tests**: Full system testing

### Running Tests

```bash
# Run all tests
make test

# Run specific test categories
make unit
make integration
make e2e

# Run with coverage
make coverage

# Generate HTML coverage report
make coverage-html
```

### Test Coverage

The service maintains high test coverage across all components:

- Data models: 100%
- Database adapters: 95%
- Fetchers: 90%
- Jobs: 85%

## 🐳 Docker

### Multi-stage Build

The Dockerfile uses multi-stage builds for optimized production images:

- **Builder Stage**: Install dependencies and build
- **Production Stage**: Minimal runtime image
- **Development Stage**: Includes development tools
- **Testing Stage**: Includes test dependencies

### Image Variants

- `petrosa-binance-data-extractor:latest` - Production image
- `petrosa-binance-data-extractor:alpine` - Lightweight Alpine image
- `petrosa-binance-data-extractor:dev` - Development image

## ☸️ Kubernetes

### Deployment

The service is deployed to Kubernetes with:

- **CronJobs**: Scheduled data extraction jobs
- **ConfigMaps**: Configuration management
- **Secrets**: Database credentials and API keys
- **Resource Limits**: Memory and CPU constraints
- **Security**: Non-root user and read-only filesystem

### Monitoring

- **Prometheus Metrics**: Available at `/metrics`
- **Health Checks**: Available at `/healthz` and `/ready`
- **OpenTelemetry**: Distributed tracing and metrics

### Configuration

Configuration is managed via Kubernetes ConfigMaps and Secrets:

- **ConfigMap**: `petrosa-binance-data-extractor-config`
- **Secrets**: Uses existing `petrosa-sensitive-credentials`

## 📊 Monitoring

### Health Endpoints

- `GET /healthz` - Liveness probe
- `GET /ready` - Readiness probe
- `GET /metrics` - Prometheus metrics
- `GET /` - Service information

### Metrics

The service exposes the following metrics:

- **Extraction Metrics**: Records processed, errors, gaps found
- **Performance Metrics**: Memory usage, CPU usage, processing time
- **Database Metrics**: Connection status, query performance
- **API Metrics**: Request success rate, response times

### Logging

Structured JSON logging with configurable levels:

```json
{
  "timestamp": "2024-01-01T00:00:00.000Z",
  "level": "INFO",
  "logger": "jobs.extract_klines_production",
  "message": "Starting klines extraction",
  "symbols": ["BTCUSDT"],
  "period": "15m",
  "start_date": "2024-01-01T00:00:00Z"
}
```

## 🔧 Development

### Project Structure

```
petrosa-binance-data-extractor/
├── jobs/                   # Data extraction jobs
│   ├── extract_klines_production.py  # Production klines extractor
│   ├── extract_klines_gap_filler.py  # Gap detection and filling
│   ├── extract_funding.py            # Funding rates extraction
│   └── extract_trades.py             # Trades extraction
├── fetchers/              # API clients
│   ├── client.py          # Base Binance client
│   ├── klines.py          # Klines fetcher
│   ├── funding.py         # Funding rates fetcher
│   └── trades.py          # Trades fetcher
├── models/                # Data models
│   ├── base.py            # Base model
│   ├── kline.py           # Kline data model
│   ├── funding_rate.py    # Funding rate model
│   └── trade.py           # Trade model
├── db/                    # Database adapters
│   ├── base_adapter.py    # Base adapter interface
│   ├── mongodb_adapter.py # MongoDB adapter
│   └── mysql_adapter.py   # MySQL adapter
├── utils/                 # Utilities
│   ├── logger.py          # Logging configuration
│   ├── time_utils.py      # Time utilities
│   └── telemetry.py       # OpenTelemetry setup
├── socket_client/         # WebSocket client (separate component)
├── tests/                 # Test suite
├── k8s/                   # Kubernetes manifests
├── scripts/               # Automation scripts
├── docs/                  # Documentation
└── requirements.txt       # Dependencies
```

### Development Commands

```bash
# Setup development environment
make setup

# Code quality checks
make format
make lint
make type-check

# Run tests
make test

# Security scan
make security

# Build and deploy
make build
make deploy
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the full test suite
6. Submit a pull request

## 🚨 Troubleshooting

### Common Issues

#### Database Connection Issues

```bash
# Check database connectivity
python -c "from db import get_adapter; print('Database adapter available')"

# Test MongoDB connection
python -c "import pymongo; print('MongoDB library available')"

# Test MySQL connection
python -c "import pymysql; print('MySQL library available')"

# Check environment variables
env | grep -E "(MONGODB|MYSQL|POSTGRESQL|DB)"
```

#### API Connection Issues

```bash
# Check Binance API connectivity
curl -s https://api.binance.com/api/v3/ping

# Test API rate limits
curl -s https://api.binance.com/api/v3/exchangeInfo | head -20

# Check environment variables
env | grep -E "(BINANCE|API)"
```

#### Kubernetes Issues

```bash
# Check pod status
kubectl --kubeconfig=k8s/kubeconfig.yaml get pods -n petrosa-apps -l app=binance-data-extractor

# View logs
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -n petrosa-apps -l app=binance-data-extractor

# Check cronjob status
kubectl --kubeconfig=k8s/kubeconfig.yaml get cronjobs -n petrosa-apps
```

#### Performance Issues

- Check memory usage: `docker stats` or Kubernetes metrics
- Monitor database connection pool
- Verify API rate limits
- Check extraction job logs

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python -m jobs.extract_klines_production --period 15m
```

## 📚 API Reference

### Extraction Jobs

```python
# Production klines extraction
python -m jobs.extract_klines_production --period 15m --symbols BTCUSDT,ETHUSDT

# Gap filling
python -m jobs.extract_klines_gap_filler --period 1h --symbols BTCUSDT

# Funding rates extraction
python -m jobs.extract_funding --symbols BTCUSDT,ETHUSDT

# Trades extraction
python -m jobs.extract_trades --symbols BTCUSDT
```

### Data Models

```python
from models.kline import KlineModel
from models.funding_rate import FundingRateModel
from models.trade import TradeModel

# Create kline model
kline = KlineModel(
    symbol="BTCUSDT",
    interval="15m",
    open_time=datetime.now(),
    open_price=Decimal("50000.00"),
    high_price=Decimal("50100.00"),
    low_price=Decimal("49900.00"),
    close_price=Decimal("50050.00"),
    volume=Decimal("100.5")
)

# Create funding rate model
funding_rate = FundingRateModel(
    symbol="BTCUSDT",
    funding_rate=Decimal("0.0001"),
    funding_time=datetime.now()
)
```

### Database Adapters

```python
from db import get_adapter

# Get MongoDB adapter
mongodb_adapter = get_adapter("mongodb", "mongodb://localhost:27017")

# Get MySQL adapter
mysql_adapter = get_adapter("mysql", "mysql://user:pass@localhost:3306/db")

# Use adapter
with mongodb_adapter:
    mongodb_adapter.insert_klines(klines_data)
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support

For support and questions:

- **Issues**: [GitHub Issues](https://github.com/petrosa/petrosa-binance-data-extractor/issues)
- **Documentation**: [Project Wiki](https://github.com/petrosa/petrosa-binance-data-extractor/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/petrosa/petrosa-binance-data-extractor/discussions)

## 🔗 Related Projects

- [Petrosa TA Bot](https://github.com/petrosa/petrosa-bot-ta-analysis) - Technical analysis bot
- [Petrosa Trade Engine](https://github.com/petrosa/petrosa-tradeengine) - Trading engine
- [Petrosa Socket Client](https://github.com/petrosa/petrosa-socket-client) - Real-time WebSocket client

---

**🚀 Production-ready historical data extraction system for Binance cryptocurrency exchange**
