#!/bin/bash

# Deployment Validation Script
# This script validates deployment configuration before CI/CD

set -e

echo "🔍 Validating deployment configuration..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "OK")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
        "WARN")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            exit 1
            ;;
    esac
}

# Check if we're in the right directory
if [ ! -f "k8s/deployment.yaml" ]; then
    print_status "ERROR" "Not in the correct directory. Run this script from the project root."
    exit 1
fi

echo "📋 Running validation checks..."

# 1. Check for VERSION_PLACEHOLDER usage
echo "1. Checking VERSION_PLACEHOLDER usage..."
VERSION_PLACEHOLDER_COUNT=$(grep -r "VERSION_PLACEHOLDER" k8s/ | wc -l || echo "0")
if [ "$VERSION_PLACEHOLDER_COUNT" -gt 0 ]; then
    print_status "OK" "Found $VERSION_PLACEHOLDER_COUNT VERSION_PLACEHOLDER references (correct)"
else
    print_status "ERROR" "No VERSION_PLACEHOLDER found. This will break CI/CD!"
fi

# 2. Check for manual version replacements
echo "2. Checking for manual version replacements..."
MANUAL_VERSION_COUNT=$(grep -r "v[0-9]\+\.[0-9]\+\.[0-9]\+" k8s/ | grep -v "VERSION_PLACEHOLDER" | wc -l || echo "0")
if [ "$MANUAL_VERSION_COUNT" -eq 0 ]; then
    print_status "OK" "No manual version replacements found"
else
    print_status "ERROR" "Found $MANUAL_VERSION_COUNT manual version replacements. Remove these!"
    grep -r "v[0-9]\+\.[0-9]\+\.[0-9]\+" k8s/ | grep -v "VERSION_PLACEHOLDER"
fi

# 3. Check image name consistency
echo "3. Checking image name consistency..."
CI_IMAGE_NAME=$(grep -r "images:" .github/workflows/deploy.yml | head -1 | sed 's/.*images: //' | sed 's/.*\///')
K8S_IMAGE_NAME=$(grep -r "image:" k8s/*.yaml | head -1 | sed 's/.*image: //' | sed 's/:.*//' | sed 's/.*\///')

# Handle CI/CD variable substitution
CI_IMAGE_NAME=$(echo "$CI_IMAGE_NAME" | sed 's/\${{.*}}//' | sed 's/\/$//')

if [ "$CI_IMAGE_NAME" = "$K8S_IMAGE_NAME" ]; then
    print_status "OK" "Image names are consistent: $CI_IMAGE_NAME"
else
    print_status "ERROR" "Image name mismatch: CI=$CI_IMAGE_NAME, K8S=$K8S_IMAGE_NAME"
fi

# 4. Check configmap keys
echo "4. Checking configmap keys..."
if [ -f "k8s/configmap.yaml" ]; then
    # Extract keys from service-specific configmap
    SERVICE_CONFIGMAP_KEYS=$(grep -A 100 "data:" k8s/configmap.yaml | grep ":" | grep -v "data:" | sed 's/^[[:space:]]*//' | sed 's/:.*//' | sort)

    # Extract keys referenced in deployment from service-specific configmap
    SERVICE_DEPLOYMENT_KEYS=$(grep -A 200 "env:" k8s/deployment.yaml | grep -A 1 "petrosa-binance-data-extractor-config" | grep "key:" | sed 's/.*key: //' | sort | uniq)

    # Check for missing keys in service-specific configmap
    MISSING_SERVICE_KEYS=""
    for key in $SERVICE_DEPLOYMENT_KEYS; do
        if ! echo "$SERVICE_CONFIGMAP_KEYS" | grep -q "^$key$"; then
            MISSING_SERVICE_KEYS="$MISSING_SERVICE_KEYS $key"
        fi
    done

    if [ -z "$MISSING_SERVICE_KEYS" ]; then
        print_status "OK" "All service-specific configmap keys exist"
    else
        print_status "ERROR" "Missing service-specific configmap keys:$MISSING_SERVICE_KEYS"
    fi

    # Check for common configmap references (these should exist in common configmap)
    COMMON_CONFIGMAP_KEYS=$(grep -A 200 "env:" k8s/deployment.yaml | grep -A 1 "petrosa-common-config" | grep "key:" | sed 's/.*key: //' | sort | uniq)
    if [ -n "$COMMON_CONFIGMAP_KEYS" ]; then
        print_status "OK" "Deployment references common configmap (expected)"
    fi

    # Check for secret references (these should exist in secrets)
    SECRET_KEYS=$(grep -A 200 "env:" k8s/deployment.yaml | grep -A 1 "petrosa-sensitive-credentials" | grep "key:" | sed 's/.*key: //' | sort | uniq)
    if [ -n "$SECRET_KEYS" ]; then
        print_status "OK" "Deployment references secrets (expected)"
    fi
else
    print_status "WARN" "Service configmap file not found"
fi

# 5. Check for required files
echo "5. Checking required files..."
REQUIRED_FILES=("k8s/deployment.yaml" "k8s/configmap.yaml" ".github/workflows/deploy.yml")
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_status "OK" "Found required file: $file"
    else
        print_status "ERROR" "Missing required file: $file"
    fi
done

# 6. Check local pipeline
echo "6. Checking local pipeline..."
if command -v make &> /dev/null; then
    if make -n pipeline &> /dev/null; then
        print_status "OK" "Local pipeline command available"
    else
        print_status "WARN" "Local pipeline command not working"
    fi
else
    print_status "WARN" "Make not available"
fi

# 7. Check Docker build
echo "7. Checking Docker build..."
if [ -f "Dockerfile" ]; then
    print_status "OK" "Dockerfile found"
else
    print_status "ERROR" "Dockerfile not found"
fi

echo ""
echo "🎯 Validation Summary:"
echo "======================"

if [ "$VERSION_PLACEHOLDER_COUNT" -gt 0 ] && [ "$MANUAL_VERSION_COUNT" -eq 0 ]; then
    print_status "OK" "✅ Ready for CI/CD deployment!"
    echo ""
    echo "📋 Next steps:"
    echo "1. git add ."
    echo "2. git commit -m 'Update configuration'"
    echo "3. git push origin main"
    echo "4. Monitor CI/CD pipeline on GitHub"
    echo "5. Verify deployment status"
else
    print_status "ERROR" "❌ Fix issues before deploying!"
    echo ""
    echo "🔧 Fix the errors above before pushing to CI/CD"
fi

echo ""
echo "📚 For more information, see:"
echo "- docs/CI_CD_BEST_PRACTICES.md"
echo "- docs/CI_CD_QUICK_REFERENCE.md"
