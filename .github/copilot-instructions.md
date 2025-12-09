# GitHub Copilot Instructions - Binance Data Extractor

## Service Context

**Purpose**: Batch data ingestion service that extracts historical cryptocurrency market data from Binance REST API.

**Deployment**: Kubernetes CronJobs running on schedules (1m, 5m, 15m, 1h, 4h, 1d)

**Role in Ecosystem**: Primary historical data ingestion layer → MySQL storage → TA Bot consumption

---

## Architecture

**Data Flow**:
```
Binance REST API → Data Extractor CronJobs → MySQL (klines, funding rates, trades)
                                              ↓
                                          TA Bot (historical analysis)
```

**Key Components**:
- `jobs/` - CronJob implementations (kline_job, funding_rate_job, trade_job, gap_filler)
- `fetchers/` - Binance API clients with rate limiting
- `db/` - MySQL connection and models
- `k8s/cronjobs.yaml` - CronJob definitions

---

## Service-Specific Patterns

### CronJob Schedules

**ALWAYS offset schedules** to avoid hour-mark collisions:

```yaml
# ✅ GOOD - Offset schedules
schedule: "2 * * * *"    # 1h candles at :02
schedule: "5 */4 * * *"  # 4h candles at :05

# ❌ BAD - Exact hour marks
schedule: "0 * * * *"    # Collision risk
```

### Idempotency

**ALL jobs MUST be idempotent** - safe to run multiple times:

```python
# ✅ GOOD - Upsert pattern
INSERT INTO klines (...) VALUES (...)
ON DUPLICATE KEY UPDATE close = VALUES(close), ...

# ❌ BAD - Duplicate risk
INSERT INTO klines (...) VALUES (...)
```

### Binance API Rate Limiting

```python
WEIGHT_LIMIT_PER_MINUTE = 1200
MAX_REQUEST_WEIGHT = 1000

# ✅ Implement exponential backoff
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=60))
def fetch_klines(...):
    pass
```

---

## Testing Patterns

```python
# Mock Binance API responses
@pytest.fixture
def mock_binance_api():
    with patch('requests.get') as mock:
        mock.return_value.json.return_value = SAMPLE_KLINE_DATA
        yield mock

# Test gap detection
def test_detect_gaps():
    gaps = detect_gaps("BTCUSDT", "1h")
    assert len(gaps) > 0
```

---

## Common Issues

**Gap Detection**: Check for missing candles
**Rate Limiting**: 429 responses from Binance
**MySQL Timeouts**: Use connection pooling

---

**Master Rules**: See `.cursorrules` in `petrosa_k8s` repo
**Service Rules**: `.cursorrules` in this repo
