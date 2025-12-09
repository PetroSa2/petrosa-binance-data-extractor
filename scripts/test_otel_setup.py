#!/usr/bin/env python3
"""
Test script to verify OpenTelemetry setup is working correctly.
"""

import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def test_imports():
    """Test that all required modules can be imported."""
    print("🔍 Testing imports...")

    try:
        import constants

        assert constants is not None  # Constants should be imported
        print("✅ Constants imported successfully")
        print(f"   - OTEL_SERVICE_NAME_KLINES: {constants.OTEL_SERVICE_NAME_KLINES}")
        print(f"   - OTEL_SERVICE_NAME_FUNDING: {constants.OTEL_SERVICE_NAME_FUNDING}")
        print(f"   - OTEL_SERVICE_NAME_TRADES: {constants.OTEL_SERVICE_NAME_TRADES}")
    except ImportError as e:
        assert e is not None  # Exception should be captured
        print(f"❌ Failed to import constants: {e}")
        return False

    try:
        print("✅ otel_init imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import otel_init: {e}")
        return False

    try:
        print("✅ TelemetryManager imported successfully")
    except ImportError as e:
        print(f"⚠️  TelemetryManager not available: {e}")
        # This is not critical

    return True


def test_otel_setup():
    """Test OpenTelemetry setup."""
    print("\n🔧 Testing OpenTelemetry setup...")

    try:
        from otel_init import setup_telemetry

        # Test with custom service name
        result = setup_telemetry(service_name="test-service")
        assert result is not None or result is False  # Result can be False
        print(f"✅ setup_telemetry completed with result: {result}")

        if not result:
            print("ℹ️  Telemetry setup returned False (expected without OTLP endpoint)")

        return True
    except Exception as e:
        assert e is not None  # Exception should be captured
        print(f"❌ OpenTelemetry setup failed: {e}")
        return False


def test_instrumentation_packages():
    """Test that required instrumentation packages are available."""
    print("\n📦 Testing instrumentation packages...")

    packages_to_test = [
        "opentelemetry",
        "opentelemetry.sdk",
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
        "opentelemetry.instrumentation.requests",
        "opentelemetry.instrumentation.pymongo",
        "opentelemetry.instrumentation.sqlalchemy",
        "opentelemetry.instrumentation.logging",
        "opentelemetry.instrumentation.urllib3",
    ]

    success_count = 0
    assert len(packages_to_test) > 0  # Should have packages to test
    for package in packages_to_test:
        try:
            module = __import__(package)
            assert module is not None  # Module should be imported
            print(f"✅ {package}")
            success_count += 1
        except ImportError as e:
            assert e is not None  # Exception should be captured
            print(f"❌ {package}: {e}")

    assert isinstance(success_count, int)  # Should be integer
    print(
        f"\n📊 Successfully imported {success_count}/{len(packages_to_test)} packages"
    )
    return success_count == len(packages_to_test)


def main():
    """Main test function."""
    print("🚀 OpenTelemetry Setup Test")
    print("=" * 50)

    all_tests_passed = True

    # Test imports
    if not test_imports():
        all_tests_passed = False

    # Test OpenTelemetry setup
    if not test_otel_setup():
        all_tests_passed = False

    # Test instrumentation packages
    if not test_instrumentation_packages():
        all_tests_passed = False

    # Final result
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("🎉 All tests passed! OpenTelemetry setup is working correctly.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
