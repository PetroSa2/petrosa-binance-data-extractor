# Scripts Directory

This directory contains utility scripts for the Petrosa Binance Data Extractor.

## 📚 Setup References
- **[Documentation Index](../docs/INDEX.md)** - Maintained service documentation
- **[Agent Instructions](../AGENTS.md)** - Commands and repository rules

## 🔧 Available Scripts

### Development Setup
- `setup-dev.sh` - Sets up development environment and tests cluster connection
- `deploy-local.sh` - Deploys to local MicroK8s cluster
- `test_pipeline_simulation.py` - Tests pipeline functionality

### Production
- `deploy-production.sh` - Deploys to production environment
- `validate-production.sh` - Validates production deployment
- `build-multiarch.sh` - Builds multi-architecture Docker images

### Utilities
- `create-release.sh` - Creates new releases
- `encode_secrets.py` - Encodes secrets for Kubernetes

## 🚀 Quick Start

```bash
# Setup development environment
./scripts/setup-dev.sh

# Deploy locally
./scripts/deploy-local.sh

# Test connection
kubectl --kubeconfig=k8s/kubeconfig.yaml get all -n petrosa-apps
```

## 💡 Important Notes

- This repository uses **local MicroK8s cluster**, not AWS EKS
- Always use `kubectl --kubeconfig=k8s/kubeconfig.yaml` for cluster operations
- For port forwarding: `kubectl --kubeconfig=k8s/kubeconfig.yaml port-forward`
- See [Agent Instructions](../AGENTS.md) for common commands
