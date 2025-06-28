#!/bin/bash

# Production Deployment Script for Binance Data Extractor
# This script deploys all timeframes (m5, m15, m30, h1, d1) to Kubernetes

set -e

echo "🚀 Starting production deployment of Binance Data Extractor..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl not found. Please install kubectl first."
    exit 1
fi

# Check cluster connectivity
print_status "Checking Kubernetes cluster connectivity..."
if ! kubectl cluster-info &> /dev/null; then
    print_error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
    exit 1
fi

print_success "Connected to Kubernetes cluster"

# Create namespace if it doesn't exist
print_status "Ensuring namespace 'petrosa-apps' exists..."
if ! kubectl get namespace petrosa-apps &> /dev/null; then
    print_status "Creating namespace 'petrosa-apps'..."
    kubectl apply -f k8s/namespace.yaml
    print_success "Namespace 'petrosa-apps' created"
else
    print_success "Namespace 'petrosa-apps' already exists"
fi

# Check if secrets exist
print_status "Checking required secrets..."
SECRETS_MISSING=false

if ! kubectl get secret binance-api-secret -n petrosa-apps &> /dev/null; then
    print_warning "Secret 'binance-api-secret' not found!"
    echo "  Create it with: kubectl create secret generic binance-api-secret -n petrosa-apps --from-literal=api-key=YOUR_API_KEY --from-literal=api-secret=YOUR_API_SECRET"
    SECRETS_MISSING=true
fi

if ! kubectl get secret database-secret -n petrosa-apps &> /dev/null; then
    print_warning "Secret 'database-secret' not found!"
    echo "  Create it with: kubectl create secret generic database-secret -n petrosa-apps --from-literal=mysql-uri=YOUR_MYSQL_URI"
    SECRETS_MISSING=true
fi

if [ "$SECRETS_MISSING" = true ]; then
    print_error "Please create the missing secrets before proceeding."
    exit 1
fi

print_success "All required secrets are present"

# Deploy all timeframes
print_status "Deploying all timeframes CronJobs (m5, m15, m30, h1, d1)..."
kubectl apply -f k8s/klines-all-timeframes-cronjobs.yaml

print_status "Deploying manual job template..."
kubectl apply -f k8s/job.yaml

# Wait a moment for resources to be created
sleep 2

# Display deployment status
echo ""
print_success "🎉 Deployment completed successfully!"
echo ""

print_status "📊 Current CronJob status:"
kubectl get cronjobs -l app=binance-extractor -n petrosa-apps -o wide

echo ""
print_status "📝 CronJob schedules:"
echo "  • m5  (5-minute):  Every 5 minutes"
echo "  • m15 (15-minute): Every 15 minutes at minute 2"
echo "  • m30 (30-minute): Every 30 minutes at minute 5"
echo "  • h1  (1-hour):    Every hour at minute 10"
echo "  • d1  (1-day):     Daily at 00:15 UTC"

echo ""
print_status "🔍 Monitor your deployment:"
echo "  • View CronJobs:    kubectl get cronjobs -l app=binance-extractor -n petrosa-apps"
echo "  • View recent jobs: kubectl get jobs -l app=binance-extractor -n petrosa-apps --sort-by=.metadata.creationTimestamp"
echo "  • View logs:        kubectl logs -l component=klines-extractor -n petrosa-apps --tail=100"

echo ""
print_status "💡 Useful commands:"
echo "  • Run manual job:   kubectl create job manual-extraction-\$(date +%s) -n petrosa-apps --from=job/binance-klines-manual"
echo "  • Delete all jobs:  kubectl delete jobs -l app=binance-extractor -n petrosa-apps"
echo "  • Suspend CronJob:  kubectl patch cronjob binance-klines-m5-production -n petrosa-apps -p '{\"spec\":{\"suspend\":true}}'"

echo ""
print_success "✅ All timeframes are now scheduled and ready for production data extraction!"

# Check if any jobs are currently running
RUNNING_JOBS=$(kubectl get jobs -l app=binance-extractor -n petrosa-apps --field-selector status.active=1 -o name 2>/dev/null | wc -l)
if [ "$RUNNING_JOBS" -gt 0 ]; then
    print_status "🏃 Currently running jobs: $RUNNING_JOBS"
else
    print_status "⏳ No jobs currently running (normal for CronJobs waiting for schedule)"
fi
