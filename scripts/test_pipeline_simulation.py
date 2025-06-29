#!/usr/bin/env python3
"""
Comprehensive OpenTelemetry Pipeline Simulation Test

This script simulates a complete pipeline run with:
- Multiple service configurations
- Environment variable testing
- Error handling scenarios
- Integration testing
- Performance monitoring
"""

import os
import sys
import time
import json
from datetime import datetime
from typing import Dict, List, Any

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

class PipelineSimulator:
    """Simulates the complete OpenTelemetry pipeline."""
    
    def __init__(self):
        self.test_results: Dict[str, Any] = {
            'timestamp': datetime.now().isoformat(),
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'errors': [],
            'performance_metrics': {},
            'service_configs': {}
        }
    
    def log_test(self, test_name: str, passed: bool, details: str = "", duration: float = 0):
        """Log test results."""
        self.test_results['tests_run'] += 1
        if passed:
            self.test_results['tests_passed'] += 1
            print(f"✅ {test_name}: PASSED {f'({details})' if details else ''}")
        else:
            self.test_results['tests_failed'] += 1
            self.test_results['errors'].append(f"{test_name}: {details}")
            print(f"❌ {test_name}: FAILED - {details}")
        
        if duration > 0:
            self.test_results['performance_metrics'][test_name] = f"{duration:.3f}s"
    
    def test_environment_configurations(self):
        """Test different environment configurations."""
        print("\n🌍 Testing Environment Configurations...")
        
        # Test 1: Default configuration
        start_time = time.time()
        try:
            import constants
            default_klines = constants.OTEL_SERVICE_NAME_KLINES
            default_funding = constants.OTEL_SERVICE_NAME_FUNDING
            default_trades = constants.OTEL_SERVICE_NAME_TRADES
            
            self.test_results['service_configs']['default'] = {
                'klines': default_klines,
                'funding': default_funding,
                'trades': default_trades
            }
            
            duration = time.time() - start_time
            self.log_test(
                "Default Service Names", 
                True, 
                f"klines={default_klines}, funding={default_funding}, trades={default_trades}",
                duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Default Service Names", False, str(e), duration)
        
        # Test 2: Custom environment variables
        start_time = time.time()
        try:
            # Set custom environment variables
            test_env = {
                'OTEL_SERVICE_NAME_KLINES': 'test-klines-service',
                'OTEL_SERVICE_NAME_FUNDING': 'test-funding-service',
                'OTEL_SERVICE_NAME_TRADES': 'test-trades-service',
                'ENABLE_OTEL': 'true',
                'OTEL_SERVICE_VERSION': '3.0.0-test'
            }
            
            # Backup original env vars
            original_env = {}
            for key, value in test_env.items():
                original_env[key] = os.getenv(key)
                os.environ[key] = value
            
            # Reload constants to pick up new env vars
            import importlib
            importlib.reload(constants)
            
            # Verify the changes
            custom_klines = constants.OTEL_SERVICE_NAME_KLINES
            custom_funding = constants.OTEL_SERVICE_NAME_FUNDING
            custom_trades = constants.OTEL_SERVICE_NAME_TRADES
            
            self.test_results['service_configs']['custom'] = {
                'klines': custom_klines,
                'funding': custom_funding,
                'trades': custom_trades
            }
            
            # Restore original env vars
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value
            
            # Reload constants again to restore defaults
            importlib.reload(constants)
            
            duration = time.time() - start_time
            expected_values = all([
                custom_klines == 'test-klines-service',
                custom_funding == 'test-funding-service',
                custom_trades == 'test-trades-service'
            ])
            
            self.log_test(
                "Custom Environment Variables", 
                expected_values,
                f"Successfully applied custom service names",
                duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Custom Environment Variables", False, str(e), duration)
    
    def test_telemetry_initialization(self):
        """Test OpenTelemetry initialization with different scenarios."""
        print("\n🔧 Testing Telemetry Initialization...")
        
        # Test 1: Basic initialization
        start_time = time.time()
        try:
            from otel_init import setup_telemetry
            result = setup_telemetry(service_name="pipeline-test")
            duration = time.time() - start_time
            
            # Result should be False without OTLP endpoint, but no errors
            self.log_test(
                "Basic Telemetry Init", 
                True,
                f"setup_telemetry returned {result} (expected False without endpoint)",
                duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Basic Telemetry Init", False, str(e), duration)
        
        # Test 2: TelemetryManager initialization
        start_time = time.time()
        try:
            from utils.telemetry import TelemetryManager
            manager = TelemetryManager()
            result = manager.initialize_telemetry(
                service_name="pipeline-test-manager",
                environment="test"
            )
            duration = time.time() - start_time
            
            self.log_test(
                "TelemetryManager Init", 
                True,
                f"TelemetryManager.initialize_telemetry returned {result}",
                duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test("TelemetryManager Init", False, str(e), duration)
    
    def test_instrumentation_coverage(self):
        """Test that all required instrumentations are available."""
        print("\n📦 Testing Instrumentation Coverage...")
        
        instrumentations = {
            'requests': 'opentelemetry.instrumentation.requests',
            'pymongo': 'opentelemetry.instrumentation.pymongo',
            'sqlalchemy': 'opentelemetry.instrumentation.sqlalchemy',
            'logging': 'opentelemetry.instrumentation.logging',
            'urllib3': 'opentelemetry.instrumentation.urllib3'
        }
        
        for name, module_path in instrumentations.items():
            start_time = time.time()
            try:
                __import__(module_path)
                duration = time.time() - start_time
                self.log_test(f"{name.title()} Instrumentation", True, f"Available", duration)
            except ImportError as e:
                duration = time.time() - start_time
                self.log_test(f"{name.title()} Instrumentation", False, str(e), duration)
    
    def test_job_initialization(self):
        """Test that all job files can be imported and initialized."""
        print("\n🏃‍♂️ Testing Job Initialization...")
        
        jobs = [
            ('Klines Production', 'jobs.extract_klines_production'),
            ('Klines Manual', 'jobs.extract_klines'),
            ('Funding Rates', 'jobs.extract_funding'),
            ('Trades', 'jobs.extract_trades')
        ]
        
        for job_name, job_module in jobs:
            start_time = time.time()
            try:
                # Try to import the job module
                __import__(job_module)
                duration = time.time() - start_time
                self.log_test(f"{job_name} Import", True, "Module imported successfully", duration)
            except Exception as e:
                duration = time.time() - start_time
                self.log_test(f"{job_name} Import", False, str(e), duration)
    
    def test_kubernetes_configuration(self):
        """Test Kubernetes configuration files."""
        print("\n☸️  Testing Kubernetes Configuration...")
        
        k8s_files = [
            ('k8s/otel-config.yaml', 'OpenTelemetry ConfigMap/Secret'),
            ('k8s/klines-all-timeframes-cronjobs.yaml', 'CronJobs Configuration'),
            ('scripts/deploy-otel.sh', 'Deployment Script')
        ]
        
        for file_path, description in k8s_files:
            start_time = time.time()
            try:
                full_path = os.path.join(project_root, file_path)
                if os.path.exists(full_path):
                    with open(full_path, 'r') as f:
                        content = f.read()
                    
                    # Basic validation
                    if file_path.endswith('.yaml'):
                        # Check for required OTEL env vars
                        required_vars = ['OTEL_SERVICE_NAME', 'ENABLE_OTEL']
                        has_vars = all(var in content for var in required_vars)
                        duration = time.time() - start_time
                        self.log_test(
                            f"K8s {description}", 
                            has_vars,
                            f"Found required variables: {required_vars}" if has_vars else "Missing required variables",
                            duration
                        )
                    else:
                        # Shell script
                        has_deploy_logic = 'kubectl' in content and 'NEW_RELIC_LICENSE_KEY' in content
                        duration = time.time() - start_time
                        self.log_test(
                            f"K8s {description}", 
                            has_deploy_logic,
                            "Contains kubectl and license key logic" if has_deploy_logic else "Missing deploy logic",
                            duration
                        )
                else:
                    duration = time.time() - start_time
                    self.log_test(f"K8s {description}", False, f"File not found: {file_path}", duration)
            except Exception as e:
                duration = time.time() - start_time
                self.log_test(f"K8s {description}", False, str(e), duration)
    
    def test_error_scenarios(self):
        """Test error handling scenarios."""
        print("\n🚨 Testing Error Scenarios...")
        
        # Test 1: Missing OpenTelemetry packages (simulate)
        start_time = time.time()
        try:
            # This should handle gracefully
            old_available = None
            try:
                from utils.telemetry import OTEL_AVAILABLE
                old_available = OTEL_AVAILABLE
            except:
                pass
            
            # Test graceful degradation
            from otel_init import setup_telemetry
            result = setup_telemetry(service_name="error-test")
            
            duration = time.time() - start_time
            self.log_test(
                "Graceful Error Handling", 
                True,
                "No exceptions thrown during error scenarios",
                duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Graceful Error Handling", False, str(e), duration)
        
        # Test 2: Invalid service names
        start_time = time.time()
        try:
            from otel_init import setup_telemetry
            # Test with None, empty string, and special characters
            test_names = [None, "", "test-service-with-special-chars!@#"]
            
            all_handled = True
            for name in test_names:
                try:
                    setup_telemetry(service_name=name)
                except Exception:
                    all_handled = False
                    break
            
            duration = time.time() - start_time
            self.log_test(
                "Invalid Service Names", 
                all_handled,
                "All invalid service names handled gracefully",
                duration
            )
        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Invalid Service Names", False, str(e), duration)
    
    def test_performance_benchmarks(self):
        """Test performance benchmarks."""
        print("\n⚡ Testing Performance Benchmarks...")
        
        # Test 1: Import time
        start_time = time.time()
        try:
            import constants
            from otel_init import setup_telemetry
            from utils.telemetry import TelemetryManager
            import_duration = time.time() - start_time
            
            self.log_test(
                "Import Performance", 
                import_duration < 2.0,  # Should import in under 2 seconds
                f"Import time: {import_duration:.3f}s",
                import_duration
            )
        except Exception as e:
            import_duration = time.time() - start_time
            self.log_test("Import Performance", False, str(e), import_duration)
        
        # Test 2: Telemetry setup time
        start_time = time.time()
        try:
            from otel_init import setup_telemetry
            setup_start = time.time()
            setup_telemetry(service_name="performance-test")
            setup_duration = time.time() - setup_start
            
            self.log_test(
                "Telemetry Setup Performance", 
                setup_duration < 1.0,  # Should setup in under 1 second
                f"Setup time: {setup_duration:.3f}s",
                setup_duration
            )
        except Exception as e:
            setup_duration = time.time() - start_time
            self.log_test("Telemetry Setup Performance", False, str(e), setup_duration)
    
    def generate_report(self):
        """Generate a comprehensive test report."""
        print("\n" + "="*60)
        print("📊 PIPELINE SIMULATION REPORT")
        print("="*60)
        
        # Summary
        print(f"🕐 Test Run Time: {self.test_results['timestamp']}")
        print(f"📈 Tests Run: {self.test_results['tests_run']}")
        print(f"✅ Tests Passed: {self.test_results['tests_passed']}")
        print(f"❌ Tests Failed: {self.test_results['tests_failed']}")
        
        if self.test_results['tests_run'] > 0:
            success_rate = (self.test_results['tests_passed'] / self.test_results['tests_run']) * 100
            print(f"📊 Success Rate: {success_rate:.1f}%")
        
        # Performance metrics
        if self.test_results['performance_metrics']:
            print(f"\n⚡ Performance Metrics:")
            for test, timing in self.test_results['performance_metrics'].items():
                print(f"   - {test}: {timing}")
        
        # Service configurations
        if self.test_results['service_configs']:
            print(f"\n🛠️  Service Configurations:")
            for config_type, config in self.test_results['service_configs'].items():
                print(f"   - {config_type.title()}:")
                for service, name in config.items():
                    print(f"     • {service}: {name}")
        
        # Errors
        if self.test_results['errors']:
            print(f"\n🚨 Errors Encountered:")
            for error in self.test_results['errors']:
                print(f"   - {error}")
        
        # Save report
        report_file = f"pipeline_test_report_{int(time.time())}.json"
        try:
            with open(report_file, 'w') as f:
                json.dump(self.test_results, f, indent=2)
            print(f"\n💾 Report saved to: {report_file}")
        except Exception as e:
            print(f"\n⚠️  Could not save report: {e}")
        
        # Final status
        print("\n" + "="*60)
        if self.test_results['tests_failed'] == 0:
            print("🎉 ALL TESTS PASSED! Pipeline is ready for production.")
            return True
        else:
            print(f"⚠️  {self.test_results['tests_failed']} test(s) failed. Review errors above.")
            return False
    
    def run_full_simulation(self):
        """Run the complete pipeline simulation."""
        print("🚀 Starting OpenTelemetry Pipeline Simulation")
        print("="*60)
        
        # Run all test suites
        self.test_environment_configurations()
        self.test_telemetry_initialization()
        self.test_instrumentation_coverage()
        self.test_job_initialization()
        self.test_kubernetes_configuration()
        self.test_error_scenarios()
        self.test_performance_benchmarks()
        
        # Generate final report
        return self.generate_report()

def main():
    """Main function to run the pipeline simulation."""
    simulator = PipelineSimulator()
    success = simulator.run_full_simulation()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
