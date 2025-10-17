# Petrosa Binance Data Extractor

**Historical cryptocurrency data extraction system with gap detection and multi-database support**

A production-ready batch processing system that extracts, validates, and stores historical market data from Binance. Supports klines (candlesticks), funding rates, and trades data with automatic gap detection and filling capabilities.

---

## 🌐 PETROSA ECOSYSTEM OVERVIEW

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PETROSA TRADING ECOSYSTEM                            │
│                                                                              │
│  ┌────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    │
│  │                │    │                  │    │                     │    │
│  │  Binance API   │───▶│  Data Extractor  │───▶│   MySQL Database    │    │
│  │  (Historical)  │    │  (THIS SERVICE)  │    │   (Klines, Rates)   │    │
│  │                │    │                  │    │                     │    │
│  └────────────────┘    └──────────────────┘    └─────────────────────┘    │
│                                                            │                 │
│  ┌────────────────┐    ┌──────────────────┐              │                 │
│  │                │    │                  │              ▼                 │
│  │  Binance WS    │───▶│  Socket Client   │──┐    ┌─────────────────┐    │
│  │  (Real-time)   │    │  (WebSocket)     │  │    │                 │    │
│  │                │    │                  │  │    │   TA Bot        │    │
│  └────────────────┘    └──────────────────┘  │    │   (28 Strategies│◀───┤
│                                │              │    │    Analysis)    │    │
│                                │              │    │                 │    │
│                                │ NATS         │    └─────────────────┘    │
│                         binance.websocket.data│             │              │
│                                │              │    signals.trading         │
│                                │              │             │              │
│                                ▼              │             ▼              │
│                         ┌──────────────────┐  │    ┌─────────────────┐    │
│                         │                  │  │    │                 │    │
│                         │  Realtime        │──┘    │  Trade Engine   │    │
│                         │  Strategies      │──────▶│  (Order Exec)   │    │
│                         │  (Live Analysis) │       │                 │    │
│                         │                  │       └─────────────────┘    │
│                         └──────────────────┘                               │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                    Kubernetes (MicroK8s Cluster)                    │    │
│  │  Namespace: petrosa-apps  │  Database: MySQL/MongoDB               │    │
│  │  Secrets: petrosa-sensitive-credentials                             │    │
│  │  CronJobs: Scheduled data extraction (15m, 1h intervals)           │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Services in the Ecosystem

| Service | Purpose | Input | Output | Status |
|---------|---------|-------|--------|--------|
| **petrosa-socket-client** | Real-time WebSocket data ingestion | Binance WebSocket API | NATS: `binance.websocket.data` | Real-time Processing |
| **petrosa-binance-data-extractor** | Historical data extraction & gap filling | Binance REST API | MySQL (klines, funding rates, trades) | **YOU ARE HERE** |
| **petrosa-bot-ta-analysis** | Technical analysis (28 strategies) | MySQL klines data | NATS: `signals.trading` | Signal Generation |
| **petrosa-realtime-strategies** | Real-time signal generation | NATS: `binance.websocket.data` | NATS: `signals.trading` | Live Processing |
| **petrosa-tradeengine** | Order execution & trade management | NATS: `signals.trading` | Binance Orders API, MongoDB audit | Order Execution |
| **petrosa_k8s** | Centralized infrastructure | Kubernetes manifests | Cluster resources | Infrastructure |

### Data Flow Pipeline

```
┌─────────────┐
│   Binance   │
│   REST API  │
│             │
│ • Klines    │
│ • Funding   │
│ • Trades    │
└──────┬──────┘
       │ https://api.binance.com
       │ https://fapi.binance.com
       ▼
┌──────────────────────┐
│  Data Extractor      │ ◄── THIS SERVICE
│  (Batch Jobs)        │
│                      │
│ • Extract historical │
│ • Detect gaps        │
│ • Fill missing data  │
│ • Validate records   │
│ • Parallel processing│
└──────┬───────────────┘
       │ MySQL INSERT (batch 2000 records)
       │
       ▼
┌──────────────────────────────────────┐
│       MySQL Database                  │
│                                      │
│  Tables:                             │
│  • symbol_klines_15m                 │
│  • symbol_klines_1h                  │
│  • symbol_klines_1d                  │
│  • symbol_funding_rates              │
│  • symbol_trades                     │
│                                      │
│  Indexes:                            │
│  • (symbol, open_time) UNIQUE        │
│  • (symbol, timestamp)               │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────┐
│  TA Bot              │
│  (Signal Generator)  │
│                      │
│ • Read klines        │
│ • Calculate          │
│   indicators         │
│ • Generate signals   │
└──────────────────────┘
```

### Transport Layer

#### Binance REST API (Primary Data Source)

**Endpoints Used:**

| Endpoint | Purpose | Rate Limit | Data Type |
|----------|---------|------------|-----------|
| `GET /api/v3/klines` | Historical klines (spot) | 1200/min | OHLCV candlesticks |
| `GET /fapi/v1/klines` | Historical klines (futures) | 1200/min | OHLCV candlesticks |
| `GET /fapi/v1/fundingRate` | Funding rate history | 1200/min | Funding rates |
| `GET /api/v3/aggTrades` | Aggregated trades | 1200/min | Trade data |

**Request Format (Klines):**
```http
GET https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=15m&startTime=1640995200000&endTime=1641081600000&limit=1000
```

**Response Format:**
```json
[
  [
    1640995200000,      // Open time
    "46222.1",          // Open price
    "46425.0",          // High price
    "46150.2",          // Low price
    "46380.5",          // Close price
    "1234.567",         // Volume
    1641081599999,      // Close time
    "57123456.789",     // Quote asset volume
    12345,              // Number of trades
    "617.283",          // Taker buy base volume
    "28561728.394",     // Taker buy quote volume
    "0"                 // Ignore
  ]
]
```

#### Database Storage

**Supported Databases:**
- **MySQL** (Primary) - Production use
- **MongoDB** - Alternative storage
- **PostgreSQL** - Future support

**Connection Patterns:**
```python
# MySQL (via SQLAlchemy)
mysql+pymysql://user:password@host:3306/database

# MongoDB (via Motor)
mongodb://user:password@host:27017/database
```

### Shared Data Contracts

#### Kline Model (OHLCV Data)

Defined in `models/kline.py`:

```python
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal

class KlineModel(BaseModel):
    """Candlestick (OHLCV) data model."""

    # Identification
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    interval: str = Field(..., description="Time interval (e.g., 15m, 1h)")

    # Timing
    open_time: datetime = Field(..., description="Kline open time")
    close_time: datetime = Field(..., description="Kline close time")

    # OHLCV
    open_price: Decimal = Field(..., description="Open price")
    high_price: Decimal = Field(..., description="High price")
    low_price: Decimal = Field(..., description="Low price")
    close_price: Decimal = Field(..., description="Close price")
    volume: Decimal = Field(..., description="Base asset volume")

    # Additional fields
    quote_asset_volume: Decimal
    number_of_trades: int
    taker_buy_base_asset_volume: Decimal
    taker_buy_quote_asset_volume: Decimal

    # Derived fields
    price_change: Decimal | None = None
    price_change_percent: Decimal | None = None

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }
```

**Database Schema (MySQL):**
```sql
CREATE TABLE symbol_klines_15m (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    open_time DATETIME(3) NOT NULL,
    close_time DATETIME(3) NOT NULL,
    open_price DECIMAL(20, 8) NOT NULL,
    high_price DECIMAL(20, 8) NOT NULL,
    low_price DECIMAL(20, 8) NOT NULL,
    close_price DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    quote_asset_volume DECIMAL(20, 8) NOT NULL,
    number_of_trades INT NOT NULL,
    taker_buy_base_asset_volume DECIMAL(20, 8) NOT NULL,
    taker_buy_quote_asset_volume DECIMAL(20, 8) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_symbol_time (symbol, open_time),
    KEY idx_symbol (symbol),
    KEY idx_open_time (open_time),
    KEY idx_symbol_time (symbol, open_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### Funding Rate Model

Defined in `models/funding_rate.py`:

```python
class FundingRateModel(BaseModel):
    """Futures funding rate model."""

    symbol: str
    funding_time: datetime
    funding_rate: Decimal
    mark_price: Decimal | None = None

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }
```

#### Trade Model

Defined in `models/trade.py`:

```python
class TradeModel(BaseModel):
    """Individual trade model."""

    symbol: str
    trade_id: int
    price: Decimal
    quantity: Decimal
    quote_quantity: Decimal
    time: datetime
    is_buyer_maker: bool
```

### Integration Patterns

#### Gap Detection Algorithm

**How It Works:**
1. Query last record timestamp from database
2. Calculate expected records from last timestamp to now
3. Query actual records in time range
4. Identify missing periods
5. Schedule extraction jobs for gaps

**Code Example:**
```python
def detect_gaps(symbol: str, interval: str, adapter) -> List[Tuple[datetime, datetime]]:
    """Detect missing data gaps."""
    # Get last record
    last_time = adapter.get_last_kline_time(symbol, interval)
    current_time = datetime.utcnow()

    # Calculate expected klines
    interval_ms = interval_to_milliseconds(interval)
    expected_count = (current_time - last_time).total_seconds() * 1000 / interval_ms

    # Query actual records
    actual_records = adapter.get_klines_in_range(symbol, interval, last_time, current_time)

    # Find gaps
    gaps = []
    for i in range(len(actual_records) - 1):
        expected_next = actual_records[i].open_time + timedelta(milliseconds=interval_ms)
        actual_next = actual_records[i + 1].open_time

        if actual_next > expected_next:
            gaps.append((expected_next, actual_next))

    return gaps
```

#### Batch Processing Pattern

**Processing Flow:**
```python
def process_batch(klines: List[KlineModel], adapter, batch_size: int = 2000):
    """Process klines in batches."""
    for i in range(0, len(klines), batch_size):
        batch = klines[i:i + batch_size]

        try:
            # Validate batch
            validated = [kline for kline in batch if validate_kline(kline)]

            # Insert batch
            adapter.insert_klines(validated)

            # Log progress
            logger.info(f"Inserted batch {i}/{len(klines)}")

        except Exception as e:
            logger.error(f"Batch failed: {e}")
            # Retry individual records
            for kline in batch:
                try:
                    adapter.insert_kline(kline)
                except Exception:
                    continue
```

#### Parallel Extraction

**ThreadPoolExecutor Pattern:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def extract_multiple_symbols(symbols: List[str], interval: str):
    """Extract data for multiple symbols in parallel."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(extract_symbol, symbol, interval): symbol
            for symbol in symbols
        }

        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result = future.result()
                logger.info(f"{symbol}: {result['records']} records extracted")
            except Exception as e:
                logger.error(f"{symbol}: Extraction failed: {e}")
```

### Deployment Architecture

**Kubernetes CronJobs:**

```yaml
# Extract 15-minute klines every 15 minutes
apiVersion: batch/v1
kind: CronJob
metadata:
  name: extract-klines-15m
  namespace: petrosa-apps
spec:
  schedule: "*/15 * * * *"  # Every 15 minutes
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: extractor
            image: yurisa2/petrosa-binance-data-extractor:VERSION_PLACEHOLDER
            command:
            - python
            - -m
            - jobs.extract_klines_production
            - --period
            - 15m
            env:
            - name: DB_ADAPTER
              value: "mysql"
            - name: MYSQL_URI
              valueFrom:
                secretKeyRef:
                  name: petrosa-sensitive-credentials
                  key: MYSQL_URI
          restartPolicy: OnFailure
```

**Job Scheduling:**

| Job | Schedule | Purpose | Symbols |
|-----|----------|---------|---------|
| `extract-klines-15m` | `*/15 * * * *` | Extract 15-minute klines | ALL |
| `extract-klines-1h` | `0 * * * *` | Extract 1-hour klines | ALL |
| `extract-klines-1d` | `0 0 * * *` | Extract daily klines | ALL |
| `extract-funding` | `0 */8 * * *` | Extract funding rates | FUTURES ONLY |
| `gap-filler` | `0 2 * * *` | Fill detected gaps | ALL |

---

## 🔧 DATA EXTRACTOR - DETAILED DOCUMENTATION

### Service Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                   Data Extractor Architecture                       │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │                    Extraction Jobs                        │     │
│  │                                                            │     │
│  │  • extract_klines_production.py                          │     │
│  │  • extract_klines_gap_filler.py                          │     │
│  │  • extract_funding.py                                    │     │
│  │  • extract_trades.py                                     │     │
│  └──────┬───────────────────────────────────────────────────┘     │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │                    Fetchers Layer                         │     │
│  │                                                            │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │     │
│  │  │   Binance   │  │   Klines    │  │  Funding    │     │     │
│  │  │   Client    │─▶│   Fetcher   │  │   Fetcher   │     │     │
│  │  │   (Base)    │  └─────────────┘  └─────────────┘     │     │
│  │  └─────────────┘                                         │     │
│  │       │                                                   │     │
│  │       │ • Rate limiting (1200/min)                       │     │
│  │       │ • Retry with backoff                             │     │
│  │       │ • Error handling                                 │     │
│  └───────┼──────────────────────────────────────────────────┘     │
│          │                                                           │
│          ▼                                                           │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │                   Data Models                             │     │
│  │                                                            │     │
│  │  • KlineModel (Pydantic validation)                      │     │
│  │  • FundingRateModel                                      │     │
│  │  • TradeModel                                            │     │
│  │  • Data validation & transformation                      │     │
│  └──────┬───────────────────────────────────────────────────┘     │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │                  Database Adapters                        │     │
│  │                                                            │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │     │
│  │  │   MySQL     │  │  MongoDB    │  │ PostgreSQL  │     │     │
│  │  │   Adapter   │  │  Adapter    │  │  Adapter    │     │     │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │     │
│  │                                                            │     │
│  │  • Batch inserts (2000 records)                          │     │
│  │  • Conflict resolution (ON DUPLICATE KEY UPDATE)         │     │
│  │  • Connection pooling                                    │     │
│  │  • Transaction management                                │     │
│  └──────┬───────────────────────────────────────────────────┘     │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │                    Databases                              │     │
│  │                                                            │     │
│  │  MySQL Tables:                                           │     │
│  │  • btcusdt_klines_15m                                    │     │
│  │  • ethusdt_klines_15m                                    │     │
│  │  • btcusdt_klines_1h                                     │     │
│  │  • btcusdt_funding_rates                                 │     │
│  └──────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Production Klines Extractor (`jobs/extract_klines_production.py`)

**Automatic Incremental Extraction:**

```python
#!/usr/bin/env python3
"""
Production-ready klines extraction job.

Features:
- Reads last timestamp from database
- Automatically downloads missing data
- Handles gaps and failures
- Parallel processing for multiple symbols
- Incremental updates without manual date configuration
"""

def extract_symbol_production(
    symbol: str,
    period: str,
    adapter: BaseAdapter,
    fetcher: KlinesFetcher,
    lookback_hours: int = 24
) -> dict:
    """
    Extract klines for a symbol with automatic gap detection.

    Args:
        symbol: Trading symbol (e.g., BTCUSDT)
        period: Time interval (e.g., 15m, 1h)
        adapter: Database adapter
        fetcher: Klines fetcher
        lookback_hours: Hours to look back if no data exists

    Returns:
        Dict with extraction statistics
    """
    # Get last extraction time from database
    last_time = adapter.get_last_kline_time(symbol, period)

    if last_time is None:
        # No data exists, start from lookback period
        start_time = get_current_utc_time() - timedelta(hours=lookback_hours)
        logger.info(f"{symbol}: No existing data, starting from {start_time}")
    else:
        # Continue from last record
        start_time = last_time + get_interval_timedelta(period)
        logger.info(f"{symbol}: Last record at {last_time}, continuing from {start_time}")

    end_time = get_current_utc_time()

    # Fetch klines from Binance
    logger.info(f"{symbol}: Fetching klines from {start_time} to {end_time}")
    klines = fetcher.fetch_klines(
        symbol=symbol,
        interval=period,
        start_time=start_time,
        end_time=end_time
    )

    if not klines:
        logger.info(f"{symbol}: No new klines to insert")
        return {"symbol": symbol, "records": 0}

    # Insert in batches
    batch_size = constants.DB_BATCH_SIZE
    total_inserted = 0

    for i in range(0, len(klines), batch_size):
        batch = klines[i:i + batch_size]
        try:
            adapter.insert_klines(batch)
            total_inserted += len(batch)
            logger.info(f"{symbol}: Inserted batch {i}/{len(klines)}")
        except Exception as e:
            logger.error(f"{symbol}: Batch insert failed: {e}")
            # Retry individual records
            for kline in batch:
                try:
                    adapter.insert_kline(kline)
                    total_inserted += 1
                except Exception:
                    continue

    logger.info(f"{symbol}: Extraction complete. Inserted {total_inserted} records")
    return {"symbol": symbol, "records": total_inserted}

def main():
    """Main extraction orchestrator."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", required=True, choices=constants.SUPPORTED_INTERVALS)
    parser.add_argument("--symbols", default=",".join(constants.DEFAULT_SYMBOLS))
    parser.add_argument("--parallel", type=int, default=constants.MAX_WORKERS)
    args = parser.parse_args()

    symbols = args.symbols.split(",")

    # Initialize database adapter
    adapter = get_adapter(constants.DB_ADAPTER, constants.MYSQL_URI)

    # Initialize fetcher
    fetcher = KlinesFetcher(
        api_url=constants.BINANCE_FUTURES_API_URL,
        api_key=constants.API_KEY,
        api_secret=constants.API_SECRET
    )

    # Extract in parallel
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {
            executor.submit(
                extract_symbol_production,
                symbol,
                args.period,
                adapter,
                fetcher
            ): symbol
            for symbol in symbols
        }

        results = []
        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    # Summary
    total_records = sum(r["records"] for r in results)
    logger.info(f"EXTRACTION COMPLETE: {total_records} total records")

if __name__ == "__main__":
    main()
```

#### 2. Gap Filler (`jobs/extract_klines_gap_filler.py`)

**Intelligent Gap Detection:**

```python
def detect_gaps(
    symbol: str,
    interval: str,
    adapter: BaseAdapter,
    max_gap_days: int = 7
) -> List[Tuple[datetime, datetime]]:
    """
    Detect missing data gaps in the database.

    Algorithm:
    1. Query all records for symbol/interval
    2. Calculate expected time between records
    3. Find periods where actual > expected
    4. Return list of (start, end) tuples for gaps
    """
    # Get all timestamps
    timestamps = adapter.get_all_kline_times(symbol, interval)

    if len(timestamps) < 2:
        return []

    # Calculate interval in milliseconds
    interval_ms = interval_to_milliseconds(interval)
    interval_delta = timedelta(milliseconds=interval_ms)

    gaps = []
    for i in range(len(timestamps) - 1):
        current = timestamps[i]
        next_time = timestamps[i + 1]
        expected_next = current + interval_delta

        # Check if there's a gap
        if next_time > expected_next + interval_delta:
            gap_duration = (next_time - expected_next).days

            # Only fill gaps up to max_gap_days
            if gap_duration <= max_gap_days:
                gaps.append((expected_next, next_time))
                logger.info(
                    f"{symbol}: Gap detected from {expected_next} to {next_time} "
                    f"({gap_duration} days)"
                )

    return gaps

def fill_gaps(
    symbol: str,
    interval: str,
    gaps: List[Tuple[datetime, datetime]],
    adapter: BaseAdapter,
    fetcher: KlinesFetcher
) -> int:
    """Fill detected gaps."""
    total_filled = 0

    for start_time, end_time in gaps:
        logger.info(f"{symbol}: Filling gap {start_time} to {end_time}")

        # Fetch missing klines
        klines = fetcher.fetch_klines(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time
        )

        if klines:
            adapter.insert_klines(klines)
            total_filled += len(klines)
            logger.info(f"{symbol}: Filled {len(klines)} records")

    return total_filled
```

#### 3. Binance Client (`fetchers/client.py`)

**Rate Limiting and Retry Logic:**

```python
class BinanceClient:
    """Base Binance API client with rate limiting."""

    def __init__(
        self,
        api_url: str,
        api_key: str = "",
        api_secret: str = "",
        rate_limit: int = 1200  # requests per minute
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.rate_limit = rate_limit

        # Rate limiting
        self.request_timestamps = []
        self.request_lock = threading.Lock()

    def _wait_for_rate_limit(self):
        """Implement rate limiting."""
        with self.request_lock:
            now = time.time()

            # Remove timestamps older than 1 minute
            self.request_timestamps = [
                ts for ts in self.request_timestamps
                if now - ts < 60
            ]

            # Check if at rate limit
            if len(self.request_timestamps) >= self.rate_limit:
                oldest = self.request_timestamps[0]
                sleep_time = 60 - (now - oldest)
                if sleep_time > 0:
                    logger.warning(f"Rate limit reached, sleeping {sleep_time:.2f}s")
                    time.sleep(sleep_time)

            # Add current request
            self.request_timestamps.append(now)

    def _make_request(
        self,
        endpoint: str,
        params: dict,
        max_retries: int = 3
    ) -> requests.Response:
        """Make API request with retry logic."""
        self._wait_for_rate_limit()

        url = f"{self.api_url}{endpoint}"

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers={"X-MBX-APIKEY": self.api_key} if self.api_key else {},
                    timeout=constants.API_TIMEOUT
                )

                if response.status_code == 429:  # Too Many Requests
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited, retrying after {retry_after}s")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise

                backoff = constants.RETRY_BACKOFF_SECONDS * (2 ** attempt)
                logger.warning(f"Request failed, retrying in {backoff}s: {e}")
                time.sleep(backoff)

        raise Exception("Max retries exceeded")
```

#### 4. Klines Fetcher (`fetchers/klines.py`)

**Efficient Data Fetching:**

```python
class KlinesFetcher:
    """Fetch klines (candlestick) data from Binance."""

    def __init__(self, api_url: str, api_key: str = "", api_secret: str = ""):
        self.client = BinanceClient(api_url, api_key, api_secret)

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> List[KlineModel]:
        """
        Fetch klines for a time range.

        Args:
            symbol: Trading symbol
            interval: Time interval (e.g., 15m, 1h)
            start_time: Start time (inclusive)
            end_time: End time (inclusive)
            limit: Max records per request (max 1000)

        Returns:
            List of validated KlineModel objects
        """
        klines = []
        current_start = start_time

        while current_start < end_time:
            # Prepare request parameters
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": int(current_start.timestamp() * 1000),
                "endTime": int(end_time.timestamp() * 1000),
                "limit": limit
            }

            # Fetch batch
            response = self.client._make_request("/fapi/v1/klines", params)
            batch_data = response.json()

            if not batch_data:
                break

            # Parse and validate
            for raw_kline in batch_data:
                try:
                    kline = self._parse_kline(symbol, interval, raw_kline)
                    klines.append(kline)
                except Exception as e:
                    logger.warning(f"Failed to parse kline: {e}")
                    continue

            # Update start time for next batch
            last_kline_time = datetime.fromtimestamp(batch_data[-1][0] / 1000, tz=UTC)
            current_start = last_kline_time + get_interval_timedelta(interval)

            # Rate limiting delay
            time.sleep(constants.REQUEST_DELAY_SECONDS)

        logger.info(f"{symbol}: Fetched {len(klines)} klines")
        return klines

    def _parse_kline(self, symbol: str, interval: str, data: list) -> KlineModel:
        """Parse raw Binance kline data into KlineModel."""
        return KlineModel(
            symbol=symbol,
            interval=interval,
            open_time=datetime.fromtimestamp(data[0] / 1000, tz=UTC),
            close_time=datetime.fromtimestamp(data[6] / 1000, tz=UTC),
            open_price=Decimal(str(data[1])),
            high_price=Decimal(str(data[2])),
            low_price=Decimal(str(data[3])),
            close_price=Decimal(str(data[4])),
            volume=Decimal(str(data[5])),
            quote_asset_volume=Decimal(str(data[7])),
            number_of_trades=int(data[8]),
            taker_buy_base_asset_volume=Decimal(str(data[9])),
            taker_buy_quote_asset_volume=Decimal(str(data[10])),
            timestamp=datetime.fromtimestamp(data[0] / 1000, tz=UTC)
        )
```

#### 5. MySQL Adapter (`db/mysql_adapter.py`)

**Efficient Batch Inserts:**

```python
class MySQLAdapter(BaseAdapter):
    """MySQL database adapter with batch insert optimization."""

    def __init__(self, connection_string: str):
        self.engine = create_engine(
            connection_string,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600    # Recycle connections every hour
        )
        self.Session = sessionmaker(bind=self.engine)

    def insert_klines(self, klines: List[KlineModel]) -> int:
        """
        Batch insert klines with conflict resolution.

        Uses ON DUPLICATE KEY UPDATE to handle conflicts.
        Returns number of rows inserted/updated.
        """
        if not klines:
            return 0

        # Group by symbol and interval
        grouped = defaultdict(list)
        for kline in klines:
            table_name = self._get_table_name(kline.symbol, kline.interval)
            grouped[table_name].append(kline)

        total_inserted = 0

        for table_name, klines_batch in grouped.items():
            # Build INSERT ... ON DUPLICATE KEY UPDATE query
            query = f"""
                INSERT INTO {table_name} (
                    symbol, open_time, close_time, interval,
                    open_price, high_price, low_price, close_price,
                    volume, quote_asset_volume, number_of_trades,
                    taker_buy_base_asset_volume, taker_buy_quote_asset_volume
                ) VALUES (
                    :symbol, :open_time, :close_time, :interval,
                    :open_price, :high_price, :low_price, :close_price,
                    :volume, :quote_asset_volume, :number_of_trades,
                    :taker_buy_base_asset_volume, :taker_buy_quote_asset_volume
                )
                ON DUPLICATE KEY UPDATE
                    close_price = VALUES(close_price),
                    high_price = GREATEST(high_price, VALUES(high_price)),
                    low_price = LEAST(low_price, VALUES(low_price)),
                    volume = VALUES(volume),
                    updated_at = CURRENT_TIMESTAMP
            """

            # Convert to dictionaries
            values = [kline.dict() for kline in klines_batch]

            with self.engine.begin() as conn:
                result = conn.execute(text(query), values)
                total_inserted += result.rowcount

        return total_inserted

    def get_last_kline_time(self, symbol: str, interval: str) -> Optional[datetime]:
        """Get timestamp of last kline in database."""
        table_name = self._get_table_name(symbol, interval)

        query = f"""
            SELECT MAX(open_time) as last_time
            FROM {table_name}
            WHERE symbol = :symbol
        """

        with self.engine.connect() as conn:
            result = conn.execute(text(query), {"symbol": symbol})
            row = result.fetchone()
            return row[0] if row and row[0] else None

    def _get_table_name(self, symbol: str, interval: str) -> str:
        """Generate table name from symbol and interval."""
        # Convert: BTCUSDT, 15m -> btcusdt_klines_15m
        return f"{symbol.lower()}_klines_{interval}"
```

### Configuration

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `BINANCE_API_URL` | `https://api.binance.com` | Binance REST API URL |
| `BINANCE_FUTURES_API_URL` | `https://fapi.binance.com` | Binance Futures API URL |
| `DEFAULT_SYMBOLS` | `BTCUSDT,ETHUSDT,BNBUSDT` | Default symbols to extract |
| `DB_ADAPTER` | `mysql` | Database adapter (mysql, mongodb, postgresql) |
| `MYSQL_URI` | `mysql://user:pass@localhost:3306/db` | MySQL connection string |
| `DB_BATCH_SIZE` | `2000` | Batch size for inserts |
| `MAX_WORKERS` | `4` | Parallel extraction workers |
| `API_RATE_LIMIT` | `1200` | API rate limit (requests/min) |
| `REQUEST_DELAY_SECONDS` | `0.1` | Delay between requests |
| `LOOKBACK_HOURS` | `24` | Initial lookback period |

### Code Examples

**Manual Extraction:**

```bash
# Extract 15-minute klines for default symbols
python -m jobs.extract_klines_production --period 15m

# Extract specific symbols
python -m jobs.extract_klines_production --period 1h --symbols BTCUSDT,ETHUSDT

# Extract with custom parallelism
python -m jobs.extract_klines_production --period 15m --parallel 8
```

**Gap Filling:**

```bash
# Detect and fill gaps
python -m jobs.extract_klines_gap_filler --period 15m

# Fill gaps for specific symbol
python -m jobs.extract_klines_gap_filler --period 1h --symbols BTCUSDT

# Fill large gaps (up to 30 days)
python -m jobs.extract_klines_gap_filler --period 15m --max-gap-days 30
```

**Python API Usage:**

```python
from db import get_adapter
from fetchers import KlinesFetcher
from models import KlineModel

# Initialize
adapter = get_adapter("mysql", "mysql://user:pass@localhost/db")
fetcher = KlinesFetcher("https://fapi.binance.com")

# Fetch klines
klines = fetcher.fetch_klines(
    symbol="BTCUSDT",
    interval="15m",
    start_time=datetime(2024, 1, 1, tzinfo=UTC),
    end_time=datetime(2024, 1, 2, tzinfo=UTC)
)

# Insert into database
adapter.insert_klines(klines)
print(f"Inserted {len(klines)} klines")

# Query data
last_time = adapter.get_last_kline_time("BTCUSDT", "15m")
print(f"Last kline at: {last_time}")
```

### Troubleshooting

**Common Issues:**

1. **Rate Limit Errors**
   - Reduce `MAX_WORKERS`
   - Increase `REQUEST_DELAY_SECONDS`
   - Check `API_RATE_LIMIT` setting

2. **Database Connection Issues**
   - Verify `MYSQL_URI` credentials
   - Check connection pool settings
   - Test connectivity: `mysql -h host -u user -p`

3. **Missing Data Gaps**
   - Run gap filler: `python -m jobs.extract_klines_gap_filler`
   - Check Binance API status
   - Verify time ranges in database queries

4. **Memory Issues**
   - Reduce `DB_BATCH_SIZE`
   - Limit number of symbols processed in parallel
   - Monitor pod memory in Kubernetes

---

## 🚀 Quick Start

```bash
# Setup
make setup

# Run extraction
python -m jobs.extract_klines_production --period 15m

# Run gap filler
python -m jobs.extract_klines_gap_filler --period 15m

# Deploy to Kubernetes
make deploy
```

---

**Production Status:** ✅ **ACTIVE** - Extracting historical data for 10+ symbols across multiple timeframes
