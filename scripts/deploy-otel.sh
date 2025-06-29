#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="petrosa-apps"
CLUSTER_NAME="your-cluster-name"  # Update this with your actual cluster name

echo -e "${BLUE}🔧 Deploying OpenTelemetry Configuration for Binance Data Extractor${NC}"
echo "=============================================================="

# Function to check if required tools are installed
check_prerequisites() {
    echo -e "${BLUE}📋 Checking prerequisites...${NC}"
    
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl is not installed or not in PATH${NC}"
        exit 1
    fi
    
    if ! command -v base64 &> /dev/null; then
        echo -e "${RED}❌ base64 is not installed or not in PATH${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Prerequisites satisfied${NC}"
}

# Function to validate New Relic license key
validate_license_key() {
    if [ -z "$NEW_RELIC_LICENSE_KEY" ]; then
        echo -e "${RED}❌ NEW_RELIC_LICENSE_KEY environment variable is required${NC}"
        echo "Please set it with: export NEW_RELIC_LICENSE_KEY=your-license-key"
        exit 1
    fi
    
    # Basic validation (New Relic license keys are typically 40 characters)
    if [ ${#NEW_RELIC_LICENSE_KEY} -lt 30 ]; then
        echo -e "${YELLOW}⚠️  Warning: License key seems too short. Please verify it's correct.${NC}"
    fi
    
    echo -e "${GREEN}✅ New Relic license key validated${NC}"
}

# Function to create namespace if it doesn't exist
create_namespace() {
    echo -e "${BLUE}🔧 Creating namespace: $NAMESPACE${NC}"
    
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        echo -e "${YELLOW}⚠️  Namespace $NAMESPACE already exists${NC}"
    else
        kubectl create namespace "$NAMESPACE"
        echo -e "${GREEN}✅ Namespace $NAMESPACE created${NC}"
    fi
}

# Function to update OpenTelemetry configuration
update_otel_config() {
    echo -e "${BLUE}🔧 Updating OpenTelemetry configuration...${NC}"
    
    # Update cluster name in the ConfigMap
    sed -i.bak "s/your-cluster-name/$CLUSTER_NAME/g" k8s/otel-config.yaml
    
    # Apply OpenTelemetry ConfigMap and Secrets
    kubectl apply -f k8s/otel-config.yaml
    
    # Create OTLP headers with the license key
    OTEL_HEADERS="api-key=$NEW_RELIC_LICENSE_KEY"
    OTEL_HEADERS_BASE64=$(echo -n "$OTEL_HEADERS" | base64)
    
    # Update the secret with the actual license key
    kubectl patch secret otel-secrets -n "$NAMESPACE" \
        --patch="{\"data\":{\"new-relic-license-key\":\"$(echo -n "$NEW_RELIC_LICENSE_KEY" | base64)\"}}"
    
    kubectl patch secret otel-secrets -n "$NAMESPACE" \
        --patch="{\"data\":{\"otel-headers\":\"$OTEL_HEADERS_BASE64\"}}"
    
    echo -e "${GREEN}✅ OpenTelemetry configuration updated${NC}"
}

# Function to deploy CronJobs with OpenTelemetry
deploy_cronjobs() {
    echo -e "${BLUE}🚀 Deploying CronJobs with OpenTelemetry support...${NC}"
    
    # Apply the updated CronJobs
    kubectl apply -f k8s/klines-all-timeframes-cronjobs.yaml
    
    echo -e "${GREEN}✅ CronJobs deployed${NC}"
}

# Function to verify deployment
verify_deployment() {
    echo -e "${BLUE}🔍 Verifying deployment...${NC}"
    
    # Check ConfigMap
    if kubectl get configmap otel-config -n "$NAMESPACE" &> /dev/null; then
        echo -e "${GREEN}✅ OpenTelemetry ConfigMap exists${NC}"
    else
        echo -e "${RED}❌ OpenTelemetry ConfigMap not found${NC}"
        return 1
    fi
    
    # Check Secret
    if kubectl get secret otel-secrets -n "$NAMESPACE" &> /dev/null; then
        echo -e "${GREEN}✅ OpenTelemetry Secret exists${NC}"
    else
        echo -e "${RED}❌ OpenTelemetry Secret not found${NC}"
        return 1
    fi
    
    # Check CronJobs
    local cronjobs=(
        "binance-klines-m5-production"
        "binance-klines-m15-production"
        "binance-klines-m30-production"
        "binance-klines-h1-production"
        "binance-klines-d1-production"
    )
    
    for cronjob in "${cronjobs[@]}"; do
        if kubectl get cronjob "$cronjob" -n "$NAMESPACE" &> /dev/null; then
            echo -e "${GREEN}✅ CronJob $cronjob exists${NC}"
        else
            echo -e "${YELLOW}⚠️  CronJob $cronjob not found${NC}"
        fi
    done
    
    # Display recent logs from a job to verify OpenTelemetry
    echo -e "${BLUE}📊 Checking recent job logs for OpenTelemetry initialization...${NC}"
    
    local recent_job=$(kubectl get jobs -n "$NAMESPACE" -l app=binance-extractor --sort-by=.metadata.creationTimestamp | tail -1 | awk '{print $1}')
    
    if [ -n "$recent_job" ] && [ "$recent_job" != "NAME" ]; then
        echo -e "${BLUE}📋 Recent job: $recent_job${NC}"
        kubectl logs "job/$recent_job" -n "$NAMESPACE" --tail=10 | grep -E "(telemetry|OpenTelemetry|OTEL)" || true
    fi
}

# Function to show monitoring information
show_monitoring_info() {
    echo -e "${BLUE}📊 OpenTelemetry Monitoring Information${NC}"
    echo "=============================================="
    echo -e "${YELLOW}New Relic Configuration:${NC}"
    echo "• Endpoint: https://otlp.nr-data.net:4317"
    echo "• Protocol: OTLP/gRPC"
    echo "• Data Types: Traces, Metrics, Logs"
    echo ""
    echo -e "${YELLOW}Service Information:${NC}"
    echo "• Service Name: binance-extractor"
    echo "• Service Version: 2.0.0"
    echo "• Environment: production"
    echo "• Cluster: $CLUSTER_NAME"
    echo ""
    echo -e "${YELLOW}Kubernetes Labels:${NC}"
    echo "• app=binance-extractor"
    echo "• component=klines-extractor"
    echo "• interval=[m5|m15|m30|h1|d1]"
    echo ""
    echo -e "${GREEN}🎉 Visit New Relic to see your telemetry data!${NC}"
    echo "https://one.newrelic.com/nr1-core"
}

# Main execution
main() {
    echo -e "${GREEN}Starting OpenTelemetry deployment for Binance Data Extractor...${NC}"
    
    check_prerequisites
    validate_license_key
    create_namespace
    update_otel_config
    deploy_cronjobs
    verify_deployment
    show_monitoring_info
    
    echo ""
    echo -e "${GREEN}🎉 OpenTelemetry deployment completed successfully!${NC}"
    echo -e "${BLUE}Your Binance data extractor now has comprehensive observability with New Relic.${NC}"
}

# Help function
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Environment Variables:"
    echo "  NEW_RELIC_LICENSE_KEY    Your New Relic license key (required)"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -c, --cluster-name      Set the Kubernetes cluster name (default: your-cluster-name)"
    echo ""
    echo "Example:"
    echo "  export NEW_RELIC_LICENSE_KEY=your-license-key"
    echo "  $0 --cluster-name my-production-cluster"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--cluster-name)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Run main function
main
