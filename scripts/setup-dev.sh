#!/bin/bash

# Petrosa Binance Data Extractor - Development Setup Script
#
# This script sets up the development environment for this repository.
# For maintained documentation, see: docs/INDEX.md

set -e

echo "🚀 Setting up Petrosa Binance Data Extractor development environment..."

# Check if we're in the right directory
if [ ! -f "k8s/kubeconfig.yaml" ]; then
    echo "❌ Error: k8s/kubeconfig.yaml not found. Are you in the repository root?"
    exit 1
fi

# Set kubeconfig for this repository
export KUBECONFIG=k8s/kubeconfig.yaml
echo "✅ Set KUBECONFIG to k8s/kubeconfig.yaml"

# Check MicroK8s status
echo "🔍 Checking MicroK8s status..."
if ! command -v microk8s > /dev/null 2>&1; then
    echo "❌ MicroK8s not installed. Please install it first:"
    echo "   Linux: sudo snap install microk8s --classic"
    echo "   macOS: brew install microk8s"
    echo "   See docs/INDEX.md for maintained documentation"
    exit 1
elif ! microk8s status > /dev/null 2>&1; then
    echo "⚠️  MicroK8s not running. Starting MicroK8s..."
    microk8s start
else
    echo "✅ MicroK8s is running"
fi

# Test cluster connection
echo "🔍 Testing cluster connection..."
if kubectl --kubeconfig=k8s/kubeconfig.yaml --insecure-skip-tls-verify get nodes > /dev/null 2>&1; then
    echo "✅ Cluster connection successful"
else
    echo "❌ Cluster connection failed. Please check:"
    echo "   - MicroK8s is running: microk8s status"
    echo "   - See docs/INDEX.md for troubleshooting guidance"
    exit 1
fi

# Check if namespace exists
echo "🔍 Checking namespace..."
if kubectl --kubeconfig=k8s/kubeconfig.yaml get namespace petrosa-apps > /dev/null 2>&1; then
    echo "✅ Namespace petrosa-apps exists"
else
    echo "⚠️  Namespace petrosa-apps not found. You may need to deploy first."
    echo "   Run: ./scripts/deploy-local.sh"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📚 Useful references:"
    echo "   - Documentation Index: docs/INDEX.md"
echo ""
echo "🔧 Common commands:"
echo "   - Check status: kubectl --kubeconfig=k8s/kubeconfig.yaml get all -n petrosa-apps"
echo "   - Port forward NATS: kubectl --kubeconfig=k8s/kubeconfig.yaml port-forward -n nats svc/nats-server 4222:4222 &"
echo "   - View logs: kubectl --kubeconfig=k8s/kubeconfig.yaml logs -f deployment/binance-extractor -n petrosa-apps"
echo ""
echo "💡 Remember: This repository uses local MicroK8s, not AWS EKS!"
