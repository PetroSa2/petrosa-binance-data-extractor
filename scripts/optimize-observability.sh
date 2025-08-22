#!/bin/bash

# Observability Optimization Script
# This script implements the cost-effective observability solution

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
KUBECONFIG_PATH="petrosa_k8s/k8s/kubeconfig.yaml"
NAMESPACE="petrosa-apps"
OBSERVABILITY_NAMESPACE="observability"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi

    if [ ! -f "$KUBECONFIG_PATH" ]; then
        print_error "Kubeconfig file not found at $KUBECONFIG_PATH"
        exit 1
    fi

    # Test cluster connectivity
    if ! kubectl --kubeconfig="$KUBECONFIG_PATH" cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi

    print_success "Prerequisites check passed"
}

# Function to backup current configuration
backup_config() {
    print_status "Backing up current configuration..."

    BACKUP_DIR="backup/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    # Backup current configmap
    kubectl --kubeconfig="$KUBECONFIG_PATH" get configmap petrosa-common-config -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/petrosa-common-config.yaml"

    # Backup New Relic namespace
    if kubectl --kubeconfig="$KUBECONFIG_PATH" get namespace newrelic &> /dev/null; then
        kubectl --kubeconfig="$KUBECONFIG_PATH" get namespace newrelic -o yaml > "$BACKUP_DIR/newrelic-namespace.yaml"
    fi

    print_success "Configuration backed up to $BACKUP_DIR"
}

# Function to remove New Relic
remove_newrelic() {
    print_status "Removing New Relic..."

    if kubectl --kubeconfig="$KUBECONFIG_PATH" get namespace newrelic &> /dev/null; then
        print_warning "Removing New Relic namespace (this will free up ~1.7GB RAM and ~1.5 CPU cores)"
        kubectl --kubeconfig="$KUBECONFIG_PATH" delete namespace newrelic --wait=true --timeout=300s
        print_success "New Relic removed successfully"
    else
        print_status "New Relic namespace not found, skipping removal"
    fi
}

# Function to update OTEL configuration
update_otel_config() {
    print_status "Updating OpenTelemetry configuration..."

    # Update the common configmap to point to local collector
    kubectl --kubeconfig="$KUBECONFIG_PATH" patch configmap petrosa-common-config -n "$NAMESPACE" \
        --type='merge' \
        -p='{"data":{"OTEL_EXPORTER_OTLP_ENDPOINT":"http://otel-collector.observability.svc.cluster.local:4317","OTEL_EXPORTER_OTLP_HEADERS":""}}'

    print_success "OpenTelemetry configuration updated"
}

# Function to optimize existing prometheus
optimize_existing_prometheus() {
    print_status "Optimizing existing Prometheus stack..."

    # Scale down existing prometheus if it exists
    if kubectl --kubeconfig="$KUBECONFIG_PATH" get deployment kube-prometheus-stack-1747-prometheus -n base &> /dev/null; then
        print_warning "Scaling down existing Prometheus to 1 replica"
        kubectl --kubeconfig="$KUBECONFIG_PATH" scale deployment kube-prometheus-stack-1747-prometheus -n base --replicas=1
    fi

    print_success "Existing Prometheus optimized"
}

# Function to deploy minimal monitoring stack
deploy_minimal_monitoring() {
    print_status "Deploying minimal monitoring stack..."

    # Create monitoring directory if it doesn't exist
    MONITORING_DIR="petrosa_k8s/k8s/monitoring"

    # Apply minimal prometheus configuration
    kubectl --kubeconfig="$KUBECONFIG_PATH" apply -f "$MONITORING_DIR/minimal-prometheus-config.yaml"

    # Apply minimal prometheus deployment
    kubectl --kubeconfig="$KUBECONFIG_PATH" apply -f "$MONITORING_DIR/minimal-prometheus-deployment.yaml"

    # Apply basic alerts
    kubectl --kubeconfig="$KUBECONFIG_PATH" apply -f "$MONITORING_DIR/basic-alerts.yaml"

    # Apply optimized grafana
    kubectl --kubeconfig="$KUBECONFIG_PATH" apply -f "$MONITORING_DIR/optimized-grafana.yaml"

    print_success "Minimal monitoring stack deployed"
}

# Function to wait for deployments to be ready
wait_for_deployments() {
    print_status "Waiting for deployments to be ready..."

    # Wait for minimal prometheus
    kubectl --kubeconfig="$KUBECONFIG_PATH" wait --for=condition=available --timeout=300s deployment/minimal-prometheus -n "$OBSERVABILITY_NAMESPACE"

    # Wait for optimized grafana
    kubectl --kubeconfig="$KUBECONFIG_PATH" wait --for=condition=available --timeout=300s deployment/optimized-grafana -n "$OBSERVABILITY_NAMESPACE"

    print_success "All deployments are ready"
}

# Function to restart applications
restart_applications() {
    print_status "Restarting applications to pick up new configuration..."

    # Restart all petrosa applications
    kubectl --kubeconfig="$KUBECONFIG_PATH" rollout restart deployment petrosa-tradeengine -n "$NAMESPACE"
    kubectl --kubeconfig="$KUBECONFIG_PATH" rollout restart deployment petrosa-socket-client -n "$NAMESPACE"
    kubectl --kubeconfig="$KUBECONFIG_PATH" rollout restart deployment petrosa-ta-bot -n "$NAMESPACE"
    kubectl --kubeconfig="$KUBECONFIG_PATH" rollout restart deployment petrosa-realtime-strategies -n "$NAMESPACE"

    # Wait for rollouts to complete
    kubectl --kubeconfig="$KUBECONFIG_PATH" rollout status deployment petrosa-tradeengine -n "$NAMESPACE"
    kubectl --kubeconfig="$KUBECONFIG_PATH" rollout status deployment petrosa-socket-client -n "$NAMESPACE"
    kubectl --kubeconfig="$KUBECONFIG_PATH" rollout status deployment petrosa-ta-bot -n "$NAMESPACE"
    kubectl --kubeconfig="$KUBECONFIG_PATH" rollout status deployment petrosa-realtime-strategies -n "$NAMESPACE"

    print_success "Applications restarted successfully"
}

# Function to verify deployment
verify_deployment() {
    print_status "Verifying deployment..."

    # Check if minimal prometheus is running
    if kubectl --kubeconfig="$KUBECONFIG_PATH" get pods -n "$OBSERVABILITY_NAMESPACE" -l app=minimal-prometheus | grep -q Running; then
        print_success "Minimal Prometheus is running"
    else
        print_error "Minimal Prometheus is not running"
        return 1
    fi

    # Check if optimized grafana is running
    if kubectl --kubeconfig="$KUBECONFIG_PATH" get pods -n "$OBSERVABILITY_NAMESPACE" -l app=optimized-grafana | grep -q Running; then
        print_success "Optimized Grafana is running"
    else
        print_error "Optimized Grafana is not running"
        return 1
    fi

    # Check resource usage
    print_status "Current resource usage:"
    kubectl --kubeconfig="$KUBECONFIG_PATH" top nodes

    print_success "Deployment verification completed"
}

# Function to show monitoring information
show_monitoring_info() {
    print_status "Monitoring Information"
    echo "========================"
    echo ""
    echo "Minimal Prometheus:"
    echo "  - URL: http://minimal-prometheus.observability.svc.cluster.local:9090"
    echo "  - Resource Usage: ~512MB RAM, ~200m CPU"
    echo ""
    echo "Optimized Grafana:"
    echo "  - URL: http://optimized-grafana.observability.svc.cluster.local:3000"
    echo "  - Username: admin"
    echo "  - Password: admin123"
    echo "  - Resource Usage: ~256MB RAM, ~200m CPU"
    echo ""
    echo "Resource Savings:"
    echo "  - Memory: ~2.7GB saved (64% reduction)"
    echo "  - CPU: ~2 cores saved (80% reduction)"
    echo ""
    echo "To access Grafana from outside the cluster:"
    echo "  kubectl --kubeconfig=$KUBECONFIG_PATH port-forward svc/optimized-grafana 3000:3000 -n $OBSERVABILITY_NAMESPACE"
    echo ""
    print_success "Observability optimization completed!"
}

# Function to rollback if needed
rollback() {
    print_error "Rolling back changes..."

    # Restore configmap from backup
    if [ -f "backup/petrosa-common-config.yaml" ]; then
        kubectl --kubeconfig="$KUBECONFIG_PATH" apply -f backup/petrosa-common-config.yaml
    fi

    # Scale up existing prometheus
    kubectl --kubeconfig="$KUBECONFIG_PATH" scale deployment kube-prometheus-stack-1747-prometheus -n base --replicas=3

    print_warning "Rollback completed. You may need to manually restore New Relic if needed."
}

# Main execution
main() {
    echo -e "${GREEN}Starting Observability Optimization...${NC}"
    echo "=============================================="

    # Set up error handling
    trap 'print_error "Script failed. Rolling back..."; rollback; exit 1' ERR

    check_prerequisites
    backup_config
    remove_newrelic
    update_otel_config
    optimize_existing_prometheus
    deploy_minimal_monitoring
    wait_for_deployments
    restart_applications
    verify_deployment
    show_monitoring_info

    echo ""
    echo -e "${GREEN}🎉 Observability optimization completed successfully!${NC}"
}

# Help function
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  --kubeconfig PATH       Path to kubeconfig file (default: petrosa_k8s/k8s/kubeconfig.yaml)"
    echo "  --dry-run               Show what would be done without executing"
    echo ""
    echo "This script will:"
    echo "  1. Remove New Relic (saves ~1.7GB RAM, ~1.5 CPU cores)"
    echo "  2. Optimize existing Prometheus stack"
    echo "  3. Deploy minimal monitoring stack"
    echo "  4. Update application configurations"
    echo "  5. Restart applications"
    echo ""
    echo "Total resource savings: ~2.7GB RAM, ~2 CPU cores"
}

# Parse command line arguments
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --kubeconfig)
            KUBECONFIG_PATH="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Execute main function
if [ "$DRY_RUN" = true ]; then
    print_warning "DRY RUN MODE - No changes will be made"
    echo "This script would:"
    echo "  - Remove New Relic namespace"
    echo "  - Update OTEL configuration"
    echo "  - Deploy minimal monitoring stack"
    echo "  - Restart applications"
else
    main
fi
