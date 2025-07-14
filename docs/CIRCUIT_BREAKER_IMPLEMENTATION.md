# Circuit Breaker Pattern Implementation

## Overview

The Circuit Breaker pattern has been implemented to prevent cascading failures and improve system resilience in the Petrosa Binance Data Extractor. This document provides detailed information about the implementation, configuration, and usage.

## Table of Contents

1. [Design Overview](#design-overview)
2. [Implementation Details](#implementation-details)
3. [Configuration Options](#configuration-options)
4. [Usage Examples](#usage-examples)
5. [State Management](#state-management)
6. [Error Handling](#error-handling)
7. [Monitoring and Metrics](#monitoring-and-metrics)
8. [Testing](#testing)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

## Design Overview

### Circuit Breaker States

The circuit breaker operates in three states:

1. **CLOSED**: Normal operation state
   - All requests pass through to the protected function
   - Failures are counted
   - When failure threshold is reached, circuit opens

2. **OPEN**: Failure state
   - All requests fail fast without calling the protected function
   - After recovery timeout, circuit moves to half-open state

3. **HALF_OPEN**: Testing state
   - Limited requests are allowed to test if service has recovered
   - Success moves circuit back to closed state
   - Failure moves circuit back to open state

### State Transition Diagram

```
CLOSED ──[failure_threshold reached]──> OPEN
  ↑                                      │
  │                                      │
  │                                      │
  └──[success]── HALF_OPEN ──[failure]──┘
       ↑                    │
       │                    │
       └──[recovery_timeout]┘
```

## Implementation Details

### Core Implementation

The circuit breaker is implemented in `utils/circuit_breaker.py`:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60, 
                 expected_exception=Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self._lock = threading.Lock()
```

### Key Features

1. **Thread Safety**: Uses threading.Lock for concurrent access
2. **Configurable Thresholds**: Adjustable failure threshold and recovery timeout
3. **Exception Filtering**: Only counts specified exception types
4. **State Persistence**: Maintains state across function calls
5. **Decorator Support**: Can be used as a decorator

### Decorator Usage

```python
from utils.circuit_breaker import CircuitBreaker

# Create circuit breaker instance
db_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=(OperationalError, ConnectionError)
)

# Use as decorator
@db_circuit_breaker
def database_operation():
    # Database operation code
    pass
```

### Context Manager Usage

```python
# Use as context manager
with db_circuit_breaker:
    # Database operation code
    pass
```

## Configuration Options

### Basic Configuration

```python
# Default configuration
circuit_breaker = CircuitBreaker()

# Custom configuration
circuit_breaker = CircuitBreaker(
    failure_threshold=10,      # Number of failures before opening
    recovery_timeout=120,      # Seconds to wait before half-open
    expected_exception=(OperationalError, ConnectionError, TimeoutError)
)
```

### Advanced Configuration

```python
# Database-specific circuit breaker
db_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=(
        sqlalchemy.exc.OperationalError,
        sqlalchemy.exc.DisconnectionError,
        pymysql.err.OperationalError,
        pymongo.errors.ConnectionFailure,
        pymongo.errors.ServerSelectionTimeoutError
    )
)

# API-specific circuit breaker
api_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30,
    expected_exception=(
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.HTTPError
    )
)
```

### Environment Variable Configuration

```bash
# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60
CIRCUIT_BREAKER_ENABLED=true
```

## Usage Examples

### Database Operations

```python
from utils.circuit_breaker import CircuitBreaker
from sqlalchemy.exc import OperationalError

# Create database circuit breaker
db_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=OperationalError
)

@db_circuit_breaker
def execute_query(query):
    """Execute database query with circuit breaker protection"""
    with engine.connect() as conn:
        result = conn.execute(query)
        return result.fetchall()

# Usage
try:
    data = execute_query("SELECT * FROM klines")
except Exception as e:
    print(f"Query failed: {e}")
```

### API Calls

```python
import requests
from utils.circuit_breaker import CircuitBreaker

# Create API circuit breaker
api_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30,
    expected_exception=(
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout
    )
)

@api_circuit_breaker
def fetch_binance_data(symbol, interval):
    """Fetch data from Binance API with circuit breaker protection"""
    url = f"https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": 1000}
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

# Usage
try:
    data = fetch_binance_data("BTCUSDT", "15m")
except Exception as e:
    print(f"API call failed: {e}")
```

### Multiple Circuit Breakers

```python
# Different circuit breakers for different services
db_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
api_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
cache_circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=15)

@db_circuit_breaker
def database_operation():
    # Database operation
    pass

@api_circuit_breaker
def api_operation():
    # API operation
    pass

@cache_circuit_breaker
def cache_operation():
    # Cache operation
    pass
```

## State Management

### State Transitions

```python
class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

# State transition logic
def _on_failure(self):
    """Handle failure and potentially open circuit"""
    with self._lock:
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

def _on_success(self):
    """Handle success and potentially close circuit"""
    with self._lock:
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker closed after successful operation")

def _should_attempt_reset(self):
    """Check if circuit should attempt to reset"""
    if self.state == CircuitState.OPEN:
        if time.time() - self.last_failure_time >= self.recovery_timeout:
            return True
    return False
```

### State Monitoring

```python
def get_state_info(self):
    """Get current circuit breaker state information"""
    with self._lock:
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }

# Usage
info = circuit_breaker.get_state_info()
print(f"Circuit state: {info['state']}")
print(f"Failure count: {info['failure_count']}")
```

## Error Handling

### Exception Filtering

```python
def _is_expected_exception(self, exception):
    """Check if exception is expected and should count toward failure"""
    if isinstance(exception, self.expected_exception):
        return True
    return False

# Example usage
db_circuit_breaker = CircuitBreaker(
    expected_exception=(
        sqlalchemy.exc.OperationalError,
        sqlalchemy.exc.DisconnectionError
    )
)
```

### Custom Error Handling

```python
def custom_error_handler(func):
    """Custom error handler with circuit breaker"""
    circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
    
    def wrapper(*args, **kwargs):
        try:
            return circuit_breaker(func)(*args, **kwargs)
        except Exception as e:
            logger.error(f"Operation failed: {e}")
            # Custom error handling logic
            raise
    
    return wrapper

@custom_error_handler
def database_operation():
    # Database operation
    pass
```

## Monitoring and Metrics

### Metrics Collection

```python
class CircuitBreakerMetrics:
    def __init__(self):
        self.state_transitions = 0
        self.failure_count = 0
        self.success_count = 0
        self.total_requests = 0
    
    def record_state_transition(self, from_state, to_state):
        self.state_transitions += 1
        logger.info(f"Circuit breaker state transition: {from_state} -> {to_state}")
    
    def record_failure(self):
        self.failure_count += 1
        self.total_requests += 1
    
    def record_success(self):
        self.success_count += 1
        self.total_requests += 1
    
    def get_success_rate(self):
        if self.total_requests == 0:
            return 0.0
        return self.success_count / self.total_requests
```

### OpenTelemetry Integration

```python
from opentelemetry import trace

def circuit_breaker_span(func):
    """Add OpenTelemetry tracing to circuit breaker operations"""
    def wrapper(*args, **kwargs):
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span("circuit_breaker_operation") as span:
            span.set_attribute("circuit_breaker.state", circuit_breaker.state.value)
            span.set_attribute("circuit_breaker.failure_count", circuit_breaker.failure_count)
            
            try:
                result = func(*args, **kwargs)
                span.set_attribute("circuit_breaker.success", True)
                return result
            except Exception as e:
                span.set_attribute("circuit_breaker.success", False)
                span.set_attribute("circuit_breaker.error", str(e))
                raise
    
    return wrapper
```

## Testing

### Unit Tests

```python
import pytest
from utils.circuit_breaker import CircuitBreaker, CircuitState

class TestCircuitBreaker:
    def test_initial_state(self):
        """Test circuit breaker starts in CLOSED state"""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_failure_threshold(self):
        """Test circuit opens after failure threshold"""
        cb = CircuitBreaker(failure_threshold=3)
        
        # Simulate failures
        for _ in range(3):
            try:
                cb._on_failure()
            except Exception:
                pass
        
        assert cb.state == CircuitState.OPEN
    
    def test_recovery_timeout(self):
        """Test circuit moves to half-open after recovery timeout"""
        cb = CircuitBreaker(recovery_timeout=1)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.time() - 2  # 2 seconds ago
        
        assert cb._should_attempt_reset() == True
    
    def test_success_reset(self):
        """Test circuit closes after successful operation"""
        cb = CircuitBreaker()
        cb.state = CircuitState.HALF_OPEN
        
        cb._on_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
```

### Integration Tests

```python
def test_database_circuit_breaker():
    """Test circuit breaker with database operations"""
    db_circuit_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
    
    @db_circuit_breaker
    def failing_operation():
        raise OperationalError("Database connection failed", None, None)
    
    # First failure
    try:
        failing_operation()
    except Exception:
        pass
    
    # Second failure should open circuit
    try:
        failing_operation()
    except Exception:
        pass
    
    assert db_circuit_breaker.state == CircuitState.OPEN
    
    # Wait for recovery timeout
    time.sleep(1.1)
    
    # Should be in half-open state
    assert db_circuit_breaker.state == CircuitState.HALF_OPEN
```

## Best Practices

### Configuration Guidelines

1. **Failure Threshold**: Set based on expected failure rates
   - Low failure rate: 5-10 failures
   - High failure rate: 2-3 failures

2. **Recovery Timeout**: Set based on service recovery time
   - Fast recovery: 30-60 seconds
   - Slow recovery: 2-5 minutes

3. **Exception Types**: Only include transient exceptions
   - Include: Connection errors, timeouts
   - Exclude: Authentication errors, permission errors

### Usage Guidelines

1. **Service-Specific Circuit Breakers**: Create separate circuit breakers for different services
2. **Monitoring**: Always monitor circuit breaker state and metrics
3. **Testing**: Test circuit breaker behavior in failure scenarios
4. **Documentation**: Document circuit breaker configuration and behavior

### Anti-Patterns

1. **Too Low Failure Threshold**: Can cause unnecessary circuit opening
2. **Too High Recovery Timeout**: Can delay service recovery
3. **Including Permanent Errors**: Can cause circuit to stay open unnecessarily
4. **No Monitoring**: Can miss circuit breaker issues

## Troubleshooting

### Common Issues

#### Circuit Breaker Stuck Open

**Symptoms**: All operations failing immediately

**Causes**:
- Recovery timeout too long
- Service not actually recovered
- Circuit breaker not properly reset

**Solutions**:
```python
# Check circuit breaker state
info = circuit_breaker.get_state_info()
print(f"State: {info['state']}")
print(f"Last failure: {info['last_failure_time']}")

# Manually reset if needed
circuit_breaker.state = CircuitState.CLOSED
circuit_breaker.failure_count = 0
```

#### Circuit Breaker Opening Too Frequently

**Symptoms**: Circuit breaker opens and closes rapidly

**Causes**:
- Failure threshold too low
- Including non-transient errors
- Service genuinely unstable

**Solutions**:
```python
# Increase failure threshold
circuit_breaker = CircuitBreaker(failure_threshold=10)

# Review exception types
circuit_breaker = CircuitBreaker(
    expected_exception=(OperationalError,)  # Only transient errors
)
```

#### Circuit Breaker Not Opening

**Symptoms**: Failures not being counted

**Causes**:
- Exception types not matching
- Circuit breaker not properly configured
- Errors being caught before circuit breaker

**Solutions**:
```python
# Check exception types
print(f"Expected exceptions: {circuit_breaker.expected_exception}")

# Ensure exceptions reach circuit breaker
@circuit_breaker
def operation():
    # Don't catch exceptions here
    return risky_operation()
```

### Debugging Tools

```python
def debug_circuit_breaker(circuit_breaker):
    """Debug circuit breaker state and configuration"""
    info = circuit_breaker.get_state_info()
    
    print("=== Circuit Breaker Debug Info ===")
    print(f"State: {info['state']}")
    print(f"Failure Count: {info['failure_count']}")
    print(f"Failure Threshold: {info['failure_threshold']}")
    print(f"Recovery Timeout: {info['recovery_timeout']}")
    print(f"Last Failure Time: {info['last_failure_time']}")
    
    if info['last_failure_time']:
        time_since_failure = time.time() - info['last_failure_time']
        print(f"Time Since Last Failure: {time_since_failure:.2f}s")
        
        if info['state'] == CircuitState.OPEN.value:
            if time_since_failure >= info['recovery_timeout']:
                print("⚠️  Circuit should be in HALF_OPEN state")
            else:
                print(f"⏳ Circuit will reset in {info['recovery_timeout'] - time_since_failure:.2f}s")

# Usage
debug_circuit_breaker(db_circuit_breaker)
```

### Monitoring Queries

```sql
-- Circuit breaker state transitions
SELECT 
    timestamp,
    state,
    failure_count,
    failure_threshold
FROM circuit_breaker_events
WHERE timestamp >= NOW() - INTERVAL 1 HOUR
ORDER BY timestamp DESC;

-- Circuit breaker performance
SELECT 
    AVG(CASE WHEN success THEN 1 ELSE 0 END) as success_rate,
    COUNT(*) as total_operations,
    AVG(duration_ms) as avg_duration
FROM circuit_breaker_operations
WHERE timestamp >= NOW() - INTERVAL 1 HOUR;
```

## Conclusion

The Circuit Breaker pattern implementation provides robust protection against cascading failures while maintaining system resilience. Proper configuration, monitoring, and testing ensure optimal performance in production environments.

Key takeaways:
- Configure thresholds based on service characteristics
- Monitor circuit breaker state and metrics
- Test circuit breaker behavior thoroughly
- Use service-specific circuit breakers
- Document configuration and behavior 