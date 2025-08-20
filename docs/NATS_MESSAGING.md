# NATS Messaging Integration

This document describes the NATS messaging integration for the Binance data extractor. When enabled, the system will send messages to NATS whenever a kline extraction action (extract a symbol) is completed.

## Overview

The NATS messaging feature provides real-time notifications about extraction completion events. This is useful for:

- Monitoring extraction progress
- Triggering downstream processes
- Alerting on failures
- Tracking performance metrics

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://localhost:4222` | NATS server URL |
| `NATS_ENABLED` | `true` | Enable/disable NATS messaging |
| `NATS_SUBJECT_PREFIX` | `binance.extraction` | Subject prefix for messages |

### Example Configuration

```bash
# Enable NATS messaging
export NATS_ENABLED=true

# Configure NATS server
export NATS_URL=nats://nats-server:4222

# Optional: Custom subject prefix
export NATS_SUBJECT_PREFIX=petrosa.binance.extraction
```

## Message Format

### Single Symbol Extraction Completion

**Subject:** `binance.extraction.{extraction_type}.{symbol}.{period}`

**Example:** `binance.extraction.klines.BTCUSDT.15m`

**Message Content:**
```json
{
  "event_type": "extraction_completed",
  "extraction_type": "klines",
  "symbol": "BTCUSDT",
  "period": "15m",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "success": true,
  "metrics": {
    "records_fetched": 150,
    "records_written": 150,
    "duration_seconds": 3.5,
    "gaps_found": 0,
    "gaps_filled": 0
  },
  "errors": []
}
```

### Batch Extraction Completion

**Subject:** `binance.extraction.{extraction_type}.batch.{period}`

**Example:** `binance.extraction.klines.batch.15m`

**Message Content:**
```json
{
  "event_type": "batch_extraction_completed",
  "extraction_type": "klines",
  "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
  "period": "15m",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "success": true,
  "metrics": {
    "total_records_fetched": 450,
    "total_records_written": 450,
    "duration_seconds": 12.5,
    "total_gaps_found": 0,
    "total_gaps_filled": 0,
    "symbols_processed": 3
  },
  "errors": []
}
```

## Extraction Types

The system supports different extraction types:

- `klines` - Regular kline data extraction
- `klines_gap_filling` - Gap filling operations
- `trades` - Trade data extraction (future)
- `funding` - Funding rate extraction (future)

## Integration Points

### 1. Regular Klines Extraction (`jobs/extract_klines.py`)

Messages are sent after each symbol is processed:

```python
# Send NATS message for symbol completion
if constants.NATS_ENABLED:
    try:
        publish_extraction_completion_sync(
            symbol=symbol,
            period=args.period,
            records_fetched=result["records_fetched"],
            records_written=result["records_written"],
            success=result["success"],
            duration_seconds=result["duration_seconds"],
            errors=result["errors"],
            gaps_found=result["gaps_found"],
            extraction_type="klines",
        )
    except Exception as e:
        logger.warning(f"Failed to send NATS message for {symbol}: {e}")
```

### 2. Production Klines Extraction (`jobs/extract_klines_production.py`)

Messages are sent after each symbol is processed in parallel:

```python
# Send NATS message for symbol completion
if constants.NATS_ENABLED:
    try:
        publish_extraction_completion_sync(
            symbol=symbol,
            period=self.period,
            records_fetched=result["records_fetched"],
            records_written=result["records_written"],
            success=result["success"],
            duration_seconds=result["duration"],
            errors=[result["error"]] if result["error"] else None,
            gaps_found=0,  # Not tracked in production extractor
            gaps_filled=result["gaps_filled"],
            extraction_type="klines",
        )
    except Exception as e:
        self.logger.warning(f"Failed to send NATS message for {symbol}: {e}")
```

### 3. Gap Filling Extraction (`jobs/extract_klines_gap_filler.py`)

Messages are sent after each symbol's gaps are processed:

```python
# Send NATS message for symbol completion
if constants.NATS_ENABLED:
    try:
        publish_extraction_completion_sync(
            symbol=symbol,
            period=self.period,
            records_fetched=result["total_records_fetched"],
            records_written=result["total_records_written"],
            success=result["success"],
            duration_seconds=result["duration"],
            errors=[result["error"]] if result["error"] else None,
            gaps_found=result["gaps_found"],
            gaps_filled=result["gaps_filled"],
            extraction_type="klines_gap_filling",
        )
    except Exception as e:
        self.logger.warning(f"Failed to send NATS message for {symbol}: {e}")
```

## Testing

### Test Script

Run the test script to verify NATS messaging:

```bash
python scripts/test_nats_messaging.py
```

### Unit Tests

Run the unit tests:

```bash
python -m pytest tests/test_messaging.py -v
```

## Error Handling

The NATS messaging is designed to be non-blocking:

1. **Connection Failures**: If NATS server is unavailable, extraction continues without messaging
2. **Message Failures**: Failed message sends are logged as warnings but don't affect extraction
3. **Configuration**: If `NATS_ENABLED=false`, messaging is completely disabled

## Monitoring

### Message Subjects

Monitor these subjects for different events:

- `binance.extraction.klines.*` - Regular kline extraction
- `binance.extraction.klines_gap_filling.*` - Gap filling operations
- `binance.extraction.klines.batch.*` - Batch extraction completion

### Example NATS Consumer

```python
import asyncio
import nats
import json

async def message_handler(msg):
    subject = msg.subject
    data = json.loads(msg.data.decode())
    print(f"Received message on {subject}: {data}")

async def main():
    nc = await nats.connect("nats://localhost:4222")

    # Subscribe to all extraction events
    await nc.subscribe("binance.extraction.>", cb=message_handler)

    # Keep the connection alive
    await asyncio.sleep(3600)  # 1 hour

if __name__ == "__main__":
    asyncio.run(main())
```

## Deployment

### Docker

Add NATS environment variables to your Docker deployment:

```yaml
environment:
  - NATS_ENABLED=true
  - NATS_URL=nats://nats-server:4222
```

### Kubernetes

Add NATS configuration to your Kubernetes deployment:

```yaml
env:
- name: NATS_ENABLED
  value: "true"
- name: NATS_URL
  value: "nats://nats-server:4222"
```

## Troubleshooting

### Common Issues

1. **NATS Connection Failed**
   - Check NATS server is running
   - Verify NATS_URL is correct
   - Check network connectivity

2. **Messages Not Received**
   - Verify NATS_ENABLED=true
   - Check subject patterns match
   - Review NATS server logs

3. **Performance Impact**
   - NATS messaging is asynchronous
   - Failed messages don't block extraction
   - Consider NATS server performance

### Logs

Look for these log messages:

- `"Connected to NATS server at {url}"` - Successful connection
- `"Published extraction completion message for {symbol}"` - Message sent
- `"Failed to send NATS message for {symbol}"` - Message failed
- `"Failed to connect to NATS server"` - Connection failed

## Future Enhancements

- Batch message aggregation
- Message persistence
- Retry mechanisms
- Message filtering
- Custom message formats
