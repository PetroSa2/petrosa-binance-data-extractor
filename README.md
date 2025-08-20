# Petrosa Socket Client

A high-performance Binance WebSocket client for real-time data streaming, designed to forward messages to NATS for consumption by other services in the Petrosa ecosystem.

## 🚀 Features

- **Real-time Data Streaming**: Connect to Binance WebSocket API for live market data
- **Multiple Stream Support**: Subscribe to trades, tickers, order book depth, and more
- **NATS Integration**: Forward messages to NATS with structured message format
- **Circuit Breaker Pattern**: Robust error handling and automatic reconnection
- **Resource Management**: Memory limits, backpressure handling, and message TTL
- **Health Checks**: Kubernetes-ready health endpoints for monitoring
- **OpenTelemetry**: Full observability with traces, metrics, and logs
- **Production Ready**: Docker containerization and Kubernetes deployment

## 📋 Requirements

- **Python 3.11+**: Required for development and runtime
- **Docker**: Required for containerization and local testing
- **kubectl**: Required for Kubernetes deployment (remote cluster)
- **Make**: Required for using the Makefile commands

## 🛠️ Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/petrosa/petrosa-socket-client.git
cd petrosa-socket-client

# Complete setup
make setup

# Run locally
make run-local

# Run tests
make test

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
| `BINANCE_WS_URL` | `wss://stream.binance.com:9443` | Binance WebSocket URL |
| `BINANCE_STREAMS` | `btcusdt@trade,btcusdt@ticker,btcusdt@depth20@100ms,ethusdt@trade,ethusdt@ticker,ethusdt@depth20@100ms` | Comma-separated list of streams |
| `NATS_URL` | `nats://localhost:4222` | NATS server URL |
| `NATS_TOPIC` | `binance.websocket.data` | NATS topic for publishing messages |
| `LOG_LEVEL` | `INFO` | Logging level |
| `WEBSOCKET_RECONNECT_DELAY` | `5` | Reconnection delay in seconds |
| `WEBSOCKET_MAX_RECONNECT_ATTEMPTS` | `10` | Maximum reconnection attempts |
| `MESSAGE_TTL_SECONDS` | `60` | Message TTL in seconds |
| `MAX_MEMORY_MB` | `500` | Maximum memory usage in MB |

### Supported Streams

The service supports all Binance WebSocket streams:

- **Trade Streams**: `{symbol}@trade`
- **Ticker Streams**: `{symbol}@ticker`
- **Depth Streams**: `{symbol}@depth{levels}@{speed}`
- **Kline Streams**: `{symbol}@kline_{interval}`
- **Mini Ticker**: `{symbol}@miniTicker`
- **24hr Ticker**: `{symbol}@ticker_24hr`

### Message Format

Messages are published to NATS in the following format:

```json
{
  "stream": "btcusdt@trade",
  "data": {
    "e": "trade",
    "E": 123456789,
    "s": "BTCUSDT",
    "t": 12345,
    "p": "0.001",
    "q": "100",
    "b": 88,
    "a": 50,
    "T": 123456785,
    "m": true,
    "M": true
  },
  "timestamp": "2024-01-01T00:00:00.000Z",
  "message_id": "uuid-here",
  "source": "binance-websocket",
  "version": "1.0"
}
```

## 🏗️ Architecture

### Components

1. **WebSocket Client**: Connects to Binance WebSocket API
2. **Message Processor**: Validates and processes incoming messages
3. **NATS Publisher**: Forwards messages to NATS
4. **Health Server**: HTTP endpoints for Kubernetes probes
5. **Circuit Breaker**: Handles connection failures gracefully

### Data Flow

```
Binance WebSocket → Message Queue → Message Processor → NATS → Consumers
```

### Resource Management

- **Memory Limits**: Configurable memory usage limits
- **Message TTL**: Automatic message expiration
- **Backpressure Handling**: Drop messages when queue is full
- **Connection Pooling**: Efficient NATS connection management

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

- Message models: 100%
- WebSocket client: 95%
- Health server: 90%
- Circuit breaker: 85%

## 🐳 Docker

### Multi-stage Build

The Dockerfile uses multi-stage builds for optimized production images:

- **Builder Stage**: Install dependencies and build
- **Production Stage**: Minimal runtime image
- **Development Stage**: Includes development tools
- **Testing Stage**: Includes test dependencies

### Image Variants

- `petrosa-socket-client:latest` - Production image
- `petrosa-socket-client:alpine` - Lightweight Alpine image
- `petrosa-socket-client:dev` - Development image

## ☸️ Kubernetes

### Deployment

The service is deployed to Kubernetes with:

- **3 Replicas**: High availability
- **Health Checks**: Liveness and readiness probes
- **Auto-scaling**: HPA based on CPU and memory
- **Resource Limits**: Memory and CPU constraints
- **Security**: Non-root user and read-only filesystem

### Monitoring

- **Prometheus Metrics**: Available at `/metrics`
- **Health Checks**: Available at `/healthz` and `/ready`
- **OpenTelemetry**: Distributed tracing and metrics

### Configuration

Configuration is managed via Kubernetes ConfigMaps and Secrets:

- **ConfigMap**: `petrosa-socket-client-config`
- **Secrets**: Uses existing `petrosa-sensitive-credentials`

## 📊 Monitoring

### Health Endpoints

- `GET /healthz` - Liveness probe
- `GET /ready` - Readiness probe
- `GET /metrics` - Prometheus metrics
- `GET /` - Service information

### Metrics

The service exposes the following metrics:

- **WebSocket Metrics**: Connection status, reconnect attempts
- **Message Metrics**: Processed/dropped message counts
- **Performance Metrics**: Memory usage, CPU usage
- **NATS Metrics**: Connection status, publish success rate

### Logging

Structured JSON logging with configurable levels:

```json
{
  "timestamp": "2024-01-01T00:00:00.000Z",
  "level": "INFO",
  "logger": "socket_client.core.client",
  "message": "Connected to Binance WebSocket",
  "streams": ["btcusdt@trade"],
  "url": "wss://stream.binance.com:9443"
}
```

## 🔧 Development

### Project Structure

```
petrosa-socket-client/
├── socket_client/           # Main application code
│   ├── core/               # Core WebSocket client
│   ├── models/             # Data models
│   ├── utils/              # Utilities
│   └── health/             # Health check server
├── tests/                  # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── e2e/               # End-to-end tests
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

#### WebSocket Connection Issues

```bash
# Check WebSocket connectivity
python -c "import websockets; print('WebSocket library available')"

# Test NATS connection
python -c "import nats; print('NATS library available')"

# Check environment variables
env | grep -E "(BINANCE|NATS|LOG)"
```

#### Kubernetes Issues

```bash
# Check pod status
kubectl --kubeconfig=k8s/kubeconfig.yaml get pods -n petrosa-apps -l app=socket-client

# View logs
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -n petrosa-apps -l app=socket-client

# Check health endpoint
curl http://localhost:8080/healthz
```

#### Performance Issues

- Check memory usage: `docker stats` or Kubernetes metrics
- Monitor message queue size in logs
- Verify NATS connection status
- Check WebSocket reconnection attempts

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
make run-local
```

## 📚 API Reference

### WebSocket Client

```python
from socket_client.core.client import BinanceWebSocketClient

client = BinanceWebSocketClient(
    ws_url="wss://stream.binance.com:9443",
    streams=["btcusdt@trade"],
    nats_url="nats://localhost:4222",
    nats_topic="binance.websocket.data"
)

await client.start()
# ... client running ...
await client.stop()
```

### Message Models

```python
from socket_client.models.message import create_message, TradeMessage

# Create trade message
message = TradeMessage(
    stream="btcusdt@trade",
    data={"e": "trade", "s": "BTCUSDT", "p": "50000"}
)

# Convert to NATS format
nats_message = message.to_nats_message()
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support

For support and questions:

- **Issues**: [GitHub Issues](https://github.com/petrosa/petrosa-socket-client/issues)
- **Documentation**: [Project Wiki](https://github.com/petrosa/petrosa-socket-client/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/petrosa/petrosa-socket-client/discussions)

## 🔗 Related Projects

- [Petrosa TA Bot](https://github.com/petrosa/petrosa-bot-ta-analysis) - Technical analysis bot
- [Petrosa Trade Engine](https://github.com/petrosa/petrosa-tradeengine) - Trading engine
- [Petrosa Data Extractor](https://github.com/petrosa/petrosa-binance-data-extractor) - Historical data extraction
