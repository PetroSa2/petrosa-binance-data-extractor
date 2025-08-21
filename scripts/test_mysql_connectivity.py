#!/usr/bin/env python3
"""
MySQL Connectivity Test Script

This script tests MySQL connectivity from within the Kubernetes cluster
to help diagnose connection issues.
"""

import os
import socket
import subprocess
from urllib.parse import urlparse


def test_dns_resolution(hostname):
    """Test DNS resolution for a hostname."""
    print(f"🔍 Testing DNS resolution for: {hostname}")
    try:
        ip = socket.gethostbyname(hostname)
        print(f"✅ DNS resolution successful: {hostname} -> {ip}")
        return ip
    except socket.gaierror as e:
        print(f"❌ DNS resolution failed: {e}")
        return None


def test_port_connectivity(hostname, port, timeout=5):
    """Test TCP connectivity to a specific port."""
    print(f"🔌 Testing TCP connectivity to {hostname}:{port}")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((hostname, port))
        sock.close()

        if result == 0:
            print(f"✅ Port {port} is open on {hostname}")
            return True
        else:
            print(f"❌ Port {port} is closed on {hostname} (error code: {result})")
            return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


def test_mysql_connection(mysql_uri):
    """Test MySQL connection using the provided URI."""
    print(f"🗄️ Testing MySQL connection with URI: {mysql_uri}")

    try:
        import pymysql
        from sqlalchemy import create_engine

        # Parse the URI
        parsed = urlparse(mysql_uri)
        hostname = parsed.hostname
        port = parsed.port or 3306
        username = parsed.username
        database = parsed.path.lstrip("/")

        print(f"   Hostname: {hostname}")
        print(f"   Port: {port}")
        print(f"   Username: {username}")
        print(f"   Database: {database}")

        # Test with SQLAlchemy
        print("   Testing with SQLAlchemy...")
        engine = create_engine(mysql_uri, pool_pre_ping=True, pool_recycle=300)
        with engine.connect() as conn:
            result = conn.execute("SELECT 1 as test")
            row = result.fetchone()
            print(f"✅ SQLAlchemy connection successful: {row[0]}")

        # Test with PyMySQL directly
        print("   Testing with PyMySQL directly...")
        connection = pymysql.connect(
            host=hostname,
            port=port,
            user=username,
            password=parsed.password,
            database=database,
            charset="utf8mb4",
            connect_timeout=10,
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            print(f"✅ PyMySQL connection successful: {result[0]}")

        connection.close()
        return True

    except ImportError as e:
        print(f"❌ Required libraries not available: {e}")
        return False
    except Exception as e:
        print(f"❌ MySQL connection failed: {e}")
        return False


def test_network_policies():
    """Test if network policies are affecting connectivity."""
    print("🔒 Checking network policies...")

    try:
        # Test basic internet connectivity
        print("   Testing internet connectivity...")
        result = subprocess.run(
            ["curl", "-s", "--connect-timeout", "5", "https://httpbin.org/ip"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print("✅ Internet connectivity is working")
        else:
            print("❌ Internet connectivity failed")

        # Test DNS resolution
        print("   Testing DNS resolution...")
        result = subprocess.run(
            ["nslookup", "google.com"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("✅ DNS resolution is working")
        else:
            print("❌ DNS resolution failed")

    except Exception as e:
        print(f"❌ Network policy test failed: {e}")


def test_environment_variables():
    """Check environment variables related to MySQL."""
    print("🔧 Checking environment variables...")

    mysql_uri = os.getenv("MYSQL_URI")
    if mysql_uri:
        print(f"✅ MYSQL_URI is set: {mysql_uri[:50]}...")
    else:
        print("❌ MYSQL_URI is not set")

    db_adapter = os.getenv("DB_ADAPTER")
    print(f"   DB_ADAPTER: {db_adapter}")

    environment = os.getenv("ENVIRONMENT")
    print(f"   ENVIRONMENT: {environment}")


def test_other_services():
    """Test connectivity to other services in the cluster."""
    print("🌐 Testing connectivity to other services...")

    services = [
        ("petrosa-ta-bot-service", 80),
        ("petrosa-tradeengine-service", 80),
        ("petrosa-socket-client", 80),
        ("petrosa-realtime-strategies", 80),
    ]

    for service, port in services:
        print(f"   Testing {service}:{port}...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((service, port))
            sock.close()

            if result == 0:
                print(f"   ✅ {service}:{port} is reachable")
            else:
                print(f"   ❌ {service}:{port} is not reachable")
        except Exception as e:
            print(f"   ❌ {service}:{port} test failed: {e}")


def main():
    """Main test function."""
    print("🚀 Starting MySQL Connectivity Test")
    print("=" * 50)

    # Test environment variables
    test_environment_variables()
    print()

    # Test network policies
    test_network_policies()
    print()

    # Test other services
    test_other_services()
    print()

    # Get MySQL URI from environment
    mysql_uri = os.getenv("MYSQL_URI")
    if not mysql_uri:
        print("❌ MYSQL_URI environment variable not found")
        return

    # Parse MySQL URI
    try:
        parsed = urlparse(mysql_uri)
        hostname = parsed.hostname
        port = parsed.port or 3306
    except Exception as e:
        print(f"❌ Failed to parse MYSQL_URI: {e}")
        return

    print(f"🎯 Testing MySQL connectivity to {hostname}:{port}")
    print("=" * 50)

    # Test DNS resolution
    ip = test_dns_resolution(hostname)
    print()

    if ip:
        # Test port connectivity
        port_open = test_port_connectivity(hostname, port)
        print()

        if port_open:
            # Test MySQL connection
            mysql_success = test_mysql_connection(mysql_uri)
            print()

            if mysql_success:
                print("🎉 All tests passed! MySQL connectivity is working.")
            else:
                print(
                    "⚠️ Port is open but MySQL connection failed. Check credentials or MySQL configuration."
                )
        else:
            print("⚠️ Port is closed. Check firewall rules or MySQL server status.")
    else:
        print("⚠️ DNS resolution failed. Check network configuration.")

    print("=" * 50)
    print("🏁 Test completed")


if __name__ == "__main__":
    main()
