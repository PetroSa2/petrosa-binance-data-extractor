#!/bin/bash

# Local deployment script for Petrosa Binance Data Extractor
# This script deploys the application to your local MicroK8s cluster

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="petrosa-apps"
APP_NAME="petrosa-binance-extractor"
DOCKER_IMAGE_TAG="local-$(date +%Y%m%d-%H%M%S)"
KUBECONFIG_PATH="$HOME/Downloads/microk8s.yaml"

echo -e "${BLUE}🚀 Petrosa Binance Data Extractor - Local Deployment${NC}"
echo "=================================================="

# Note: Secrets will be managed by Kubernetes manifests
echo -e "${BLUE}📋 Using Kubernetes-managed secrets...${NC}"
echo -e "${YELLOW}💡 Make sure your secrets are properly configured in k8s/secrets-example.yaml${NC}"
echo -e "${GREEN}✅ No local environment variables needed${NC}"

# Check if MicroK8s kubeconfig exists and kubectl can connect
# Check if Docker is available
echo -e "${BLUE}🐳 Checking Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed or not in PATH!${NC}"
    exit 1
fi

if ! docker info &>/dev/null; then
    echo -e "${RED}❌ Docker daemon is not running!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker is available${NC}"

# Build Docker image locally
echo -e "${BLUE}🔨 Building Docker image...${NC}"
docker build -t $APP_NAME:$DOCKER_IMAGE_TAG . || {
    echo -e "${RED}❌ Failed to build Docker image!${NC}"
    exit 1
}

echo -e "${GREEN}✅ Docker image built: $APP_NAME:$DOCKER_IMAGE_TAG${NC}"

# Check Kubernetes connection and determine setup
echo -e "${BLUE}🔍 Checking Kubernetes connection...${NC}"

# Try different kubeconfig approaches
KUBECONFIG_FOUND=false
KUBECTL_CMD=""

# Check if MicroK8s kubeconfig exists
if [ -f "$KUBECONFIG_PATH" ]; then
    if kubectl --kubeconfig="$KUBECONFIG_PATH" cluster-info --insecure-skip-tls-verify &>/dev/null; then
        echo -e "${GREEN}✅ Connected using MicroK8s kubeconfig${NC}"
        KUBECONFIG_FOUND=true
        KUBECTL_CMD="kubectl --kubeconfig=\"$KUBECONFIG_PATH\" --insecure-skip-tls-verify"

        # Import image to MicroK8s if available
        echo -e "${BLUE}📦 Importing image to MicroK8s...${NC}"
        if command -v microk8s &>/dev/null; then
            docker save $APP_NAME:$DOCKER_IMAGE_TAG | microk8s ctr image import - || {
                echo -e "${YELLOW}⚠️ Failed to import image to MicroK8s, but continuing...${NC}"
            }
            echo -e "${GREEN}✅ Image imported to MicroK8s${NC}"
        else
            echo -e "${YELLOW}⚠️ MicroK8s CLI not found, skipping image import${NC}"
        fi
    fi
fi

# Try default kubectl context
if [ "$KUBECONFIG_FOUND" = false ]; then
    if kubectl cluster-info &>/dev/null; then
        echo -e "${GREEN}✅ Connected using default kubectl context${NC}"
        KUBECONFIG_FOUND=true
        KUBECTL_CMD="kubectl"

        # For other setups (Docker Desktop, minikube), the image should be available
        echo -e "${BLUE}📦 Using local Docker image (should be available in cluster)${NC}"
    fi
fi

if [ "$KUBECONFIG_FOUND" = false ]; then
    echo -e "${RED}❌ Cannot connect to any Kubernetes cluster!${NC}"
    echo "Please ensure one of the following:"
    echo "  1. MicroK8s is running with kubeconfig at: $KUBECONFIG_PATH"
    echo "  2. Docker Desktop Kubernetes is enabled"
    echo "  3. minikube is running"
    echo "  4. kubectl is configured with a valid context"
    exit 1
fi

# Create namespace if it doesn't exist
echo -e "${BLUE}📁 Creating namespace...${NC}"
eval "$KUBECTL_CMD create namespace $NAMESPACE --dry-run=client -o yaml | $KUBECTL_CMD apply -f -"

# Note: Secrets will be created from the Kubernetes manifests
echo -e "${BLUE}🔐 Secrets will be applied from k8s/secrets-example.yaml${NC}"
echo -e "${YELLOW}💡 Make sure to update k8s/secrets-example.yaml with your actual credentials${NC}"

# Update image tags in manifests
echo -e "${BLUE}🔄 Updating manifest image tags...${NC}"
# Create temporary directory for modified manifests
TEMP_DIR=$(mktemp -d)
cp -r k8s/* $TEMP_DIR/

# Update image references in the temporary manifests
find $TEMP_DIR -name "*.yaml" -o -name "*.yml" | xargs sed -i.bak "s|image: DOCKERHUB_USERNAME/petrosa-binance-extractor:.*|image: $APP_NAME:$DOCKER_IMAGE_TAG|g"

echo -e "${GREEN}✅ Image tags updated to: $APP_NAME:$DOCKER_IMAGE_TAG${NC}"

# Apply Kubernetes manifests
echo -e "${BLUE}🚀 Applying Kubernetes manifests...${NC}"
eval "$KUBECTL_CMD apply -f $TEMP_DIR/ --recursive" || {
    echo -e "${RED}❌ Failed to apply manifests!${NC}"
    exit 1
}

# Clean up temporary files
rm -rf $TEMP_DIR

echo -e "${GREEN}✅ Manifests applied successfully${NC}"

# Wait a moment for resources to be created
sleep 3

# Show deployment status
echo -e "${BLUE}📊 Deployment Status${NC}"
echo "===================="

echo -e "${YELLOW}📅 CronJobs:${NC}"
eval "$KUBECTL_CMD get cronjobs -n $NAMESPACE" || echo "No CronJobs found"

echo -e "${YELLOW}📦 Recent Pods:${NC}"
eval "$KUBECTL_CMD get pods -n $NAMESPACE" || echo "No pods found"

echo -e "${YELLOW}🔐 Secrets:${NC}"
eval "$KUBECTL_CMD get secrets -n $NAMESPACE" || echo "No secrets found"

echo -e "${YELLOW}📋 ConfigMaps:${NC}"
eval "$KUBECTL_CMD get configmaps -n $NAMESPACE" || echo "No configmaps found"

# Display monitoring commands
echo ""
echo -e "${BLUE}📊 Monitoring Commands${NC}"
echo "====================="
echo -e "${YELLOW}View all resources:${NC}"
echo "$KUBECTL_CMD get all -n $NAMESPACE"
echo ""
echo -e "${YELLOW}Watch CronJobs:${NC}"
echo "$KUBECTL_CMD get cronjobs -n $NAMESPACE -w"
echo ""
echo -e "${YELLOW}View logs (when pods are running):${NC}"
echo "$KUBECTL_CMD logs -l app=binance-extractor -n $NAMESPACE"
echo ""
echo -e "${YELLOW}Trigger a manual job (example for klines):${NC}"
echo "$KUBECTL_CMD create job --from=cronjob/binance-klines-m15-production manual-test-\$(date +%s) -n $NAMESPACE"

echo ""
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${BLUE}💡 The CronJobs are now scheduled and will run automatically based on their schedules.${NC}"
echo -e "${BLUE}💡 Check the CronJob schedules with: $KUBECTL_CMD get cronjobs -n $NAMESPACE${NC}"
