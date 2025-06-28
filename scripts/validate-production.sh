#!/bin/bash

# Production Validation Script
# Validates that all components are ready for production deployment

echo "🔍 Validating Petrosa Binance Data Extractor for Production..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

# Function to print colored output
print_check() {
    if [ "$2" = "PASS" ]; then
        echo -e "${GREEN}✅ $1${NC}"
        ((CHECKS_PASSED++))
    elif [ "$2" = "FAIL" ]; then
        echo -e "${RED}❌ $1${NC}"
        ((CHECKS_FAILED++))
    elif [ "$2" = "WARN" ]; then
        echo -e "${YELLOW}⚠️  $1${NC}"
        ((WARNINGS++))
    else
        echo -e "${BLUE}ℹ️  $1${NC}"
    fi
}

print_section() {
    echo ""
    echo -e "${BLUE}=== $1 ===${NC}"
}

# 1. Validate File Structure
print_section "File Structure Validation"

# Check main files
if [ -f "constants.py" ]; then
    print_check "constants.py exists" "PASS"
else
    print_check "constants.py missing" "FAIL"
fi

if [ -f "requirements.txt" ]; then
    print_check "requirements.txt exists" "PASS"
else
    print_check "requirements.txt missing" "FAIL"
fi

if [ -f "Dockerfile" ]; then
    print_check "Dockerfile exists" "PASS"
else
    print_check "Dockerfile missing" "FAIL"
fi

# Check directories
for dir in models db fetchers utils jobs config k8s scripts tests; do
    if [ -d "$dir" ]; then
        print_check "Directory $dir exists" "PASS"
    else
        print_check "Directory $dir missing" "FAIL"
    fi
done

# 2. Validate Configuration
print_section "Configuration Validation"

if [ -f "config/symbols.py" ]; then
    print_check "Symbol configuration exists" "PASS"
    
    # Check for production symbols
    if grep -q "PRODUCTION_SYMBOLS" config/symbols.py; then
        print_check "Production symbols defined" "PASS"
        symbol_count=$(grep -A 50 "PRODUCTION_SYMBOLS = \[" config/symbols.py | grep '".*USDT"' | wc -l)
        if [ "$symbol_count" -gt 10 ]; then
            print_check "Production symbols ($symbol_count symbols)" "PASS"
        else
            print_check "Limited production symbols ($symbol_count symbols)" "WARN"
        fi
    else
        print_check "Production symbols not defined" "FAIL"
    fi
else
    print_check "Symbol configuration missing" "FAIL"
fi

if [ -f ".env.example" ]; then
    print_check ".env.example exists" "PASS"
else
    print_check ".env.example missing" "WARN"
fi

# 3. Validate Kubernetes Manifests
print_section "Kubernetes Manifests Validation"

if [ -f "k8s/klines-all-timeframes-cronjobs.yaml" ]; then
    print_check "All timeframes CronJobs manifest exists" "PASS"
    
    # Check for all timeframes
    for timeframe in m5 m15 m30 h1 d1; do
        if grep -q "binance-klines-${timeframe}-production" k8s/klines-all-timeframes-cronjobs.yaml; then
            print_check "CronJob for $timeframe timeframe defined" "PASS"
        else
            print_check "CronJob for $timeframe timeframe missing" "FAIL"
        fi
    done
else
    print_check "All timeframes CronJobs manifest missing" "FAIL"
fi

if [ -f "k8s/job.yaml" ]; then
    print_check "Manual job manifest exists" "PASS"
else
    print_check "Manual job manifest missing" "WARN"
fi

if [ -f "k8s/secrets-example.yaml" ]; then
    print_check "Secrets example exists" "PASS"
else
    print_check "Secrets example missing" "WARN"
fi

# 4. Validate Production Scripts
print_section "Production Scripts Validation"

if [ -f "scripts/deploy-production.sh" ]; then
    print_check "Production deployment script exists" "PASS"
    if [ -x "scripts/deploy-production.sh" ]; then
        print_check "Production deployment script is executable" "PASS"
    else
        print_check "Production deployment script not executable" "WARN"
    fi
else
    print_check "Production deployment script missing" "FAIL"
fi

if [ -f "scripts/encode_secrets.py" ]; then
    print_check "Secret encoding script exists" "PASS"
else
    print_check "Secret encoding script missing" "WARN"
fi

# 5. Validate CI/CD Pipeline
print_section "CI/CD Pipeline Validation"

if [ -f ".github/workflows/ci-cd.yml" ]; then
    print_check "GitHub Actions workflow exists" "PASS"
    
    # Check for key workflow steps
    if grep -q "docker/build-push-action" .github/workflows/ci-cd.yml; then
        print_check "Docker build step configured" "PASS"
    else
        print_check "Docker build step missing" "FAIL"
    fi
    
    if grep -q "kubectl apply" .github/workflows/ci-cd.yml; then
        print_check "Kubernetes deployment step configured" "PASS"
    else
        print_check "Kubernetes deployment step missing" "FAIL"
    fi
    
    if grep -q "klines-all-timeframes-cronjobs.yaml" .github/workflows/ci-cd.yml; then
        print_check "All timeframes deployment configured" "PASS"
    else
        print_check "All timeframes deployment not configured" "WARN"
    fi
else
    print_check "GitHub Actions workflow missing" "FAIL"
fi

# 6. Validate Production Jobs
print_section "Production Jobs Validation"

if [ -f "jobs/extract_klines_production.py" ]; then
    print_check "Production extractor exists" "PASS"
    
    # Check for key features
    if grep -q "get_symbols_for_environment" jobs/extract_klines_production.py; then
        print_check "Environment-based symbol selection" "PASS"
    else
        print_check "Environment-based symbol selection missing" "WARN"
    fi
    
    if grep -q "ThreadPoolExecutor" jobs/extract_klines_production.py; then
        print_check "Parallel processing capability" "PASS"
    else
        print_check "Parallel processing capability missing" "WARN"
    fi
else
    print_check "Production extractor missing" "FAIL"
fi

# 7. Validate Documentation
print_section "Documentation Validation"

docs=("README.md" "DEPLOYMENT_GUIDE.md" "OPERATIONS_GUIDE.md" "PRODUCTION_SUMMARY.md" "PRODUCTION_READINESS.md")
for doc in "${docs[@]}"; do
    if [ -f "$doc" ]; then
        print_check "$doc exists" "PASS"
    else
        print_check "$doc missing" "WARN"
    fi
done

# 8. Validate Python Dependencies
print_section "Python Dependencies Validation"

if command -v python3 &> /dev/null; then
    print_check "Python 3 available" "PASS"
    python_version=$(python3 --version | cut -d' ' -f2)
    print_check "Python version: $python_version" "INFO"
else
    print_check "Python 3 not available" "FAIL"
fi

if [ -f "requirements.txt" ]; then
    # Check for key dependencies
    key_deps=("pydantic" "binance-connector" "pymongo" "pymysql" "kubernetes")
    for dep in "${key_deps[@]}"; do
        if grep -q "$dep" requirements.txt; then
            print_check "Dependency $dep included" "PASS"
        else
            print_check "Dependency $dep missing" "WARN"
        fi
    done
fi

# 9. Production Readiness Check
print_section "Production Readiness Summary"

echo ""
echo -e "${BLUE}📊 Validation Results:${NC}"
echo "  ✅ Checks Passed: $CHECKS_PASSED"
echo "  ⚠️  Warnings: $WARNINGS"
echo "  ❌ Checks Failed: $CHECKS_FAILED"

echo ""
if [ $CHECKS_FAILED -eq 0 ]; then
    if [ $WARNINGS -eq 0 ]; then
        echo -e "${GREEN}🎉 PRODUCTION READY! All validations passed.${NC}"
        echo ""
        echo -e "${BLUE}Next Steps:${NC}"
        echo "  1. Create Kubernetes secrets with your credentials"
        echo "  2. Run: ./scripts/deploy-production.sh"
        echo "  3. Monitor: kubectl get cronjobs -l app=binance-extractor"
        echo ""
        echo -e "${BLUE}Documentation:${NC}"
        echo "  📋 PRODUCTION_READINESS.md - Pre-deployment checklist"
        echo "  🔧 OPERATIONS_GUIDE.md - Operations and monitoring"
        echo "  🚀 DEPLOYMENT_GUIDE.md - Deployment instructions"
        exit 0
    else
        echo -e "${YELLOW}⚠️  PRODUCTION READY WITH WARNINGS${NC}"
        echo "Consider addressing the warnings above for optimal production deployment."
        exit 0
    fi
else
    echo -e "${RED}❌ NOT PRODUCTION READY${NC}"
    echo "Please fix the failed checks above before deploying to production."
    exit 1
fi
