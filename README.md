# Petrosa Binance Data Extractor

A robust, production-ready cryptocurrency data extraction system designed for enterprise-scale Binance Futures data collection. This system provides automated, parallel extraction of market data across multiple timeframes with comprehensive Kubernetes deployment, monitoring, and operational capabilities.

## 🚀 Key Features

### Enterprise-Grade Production System
- **🔄 Fully Automated Extraction**: Production extractor with auto-detection of last timestamp and gap-filling
- **⏰ Multi-Timeframe Support**: Simultaneous extraction across m5, m## 📚 Documen## 📚 Quick References## Production Guides
- **[Production Readiness Checklist](docs/PRODUCTION_READINESS.md)** - Complete pre-deployment validation
- **[Operations Guide](docs/OPERATIONS_GUIDE.md)** - Day-to-day operations, monitoring, and troubleshooting
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Step-by-step deployment instructions
- **[Production Summary](docs/PRODUCTION_SUMMARY.md)** - Architecture overview and system design

### Setup Guides
- **[Docker Hub Integration](docs/DOCKERHUB_SETUP.md)** - Docker Hub CI/CD setup and configuration
- **[Local Deployment](docs/LOCAL_DEPLOY.md)** - Local development and testing setup
- **[Namespace Configuration](docs/NAMESPACE_UPDATE.md)** - Kubernetes namespace setup and migration

### Post-Deployment
- **[Deployment Complete Guide](docs/DEPLOYMENT_COMPLETE.md)** - Post-deployment summary and next steps
- **[Versioning Guide](docs/VERSIONING_GUIDE.md)** - Automatic versioning and release management

### Development & CI/CD
- **[Test Implementation Guide](docs/TEST_IMPLEMENTATION_GUIDE.md)** - Testing strategies and best practices
- **[OpenTelemetry Setup](docs/OTEL_INSTALLATION_GUIDE.md)** - Observability and monitoring setup
- **🏃‍♂️ Parallel Processing**: Extract 20+ symbols simultaneously with optimized worker pools
- **🎯 Zero Configuration**: Production system requires no manual start/end dates
- **📊 Financial Market Standards**: Proper table naming conventions following financial industry standards

### Kubernetes-Native Architecture
- **🔧 Production CronJobs**: Scheduled extraction for all timeframes with optimal resource allocation
- **🛡️ Security-First**: Non-root containers, secret management, and RBAC compliance
- **📈 Auto-Scaling**: Resource-optimized deployments with horizontal scaling capabilities
- **🔍 Comprehensive Monitoring**: Built-in observability with structured logging and health checks

### Database & Data Management
- **💾 Multi-Database Support**: MongoDB and MySQL adapters with robust connection handling (PostgreSQL planned)
- **🔄 Incremental Updates**: Smart gap detection and backfill capabilities
- **✅ Data Validation**: Pydantic v2 models ensuring data integrity
- **📊 Optimized Storage**: Efficient indexing and partitioning strategies

### Developer Experience
- **🚀 One-Command Deployment**: Single script deployment with full validation
- **📚 Comprehensive Documentation**: Operations guides, troubleshooting, and best practices
- **🧪 Full Test Coverage**: Unit, integration, and end-to-end testing
- **🔄 CI/CD Pipeline**: Automated testing, building, and deployment via GitHub Actions
- **🏷️ Automatic Versioning**: Semantic versioning with automatic tag creation and release management

## 📋 Project Structure

```
petrosa-binance-data-extractor/
├── constants.py              # Central configuration
├── models/                   # Pydantic data models
│   ├── base.py              # Base models with common fields
│   ├── kline.py             # Candlestick data model
│   ├── trade.py             # Trade data model
│   └── funding_rate.py      # Funding rate model
├── db/                      # Database adapters
│   ├── base_adapter.py      # Abstract base adapter
│   ├── mongodb_adapter.py   # MongoDB implementation
│   └── mysql_adapter.py     # MySQL implementation
├── fetchers/                # API clients and data fetchers
│   ├── client.py            # Binance API HTTP client
│   ├── klines.py            # Klines data fetcher
│   ├── trades.py            # Trades data fetcher
│   └── funding.py           # Funding rates fetcher
├── utils/                   # Utility modules
│   ├── logger.py            # Structured logging setup
│   ├── time_utils.py        # Time/date utilities
│   └── retry.py             # Retry and rate limiting
├── jobs/                    # CLI entry points
│   ├── extract_klines.py    # Manual klines extraction job
│   ├── extract_klines_production.py # 🆕 Production auto-extractor
│   ├── extract_klines_gap_filler.py # 🔧 Gap detection and filling job
│   ├── extract_trades.py    # Trades extraction job
│   └── extract_funding.py   # Funding rates extraction job
├── config/                  # 🆕 Configuration management
│   └── symbols.py           # Symbol configuration for production
├── k8s/                     # 🆕 Kubernetes manifests
│   ├── klines-all-timeframes-cronjobs.yaml
│   ├── klines-gap-filler-cronjob.yaml # 🔧 Daily gap filling job
│   ├── namespace.yaml
│   └── secrets-example.yaml
├── scripts/                 # 🆕 Utility scripts
│   ├── deploy-production.sh # Production deployment script
│   ├── validate-production.sh # Production validation
│   ├── deploy-local.sh      # Local development deployment
│   ├── build-multiarch.sh   # Multi-architecture Docker builds
│   ├── create-release.sh    # 🆕 Manual version and release management
│   └── encode_secrets.py    # Secret encoding for Kubernetes
├── Dockerfile               # Multi-stage container build
├── tests/                   # Comprehensive test suite
├── requirements.txt         # Runtime dependencies
└── requirements-dev.txt     # Development dependencies
```

## 🛠️ Installation

### Prerequisites
- Python 3.11+
- Docker (optional, for containerized deployment)
- Kubernetes cluster (optional, for production deployment)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/petrosa-binance-data-extractor.git
   cd petrosa-binance-data-extractor
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `BINANCE_API_KEY` | Binance API key | No | "" |
| `BINANCE_API_SECRET` | Binance API secret | No | "" |
| `DB_ADAPTER` | Database adapter type | No | "mysql" |
| `MYSQL_URI` | MySQL connection string | No | "mysql+pymysql://username:password@localhost:3306/binance_data" |
| `MONGODB_URI` | MongoDB connection string | No | "mongodb://localhost:27017/binance_data" |
| `POSTGRESQL_URI` | PostgreSQL connection string | No | "postgresql://user:password@localhost:5432/binance_data" |
| `LOG_LEVEL` | Logging level | No | "INFO" |
| `DEFAULT_PERIOD` | Default extraction interval | No | "15m" |
| `DB_BATCH_SIZE` | Database batch size | No | "1000" |

## 🚀 Usage

### 🎯 Unified Pipeline Runner (New!)

The `run_pipeline.py` script provides a unified interface to run all data extraction jobs with proper error handling, logging, and configuration management.

**Quick Start:**
```bash
# Run all jobs in sequence (dry-run mode)
python scripts/run_pipeline.py --all --dry-run

# Run specific job
python scripts/run_pipeline.py --job klines --period 15m --dry-run
python scripts/run_pipeline.py --job funding --dry-run
python scripts/run_pipeline.py --job trades --limit 1000 --dry-run
python scripts/run_pipeline.py --job gap-filler --period 1h --dry-run
```

**Available Commands:**
```bash
# Pipeline runner help
python scripts/run_pipeline.py --help

# Run with custom parameters
python scripts/run_pipeline.py --job klines \
  --period 15m \
  --symbols BTCUSDT ETHUSDT \
  --max-workers 5 \
  --db-adapter mysql \
  --log-level DEBUG

# Run all jobs with custom configuration
python scripts/run_pipeline.py --all \
  --symbols BTCUSDT ETHUSDT BNBUSDT \
  --db-adapter mysql \
  --log-level INFO \
  --dry-run
```

**Makefile Integration:**
```bash
# Test pipeline runner
make test-pipeline

# Run individual jobs via pipeline
make pipeline-klines
make pipeline-funding
make pipeline-trades
make pipeline-gap-filler

# Run all jobs via pipeline
make pipeline-all
```

### 🏭 Production Extractor (Recommended)

The production extractor automatically detects the last extraction timestamp and continues from there, making it perfect for Kubernetes CronJobs and automated deployments.

**Auto-Extract All Configured Symbols**
```bash
# Extract 15m klines for all production symbols
python -m jobs.extract_klines_production --period 15m

# Extract with custom symbols and parallel workers
python -m jobs.extract_klines_production \
  --period 1h \
  --symbols BTCUSDT,ETHUSDT,BNBUSDT \
  --max-workers 8

# Dry run to test configuration
python -m jobs.extract_klines_production \
  --period 15m \
  --dry-run
```

**Key Features:**
- ✅ **Zero Configuration**: No start/end dates needed
- ✅ **Gap Detection**: Automatically finds and fills missing data
- ✅ **Parallel Processing**: Configurable worker pools for multiple symbols
- ✅ **Financial Naming**: Creates tables with proper naming (klines_m15, klines_h1, etc.)
- ✅ **Production Ready**: Designed for Kubernetes CronJobs

### 🔧 Gap Detection and Filling

The gap filler job detects missing klines data and fills gaps with weekly request splitting to avoid Binance rate limiting.

**Daily Gap Filling (Recommended for Production)**
```bash
# Fill gaps for all configured symbols (15m period)
python -m jobs.extract_klines_gap_filler --period 15m

# Fill gaps with custom symbols and more workers
python -m jobs.extract_klines_gap_filler \
  --period 1h \
  --symbols BTCUSDT,ETHUSDT \
  --max-workers 5

# Fill gaps with custom weekly chunk size
python -m jobs.extract_klines_gap_filler \
  --period 15m \
  --weekly-chunk-days 5 \
  --max-gap-size-days 30
```

**Key Features:**
- ✅ **Weekly Request Splitting**: Splits large requests into weekly chunks to avoid rate limiting
- ✅ **Gap Detection**: Automatically finds missing data from start date in constants
- ✅ **Enhanced Retry Logic**: Exponential backoff with jitter for all operations
- ✅ **Comprehensive Error Handling**: Retries on connection, API, and network errors
- ✅ **Rate Limit Aware**: Built-in delays and limited parallel workers
- ✅ **Long Runtime Support**: Designed to run daily with 6+ hour runtime
- ✅ **Large Gap Filtering**: Skips gaps larger than configurable threshold
- ✅ **OpenTelemetry Instrumentation**: Automatic instrumentation using `opentelemetry-instrument`

**Retry Strategy:**
- **Data Fetching**: 7 retries with 3-300 second delays
- **Database Operations**: 5 retries with 2-180 second delays  
- **Gap Detection**: 5 retries with 2-120 second delays
- **Symbol Processing**: 5 retries with 3-240 second delays
- **API Rate Limits**: Additional 30-60 second delays
- **Connection Errors**: Exponential backoff with jitter

### 🔍 OpenTelemetry Instrumentation

The application uses automatic OpenTelemetry instrumentation for comprehensive observability:

**Automatic Instrumentation:**
- **HTTP Requests**: All API calls to Binance are automatically traced
- **Database Operations**: MySQL/MongoDB queries are instrumented
- **Log Correlation**: Logs are automatically correlated with traces
- **Metrics Collection**: Built-in metrics for monitoring

**Deployment Command:**
```bash
opentelemetry-instrument python -m jobs.extract_klines_gap_filler --period=15m
```

**Environment Variables:**
```bash
OTEL_SERVICE_NAME=binance-extractor
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_LOGS_EXPORTER=otlp
```

### 🛠️ Manual Extractor

For manual extractions with specific date ranges:

**Extract Klines (Candlestick Data)**
```bash
python jobs/extract_klines.py \
  --symbols BTCUSDT ETHUSDT \
  --interval 15m \
  --start-date "2024-01-01T00:00:00Z" \
  --end-date "2024-01-02T00:00:00Z" \
  --database mongodb \
  --db-uri "mongodb://localhost:27017/crypto"
```

**Extract Recent Trades**
```bash
python jobs/extract_trades.py \
  --symbols BTCUSDT \
  --limit 1000 \
  --database mongodb
```

**Extract Funding Rates**
```bash
python jobs/extract_funding.py \
  --symbols BTCUSDT ETHUSDT \
  --start-date "2024-01-01T00:00:00Z" \
  --database mongodb
```

### Python API

```python
from fetchers.klines import KlinesFetcher
from db.mongodb_adapter import MongoDBAdapter
from datetime import datetime, timezone

# Initialize components
fetcher = KlinesFetcher()
db_adapter = MongoDBAdapter("mongodb://localhost:27017/crypto")

# Fetch data
start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
end_time = datetime(2024, 1, 2, tzinfo=timezone.utc)

klines = fetcher.fetch_klines("BTCUSDT", "15m", start_time, end_time)

# Store in database
with db_adapter:
    db_adapter.write_batch(klines, "klines")
```

## 🐳 Docker Deployment

### Build and Run Locally

```bash
# Build the image
docker build -t binance-extractor .

# Run production extractor with MySQL
docker run --rm \
  -e BINANCE_API_KEY=$API_KEY \
  -e BINANCE_API_SECRET=$API_SECRET \
  -e DB_ADAPTER=mysql \
  -e MYSQL_URI=$MYSQL_URI \
  binance-extractor \
  python jobs/extract_klines_production.py --period 15m
```

### Docker Compose

```yaml
version: '3.8'
services:
  binance-extractor:
    build: .
    environment:
      - BINANCE_API_KEY=${BINANCE_API_KEY}
      - BINANCE_API_SECRET=${BINANCE_API_SECRET}
      - DB_ADAPTER=mongodb
      - MONGODB_URI=mongodb://mongo:27017/binance_data
    depends_on:
      - mongo
    
  mongo:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

volumes:
  mongo_data:
```

## ☸️ Kubernetes Deployment

### Production CronJobs

The project includes Kubernetes CronJob configurations for automated data extraction:

**Regular Klines Extraction (Every 5/15/30 minutes)**
```bash
# Deploy regular extraction jobs
kubectl apply -f k8s/klines-all-timeframes-cronjobs.yaml
```

**Daily Gap Filling (Every day at 2 AM UTC)**
```bash
# Deploy gap filling job
kubectl apply -f k8s/klines-gap-filler-cronjob.yaml
```

**Key Features:**
- ✅ **Automated Scheduling**: CronJobs run at optimal times
- ✅ **Resource Management**: Configurable CPU/memory limits
- ✅ **Long Runtime Support**: Gap filler has 6-hour timeout
- ✅ **Concurrency Control**: Prevents overlapping jobs
- ✅ **Telemetry Integration**: Full OpenTelemetry support

## ☸️ Kubernetes Production Deployment

### Quick Start (Recommended)

Deploy all timeframes (m5, m15, m30, h1, d1) with a single command:

```bash
# 1. Create required secrets
kubectl create secret generic binance-api-secret -n petrosa-apps \
  --from-literal=api-key=YOUR_API_KEY \
  --from-literal=api-secret=YOUR_API_SECRET

kubectl create secret generic database-secret -n petrosa-apps \
  --from-literal=mysql-uri="mysql://user:pass@host:3306/database"

# 2. Deploy all timeframes
./scripts/deploy-production.sh
```

### Automated CI/CD Deployment

The system includes a complete GitHub Actions pipeline that:
- Builds and pushes Docker images to Docker Hub
- Updates Kubernetes manifests with new image tags
- Deploys to your cluster automatically

**Setup:**
1. Configure GitHub secrets: `KUBE_CONFIG_DATA`, `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`
2. Push to main branch to trigger deployment
3. Monitor deployment in Actions tab

### Multi-Timeframe Production Schedule

The production deployment creates CronJobs for all major timeframes:

| Timeframe | Schedule | Workers | Resources | Description |
|-----------|----------|---------|-----------|-------------|
| **m5** | `*/5 * * * *` | 15 | 512Mi/1Gi RAM | Every 5 minutes |
| **m15** | `2 */15 * * *` | 12 | 384Mi/768Mi RAM | Every 15 min at :02 |
| **m30** | `5 */30 * * *` | 10 | 320Mi/640Mi RAM | Every 30 min at :05 |
| **h1** | `10 * * * *` | 8 | 256Mi/512Mi RAM | Every hour at :10 |
| **d1** | `15 0 * * *` | 6 | 256Mi/512Mi RAM | Daily at 00:15 UTC |

> **Note:** Schedules are staggered to prevent resource conflicts and API rate limiting.

### Production Features

- **🔄 Automatic Gap Filling**: Each job auto-detects last timestamp and continues extraction
- **⚡ Parallel Processing**: All 20+ symbols extracted simultaneously per timeframe
- **🛡️ Resource Optimized**: Memory and CPU limits tuned for each timeframe frequency
- **📊 Financial Naming**: Tables follow financial market conventions (klines_m5, klines_h1, etc.)
- **🔍 Full Observability**: Structured JSON logs with job correlation IDs
- **🚨 Production Hardened**: Security contexts, resource limits, and failure handling

### Manual Deployment (Advanced)

If you prefer manual deployment or need to customize the setup:

1. **Encode Secrets**
   ```bash
   # Use the provided script to encode your credentials
   python scripts/encode_secrets.py
   ```

2. **Create Secrets**
   ```bash
   # Apply the generated secrets (keep secure!)
   kubectl apply -f k8s/secrets-generated.yaml
   ```

3. **Deploy All Timeframes**
   ```bash
   # Deploy all timeframe extractors
   kubectl apply -f k8s/klines-all-timeframes-cronjobs.yaml
   ```

### Monitor Production Jobs

```bash
# Check CronJob status
kubectl get cronjobs -l app=binance-extractor

# View recent job logs
kubectl logs -l component=klines-extractor --tail=100

# Check job history
kubectl get jobs -l app=binance-extractor --sort-by=.metadata.creationTimestamp

# Get job metrics
kubectl describe cronjob binance-klines-m15-production
```

### Configuration

**Environment Variables in CronJob:**
- `BINANCE_API_KEY` / `BINANCE_API_SECRET`: From Kubernetes secrets
- `MYSQL_URI`: Database connection string
- `LOG_LEVEL`: `INFO` (production) / `DEBUG` (development)
- `ENVIRONMENT`: `production` (determines symbol list)

**Resource Limits:**
- Memory: 256Mi request, 512Mi limit
- CPU: 200m request, 500m limit
- Timeout: 10 minutes (15m), 15 minutes (1h), 30 minutes (1d)

## 🧪 Testing

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test categories
pytest tests/test_models.py -v
pytest tests/test_fetchers.py -v
pytest tests/test_db_adapters.py -v
```

### Test Categories

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **Mock Tests**: Test external API interactions with mocking

## 🔧 Configuration

### Environment Variables & .env File

The application supports loading configuration from a `.env` file for local development. Copy the example file and customize it:

```bash
cp .env.example .env
# Edit .env with your configuration
```

Example `.env` file:
```bash
# Binance API Credentials
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Database Configuration
DATABASE_TYPE=mongodb
DATABASE_URI=mongodb://localhost:27017/binance_data

# Extraction Settings
DEFAULT_PERIOD=15m
DEFAULT_START_DATE=2021-01-01T00:00:00Z

# Logging Configuration
LOG_LEVEL=INFO
```

### Central Configuration (`constants.py`)

All configuration is centralized in `constants.py` and loaded from environment variables:

```python
# API Configuration
BINANCE_API_URL = "https://fapi.binance.com"
API_RATE_LIMIT_PER_MINUTE = 1200

# Database Configuration  
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/binance")
MYSQL_URI = os.getenv("MYSQL_URI", "mysql+pymysql://user:pass@localhost:3306/binance")
POSTGRESQL_URI = os.getenv("POSTGRESQL_URI", "postgresql://user:pass@localhost:5432/binance")

# Extraction Parameters
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "SOLUSDT", "DOTUSDT", "AVAXUSDT", "MATICUSDT", "LINKUSDT"]  # Production has 20+ symbols
DEFAULT_PERIOD = "15m"
MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 2

# Logging and Observability
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENABLE_OTEL = bool(os.getenv("ENABLE_OTEL", "false"))
```

### Database Adapters

The system supports multiple databases through pluggable adapters:

- **MongoDB**: Full-featured adapter with aggregation support
- **MySQL**: SQL-based adapter with SQLAlchemy integration and robust retry logic for connection handling
- **PostgreSQL**: (Planned for future release - infrastructure ready, implementation pending)

## 📊 Data Models

### Kline (Candlestick) Data

```python
{
  "symbol": "BTCUSDT",
  "timestamp": "2024-01-01T00:00:00Z",
  "interval": "15m",
  "open_price": "43000.50",
  "high_price": "43250.75",
  "low_price": "42800.25", 
  "close_price": "43100.00",
  "volume": "1234.56789",
  "number_of_trades": 1500
}
```

### Trade Data

```python
{
  "symbol": "BTCUSDT", 
  "timestamp": "2024-01-01T00:00:00Z",
  "trade_id": 28457,
  "price": "43000.50",
  "quantity": "0.01000000",
  "is_buyer_maker": true
}
```

### Funding Rate Data

```python
{
  "symbol": "BTCUSDT",
  "timestamp": "2024-01-01T00:00:00Z", 
  "funding_rate": "0.00010000",
  "mark_price": "43000.50000000",
  "funding_interval_hours": 8
}
```

## 🔄 CI/CD Pipeline

The project includes a comprehensive GitHub Actions workflow (see `.github/workflows/ci-cd.yml` and `.github/workflows/deploy.yaml`):

### Pipeline Stages

1. **Lint & Format**: Code quality checks with flake8, black, mypy
2. **Test**: Comprehensive test suite with coverage reporting
3. **Security**: Security scanning with bandit and safety
4. **Build**: Multi-stage Docker image build
5. **Push**: Container registry publishing
6. **Deploy**: Kubernetes deployment (optional)

### Workflow Configuration

```yaml
name: Build and Deploy
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Run tests
        run: |
          pip install -r requirements-dev.txt
          pytest --cov=. --cov-report=xml
```

## 🔍 Monitoring and Observability

### Logging

The system uses structured JSON logging with:
- **Correlation IDs**: Track requests across components
- **Contextual Information**: Symbol, timerange, operation type
- **Performance Metrics**: Execution time, record counts
- **Error Details**: Stack traces, error codes

### OpenTelemetry Integration

- **Traces**: End-to-end request tracing
- **Metrics**: Custom business metrics (extraction rates, error rates)
- **Resource Attributes**: Service metadata and environment info

### Health Checks

```bash
# Check service health
curl http://localhost:8080/health

# Check readiness  
curl http://localhost:8080/ready
```

## 🔒 Security

### Security Features

- **Non-root Containers**: All containers run as non-root user
- **Secret Management**: Kubernetes secrets for sensitive data
- **RBAC**: Role-based access control for Kubernetes resources
- **Dependency Scanning**: Automated vulnerability scanning
- **Code Security**: Static analysis with bandit

### Best Practices

- API keys stored in Kubernetes secrets
- Minimal container privileges
- Regular dependency updates
- Security scanning in CI/CD

## 🤝 Contributing

### Development Workflow

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** changes: `git commit -m 'Add amazing feature'`
4. **Push** to branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### Code Standards

- **Python**: Follow PEP 8, use type hints (some style improvements needed)
- **Testing**: Minimum 80% code coverage
- **Documentation**: Docstrings for all public methods
- **Commits**: Use conventional commit messages

> **Note**: Code style improvements (line length, import organization) are planned for upcoming releases.

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Manual run
pre-commit run --all-files
```

## 📝 Documentation

### Production Guides
- **[Production Readiness Checklist](docs/PRODUCTION_READINESS.md)** - Complete pre-deployment validation
- **[Operations Guide](docs/OPERATIONS_GUIDE.md)** - Day-to-day operations, monitoring, and troubleshooting
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Step-by-step deployment instructions
- **[Production Summary](docs/PRODUCTION_SUMMARY.md)** - Architecture overview and system design

### Setup Guides
- **[Docker Hub Integration](docs/DOCKERHUB_SETUP.md)** - Docker Hub CI/CD setup and configuration
- **[Local Deployment](docs/LOCAL_DEPLOY.md)** - Local development and testing setup
- **[Namespace Configuration](docs/NAMESPACE_UPDATE.md)** - Kubernetes namespace setup and migration

### Post-Deployment
- **[Deployment Complete Guide](docs/DEPLOYMENT_COMPLETE.md)** - Post-deployment summary and next steps

### Quick References
- **Production Deployment**: `./scripts/deploy-production.sh`
- **Monitor Jobs**: `kubectl get cronjobs -l app=binance-extractor -n petrosa-apps`
- **View Logs**: `kubectl logs -l component=klines-extractor -n petrosa-apps --tail=100`
- **Manual Job**: `kubectl create job manual-extraction-$(date +%s) -n petrosa-apps --from=job/binance-klines-manual`

## 🏗️ Architecture

### Production System Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GitHub Actions │    │   Kubernetes     │    │   MySQL         │
│   ├─ CI/CD      │───▶│   ├─ CronJobs    │───▶│   ├─ klines_m5  │
│   ├─ Build      │    │   ├─ Secrets     │    │   ├─ klines_m15 │
│   └─ Deploy     │    │   └─ ConfigMaps  │    │   ├─ klines_m30 │
└─────────────────┘    └──────────────────┘    │   ├─ klines_h1  │
                                               │   └─ klines_d1  │
┌─────────────────┐    ┌──────────────────┐    └─────────────────┘
│   Binance API   │    │   Extractor      │
│   ├─ Klines     │◀───│   ├─ Parallel    │
│   ├─ Rate Limit │    │   ├─ Retry       │
│   └─ Futures    │    │   └─ Gap Fill    │
└─────────────────┘    └──────────────────┘
```

### Key Components

- **Production Extractor**: Auto-detection, gap-filling, parallel processing
- **Multi-Timeframe CronJobs**: Optimized schedules for m5, m15, m30, h1, d1
- **Database Adapters**: Pluggable backends (MySQL, MongoDB, PostgreSQL)
- **Symbol Management**: Environment-based configuration (20+ production symbols)
- **CI/CD Pipeline**: Automated testing, building, and deployment

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

### Getting Help

- **Documentation**: Check this README and the production guides above
- **Issues**: [GitHub Issues](https://github.com/your-org/petrosa-binance-data-extractor/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/petrosa-binance-data-extractor/discussions)

### Reporting Issues

When reporting issues, please include:
- Python version and environment details
- Full error messages and stack traces  
- Steps to reproduce the issue
- Expected vs actual behavior
- Kubernetes/deployment context if applicable

## 🗺️ Roadmap

### Recent Achievements ✅

- **Multi-Timeframe Production System**: Complete m5-d1 coverage
- **Kubernetes-Native Architecture**: Production-ready CronJobs
- **Automated CI/CD**: GitHub Actions deployment pipeline
- **Production Operations**: Comprehensive monitoring and maintenance guides
- **Financial Market Standards**: Proper table naming and industry conventions

### Upcoming Features

- [ ] **Real-time Streaming**: WebSocket-based live data feeds
- [ ] **Advanced Monitoring**: Prometheus/Grafana integration
- [ ] **Data Analytics**: Built-in analysis and reporting tools
- [ ] **Multi-Exchange Support**: Coinbase, Kraken, OKX adapters
- [ ] **Performance Optimization**: Advanced caching and partitioning
- [ ] **Web Dashboard**: Real-time monitoring and control interface

### Version History

- **v1.0.0**: Initial release with core functionality
- **v1.1.0**: Enhanced observability and monitoring
- **v1.2.0**: Kubernetes native deployment
- **v2.0.0**: Production multi-timeframe system (current)
- **v2.1.0**: (Planned) Real-time streaming support

---

**🚀 Production-ready crypto data extraction at enterprise scale**

## OpenTelemetry Configuration

### Initialization Strategy

The application supports two OpenTelemetry initialization modes to prevent double initialization conflicts:

1. **Manual Initialization** (for local development/testing):
   - OpenTelemetry is initialized in-code via `setup_telemetry()`
   - Used when running jobs directly with `python -m jobs.extract_klines`

2. **Automatic Initialization** (for production/Kubernetes):
   - Uses `opentelemetry-instrument` wrapper
   - In-code initialization is disabled via `OTEL_NO_AUTO_INIT=1`
   - Prevents "I/O operation on closed file" errors

### Environment Variables

- `OTEL_NO_AUTO_INIT`: Set to "1" to disable in-code OpenTelemetry initialization
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP endpoint for remote tracing
- `OTEL_SERVICE_NAME`: Service name for traces
- `OTEL_RESOURCE_ATTRIBUTES`: Additional resource attributes

### Usage

**Local Development:**
```bash
python -m jobs.extract_klines --symbols BTCUSDT --period 1m
```

**Production/Kubernetes:**
```bash
opentelemetry-instrument python -m jobs.extract_klines --symbols BTCUSDT --period 1m
```

## Gap Filler Job