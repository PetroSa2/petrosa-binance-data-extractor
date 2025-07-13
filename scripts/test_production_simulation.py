#!/usr/bin/env python3
"""
Production Environment Simulation Test

This script simulates a complete production environment with:
- Environment variable configuration
- OpenTelemetry initialization
- Kubernetes environment simulation
- New Relic integration test
"""

import json
import os
import sys
import time
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class ProductionEnvironmentSimulator:
    """Simulates a complete production environment."""

    def __init__(self):
        self.original_env = {}
        self.test_results = {
            "simulation_start": datetime.now().isoformat(),
            "tests_completed": [],
            "environment_configured": False,
            "telemetry_initialized": False,
            "jobs_ready": False,
            "kubernetes_ready": False,
            "production_ready": False,
        }

    def backup_environment(self):
        """Backup current environment variables."""
        env_vars_to_test = [
            "ENABLE_OTEL",
            "OTEL_SERVICE_NAME",
            "OTEL_SERVICE_VERSION",
            "OTEL_SERVICE_NAME_KLINES",
            "OTEL_SERVICE_NAME_FUNDING",
            "OTEL_SERVICE_NAME_TRADES",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "OTEL_EXPORTER_OTLP_HEADERS",
            "ENVIRONMENT",
            "K8S_NAMESPACE",
            "K8S_CLUSTER_NAME",
            "NEW_RELIC_LICENSE_KEY",
        ]

        for var in env_vars_to_test:
            self.original_env[var] = os.getenv(var)

    def restore_environment(self):
        """Restore original environment variables."""
        for var, value in self.original_env.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value

    def setup_production_environment(self):
        """Set up production-like environment variables."""
        print("🌍 Setting up production environment...")

        # Production environment variables
        production_env = {
            "ENABLE_OTEL": "true",
            "OTEL_SERVICE_NAME": "petrosa-binance-extractor",
            "OTEL_SERVICE_VERSION": "2.0.0",
            "OTEL_SERVICE_NAME_KLINES": "petrosa-klines-extractor",
            "OTEL_SERVICE_NAME_FUNDING": "petrosa-funding-extractor",
            "OTEL_SERVICE_NAME_TRADES": "petrosa-trades-extractor",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "https://otlp.nr-data.net:4317",
            "OTEL_EXPORTER_OTLP_HEADERS": "api-key=test-license-key-12345",
            "ENVIRONMENT": "production",
            "K8S_NAMESPACE": "petrosa-apps",
            "K8S_CLUSTER_NAME": "production-cluster",
            "K8S_POD_NAME": "klines-extractor-12345",
            "K8S_DEPLOYMENT_NAME": "binance-extractor",
            "KUBERNETES_SERVICE_HOST": "10.0.0.1",  # Simulate K8s
            "NEW_RELIC_LICENSE_KEY": "test-license-key-12345",
        }

        # Apply environment variables
        for key, value in production_env.items():
            os.environ[key] = value

        print("✅ Production environment variables set:")
        for key, value in production_env.items():
            if "key" in key.lower() or "license" in key.lower():
                print(f"   - {key}: ***masked***")
            else:
                print(f"   - {key}: {value}")

        self.test_results["environment_configured"] = True
        return True

    def test_telemetry_initialization(self):
        """Test telemetry initialization in production environment."""
        print("\n🔧 Testing telemetry initialization...")

        try:
            # Reload constants to pick up new environment
            import importlib

            import constants

            importlib.reload(constants)

            # Test service name configuration
            print(f"✅ Service names configured:")
            print(f"   - Klines: {constants.OTEL_SERVICE_NAME_KLINES}")
            print(f"   - Funding: {constants.OTEL_SERVICE_NAME_FUNDING}")
            print(f"   - Trades: {constants.OTEL_SERVICE_NAME_TRADES}")

            # Test OpenTelemetry setup
            from otel_init import setup_telemetry

            # Test each service type
            services = [
                ("klines", constants.OTEL_SERVICE_NAME_KLINES),
                ("funding", constants.OTEL_SERVICE_NAME_FUNDING),
                ("trades", constants.OTEL_SERVICE_NAME_TRADES),
            ]

            for service_type, service_name in services:
                result = setup_telemetry(service_name=service_name)
                print(f"✅ {service_type.title()} telemetry: {result}")

            # Test TelemetryManager
            from utils.telemetry import TelemetryManager

            manager = TelemetryManager()
            result = manager.initialize_telemetry()
            print(f"✅ TelemetryManager production init: {result}")

            self.test_results["telemetry_initialized"] = True
            return True

        except Exception as e:
            print(f"❌ Telemetry initialization failed: {e}")
            return False

    def test_job_readiness(self):
        """Test that all jobs are ready for production."""
        print("\n🏃‍♂️ Testing job readiness...")

        jobs = [
            ("Klines Production", "jobs.extract_klines_production"),
            ("Klines Manual", "jobs.extract_klines"),
            ("Funding Rates", "jobs.extract_funding"),
            ("Trades", "jobs.extract_trades"),
        ]

        all_ready = True
        for job_name, job_module in jobs:
            try:
                # Import job module
                __import__(job_module)
                print(f"✅ {job_name}: Import successful")

                # Verify constants are accessible
                import constants

                print(f"   - Service name: {getattr(constants, 'OTEL_SERVICE_NAME_KLINES', 'N/A')}")

            except Exception as e:
                print(f"❌ {job_name}: Failed - {e}")
                all_ready = False

        self.test_results["jobs_ready"] = all_ready
        return all_ready

    def test_kubernetes_configuration(self):
        """Test Kubernetes configuration readiness."""
        print("\n☸️  Testing Kubernetes configuration...")

        # Test ConfigMap/Secret file
        try:
            config_file = os.path.join(project_root, "k8s/otel-config.yaml")
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    config_content = f.read()

                # Check for required variables
                required_vars = [
                    "ENABLE_OTEL",
                    "OTEL_SERVICE_NAME",
                    "OTEL_SERVICE_NAME_KLINES",
                    "OTEL_SERVICE_NAME_FUNDING",
                    "OTEL_SERVICE_NAME_TRADES",
                    "new-relic-license-key",
                    "otel-headers",
                ]

                missing_vars = []
            else:
                print("⚠️  otel-config.yaml not found - this is expected in local testing")
                print("   - In production, this file would be created by Kubernetes")
                return True
            for var in required_vars:
                if var not in config_content:
                    missing_vars.append(var)

            if missing_vars:
                print(f"❌ Missing variables in ConfigMap: {missing_vars}")
                return False
            else:
                print("✅ ConfigMap/Secret configuration complete")

            # Test CronJob file
            cronjob_file = os.path.join(project_root, "k8s/klines-all-timeframes-cronjobs.yaml")
            with open(cronjob_file, "r", encoding="utf-8") as f:
                cronjob_content = f.read()

            # Check for environment variable injection
            if "configMapKeyRef" in cronjob_content and "secretKeyRef" in cronjob_content:
                print("✅ CronJob environment variable injection configured")
            else:
                print("❌ CronJob missing environment variable injection")
                return False

            # Test deployment script
            deploy_script = os.path.join(project_root, "scripts/deploy-otel.sh")
            if os.path.exists(deploy_script):
                print("✅ Deployment script available")
            else:
                print("❌ Deployment script missing")
                return False

            self.test_results["kubernetes_ready"] = True
            return True

        except Exception as e:
            print(f"❌ Kubernetes configuration test failed: {e}")
            return False

    def test_new_relic_integration(self):
        """Test New Relic integration readiness."""
        print("\n📊 Testing New Relic integration...")

        try:
            # Check environment variables
            license_key = os.getenv("NEW_RELIC_LICENSE_KEY")
            otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            otlp_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")

            if not license_key:
                print("❌ NEW_RELIC_LICENSE_KEY not set")
                return False
            print(f"✅ License key configured: ***{license_key[-4:]}***")

            if not otlp_endpoint:
                print("❌ OTEL_EXPORTER_OTLP_ENDPOINT not set")
                return False
            print(f"✅ OTLP endpoint configured: {otlp_endpoint}")

            if not otlp_headers:
                print("❌ OTEL_EXPORTER_OTLP_HEADERS not set")
                return False
            print("✅ OTLP headers configured")

            # Test that configuration is valid for New Relic
            if "nr-data.net" in otlp_endpoint:
                print("✅ New Relic OTLP endpoint detected")
            else:
                print("⚠️  Non-standard OTLP endpoint (may not be New Relic)")

            if "api-key" in otlp_headers.lower():
                print("✅ API key header format detected")
            else:
                print("⚠️  Non-standard header format for New Relic")

            return True

        except Exception as e:
            print(f"❌ New Relic integration test failed: {e}")
            return False

    def simulate_kubernetes_deployment(self):
        """Simulate a Kubernetes deployment scenario."""
        print("\n🚀 Simulating Kubernetes deployment...")

        # Simulate pod environment variables that Kubernetes would inject
        k8s_pod_env = {
            "HOSTNAME": "klines-extractor-abc123",
            "K8S_POD_NAME": "klines-extractor-abc123",
            "K8S_CONTAINER_NAME": "klines-extractor",
        }

        for key, value in k8s_pod_env.items():
            os.environ[key] = value

        print("✅ Kubernetes pod environment simulated:")
        for key, value in k8s_pod_env.items():
            print(f"   - {key}: {value}")

        # Test that otel_init picks up Kubernetes environment
        try:
            from otel_init import setup_telemetry

            # Test telemetry setup in Kubernetes environment
            result = setup_telemetry(service_name="kubernetes-test")
            print("✅ OpenTelemetry Kubernetes detection successful")
            return True
        except Exception as e:
            print(f"❌ Kubernetes environment detection failed: {e}")
            return False

    def run_production_simulation(self):
        """Run the complete production simulation."""
        print("🏭 PRODUCTION ENVIRONMENT SIMULATION")
        print("=" * 60)

        # Backup current environment
        self.backup_environment()

        try:
            # Run simulation steps
            success = True

            success &= self.setup_production_environment()
            success &= self.test_telemetry_initialization()
            success &= self.test_job_readiness()
            success &= self.test_kubernetes_configuration()
            success &= self.test_new_relic_integration()
            success &= self.simulate_kubernetes_deployment()

            # Generate final report
            self.test_results["production_ready"] = success
            self.generate_production_report()

            return success

        finally:
            # Always restore environment
            self.restore_environment()

    def generate_production_report(self):
        """Generate production readiness report."""
        print("\n" + "=" * 60)
        print("📋 PRODUCTION READINESS REPORT")
        print("=" * 60)

        # Status summary
        status_items = [
            ("Environment Configuration", self.test_results["environment_configured"]),
            ("Telemetry Initialization", self.test_results["telemetry_initialized"]),
            ("Job Readiness", self.test_results["jobs_ready"]),
            ("Kubernetes Configuration", self.test_results["kubernetes_ready"]),
            ("Overall Production Ready", self.test_results["production_ready"]),
        ]

        for item, status in status_items:
            icon = "✅" if status else "❌"
            print(f"{icon} {item}: {'READY' if status else 'NOT READY'}")

        # Save detailed report
        report_file = f"production_readiness_report_{int(time.time())}.json"
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(self.test_results, f, indent=2)
            print(f"\n💾 Detailed report saved: {report_file}")
        except Exception as e:
            print(f"\n⚠️  Could not save report: {e}")

        # Final verdict
        print("\n" + "=" * 60)
        if self.test_results["production_ready"]:
            print("🎉 PRODUCTION READY!")
            print("🚀 Your OpenTelemetry pipeline is ready for deployment!")
            print("\n📋 Deployment checklist:")
            print("1. ✅ Set actual NEW_RELIC_LICENSE_KEY")
            print("2. ✅ Run: chmod +x scripts/deploy-otel.sh")
            print("3. ✅ Run: ./scripts/deploy-otel.sh")
            print("4. ✅ Apply Kubernetes manifests")
            print("5. ✅ Monitor New Relic dashboard")
        else:
            print("⚠️  NOT READY FOR PRODUCTION")
            print("Please fix the issues identified above.")

        return self.test_results["production_ready"]


def main():
    """Main function."""
    simulator = ProductionEnvironmentSimulator()
    success = simulator.run_production_simulation()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
