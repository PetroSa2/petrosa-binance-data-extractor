# Test Implementation Guide

## Quick Start

### 1. Setting Up Test Environment

```bash
# Ensure you have all dev dependencies
pip install -r requirements-dev.txt

# Run current tests to establish baseline
make run_unit_tests

# Check current coverage
make coverage
```

### 2. Test File Structure

Follow this pattern for new test files:

```python
#!/usr/bin/env python3
"""
Tests for [module_name].

This module tests the functionality of [module_name].
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Import the module under test
from [module_path] import [ClassOrFunction]


class Test[ClassName]:
    """Test cases for [ClassName]."""

    def setup_method(self):
        """Set up test fixtures."""
        # Initialize test data and mocks
        pass

    def test_method_name(self):
        """Test specific functionality."""
        # Arrange
        # Act
        # Assert
        pass

    def test_error_handling(self):
        """Test error scenarios."""
        # Test exception handling
        pass
```

### 3. Mock Patterns

#### Database Mocks
```python
@pytest.fixture
def mock_db_adapter():
    """Mock database adapter."""
    adapter = Mock()
    adapter.connect.return_value = None
    adapter.disconnect.return_value = None
    adapter.write.return_value = 10
    adapter.query_range.return_value = []
    return adapter
```

#### API Client Mocks
```python
@pytest.fixture
def mock_binance_client():
    """Mock Binance API client."""
    client = Mock()
    client.get_request.return_value = {
        "status_code": 200,
        "data": []
    }
    return client
```

#### Time Mocks
```python
@patch('utils.time_utils.get_current_utc_time')
def test_time_dependent_function(mock_current_time):
    """Test time-dependent functionality."""
    mock_current_time.return_value = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Test implementation
```

### 4. Testing Priority Order

#### Phase 1: Critical (0% Coverage)

**Start with config/symbols.py:**
```python
# tests/test_config.py
from config.symbols import get_symbols, validate_symbol

def test_get_symbols():
    """Test symbol loading."""
    symbols = get_symbols()
    assert isinstance(symbols, list)
    assert len(symbols) > 0

def test_validate_symbol():
    """Test symbol validation."""
    assert validate_symbol("BTCUSDT") is True
    assert validate_symbol("INVALID") is False
```

**Then jobs/extract_funding.py:**
```python
# tests/test_extract_funding.py
from jobs.extract_funding import main, parse_arguments

def test_parse_arguments():
    """Test argument parsing."""
    with patch('sys.argv', ['extract_funding.py', '--symbols', 'BTCUSDT']):
        args = parse_arguments()
        assert args.symbols == ['BTCUSDT']

def test_main_with_mocks():
    """Test main function with mocked dependencies."""
    with patch('jobs.extract_funding.BinanceClient'), \
         patch('jobs.extract_funding.get_adapter'):
        # Test implementation
        pass
```

### 5. Database Testing

#### MongoDB Testing
```python
@pytest.fixture
def mock_mongodb():
    """Mock MongoDB connection."""
    with patch('pymongo.MongoClient') as mock_client:
        mock_db = Mock()
        mock_collection = Mock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        yield mock_collection
```

#### MySQL Testing
```python
@pytest.fixture
def mock_mysql():
    """Mock MySQL connection."""
    with patch('sqlalchemy.create_engine') as mock_engine:
        mock_conn = Mock()
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
        yield mock_conn
```

### 6. Integration Testing

#### End-to-End Workflow
```python
def test_complete_extraction_workflow():
    """Test complete extraction workflow."""
    # Mock all external dependencies
    with patch('fetchers.client.BinanceClient'), \
         patch('db.mysql_adapter.MySQLAdapter'), \
         patch('utils.logger.get_logger'):
        
        # Test the complete workflow
        result = run_extraction_workflow()
        assert result['success'] is True
```

### 7. Error Handling Testing

#### Test Exception Scenarios
```python
def test_database_connection_error():
    """Test database connection failure."""
    with patch('db.mysql_adapter.MySQLAdapter.connect', side_effect=Exception("Connection failed")):
        with pytest.raises(DatabaseError):
            # Test implementation
            pass

def test_api_rate_limit_error():
    """Test API rate limiting."""
    with patch('fetchers.client.BinanceClient.get_request', side_effect=RateLimitError()):
        # Test retry logic
        pass
```

### 8. Performance Testing

#### Test Large Data Sets
```python
def test_large_dataset_processing():
    """Test processing large datasets."""
    large_dataset = generate_test_data(10000)
    
    start_time = time.time()
    result = process_data(large_dataset)
    end_time = time.time()
    
    assert end_time - start_time < 5.0  # Should complete within 5 seconds
    assert result['processed_count'] == 10000
```

### 9. Coverage Reporting

#### Check Coverage for Specific Files
```bash
# Check coverage for specific module
pytest tests/test_extract_funding.py --cov=jobs.extract_funding --cov-report=term-missing

# Check coverage for specific function
pytest tests/test_extract_funding.py::TestExtractFunding::test_main --cov=jobs.extract_funding --cov-report=term-missing
```

### 10. Continuous Integration

#### GitHub Actions Integration
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      - name: Run tests with coverage
        run: |
          pytest tests/ --cov=. --cov-report=xml --cov-report=term
      - name: Upload coverage
        uses: codecov/codecov-action@v1
```

### 11. Best Practices

#### Test Organization
- Group related tests in classes
- Use descriptive test names
- Test both success and failure scenarios
- Test edge cases and boundary conditions

#### Mock Management
- Use fixtures for common mocks
- Reset mocks between tests
- Verify mock calls when important
- Use `autospec=True` for better mock behavior

#### Data Management
- Use factories for test data generation
- Clean up test data after tests
- Use unique identifiers for test data
- Avoid hardcoded test values

#### Assertions
- Use specific assertions
- Test one thing per test
- Use meaningful assertion messages
- Test both positive and negative cases

### 12. Common Patterns

#### Testing CLI Applications
```python
def test_cli_application():
    """Test CLI application."""
    with patch('sys.argv', ['app.py', '--help']):
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            main()
            assert 'usage:' in mock_stdout.getvalue()
```

#### Testing Configuration Loading
```python
def test_config_loading():
    """Test configuration loading."""
    with patch.dict(os.environ, {'DB_URI': 'test://localhost'}):
        config = load_config()
        assert config['db_uri'] == 'test://localhost'
```

#### Testing File Operations
```python
def test_file_operations():
    """Test file operations."""
    with tempfile.NamedTemporaryFile() as temp_file:
        # Test file operations
        write_data(temp_file.name, "test data")
        assert read_data(temp_file.name) == "test data"
```

This guide provides a foundation for implementing comprehensive test coverage across all modules in the project. 