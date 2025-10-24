# Repository Setup Guide

This guide provides a comprehensive reference for setting up and working with the Petrosa Binance Data Extractor repository.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker
- kubectl
- MicroK8s (for local development)

### Installation Commands
```bash
# Install MicroK8s
# Linux:
sudo snap install microk8s --classic

# macOS:
brew install microk8s

# Install kubectl
# Linux:
sudo snap install kubectl --classic

# macOS:
brew install kubectl

# Verify installations
microk8s --version
kubectl version --client
```

### Initial Setup
```bash
# 1. Clone and setup
git clone <repository-url>
cd petrosa-binance-data-extractor

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements-dev.txt

# 4. Copy environment template
cp .env.example .env
# Edit .env with your configuration
```

## 🔧 Environment Configuration

### Required Environment Variables
```bash
# Database Configuration
DB_ADAPTER=mysql  # or mongodb
MYSQL_URI=mysql+pymysql://username:password@localhost:3306/binance_data
MONGODB_URI=mongodb://localhost:27017/binance_data

# Binance API (optional for public data)
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# Logging
LOG_LEVEL=INFO

# NATS Messaging (optional)
NATS_ENABLED=true
NATS_URL=nats://localhost:4222
```

## 🏗️ Development Environment

### ⚠️ CRITICAL: VERSION_PLACEHOLDER Rules
- **NEVER replace VERSION_PLACEHOLDER in Kubernetes manifests**
- **VERSION_PLACEHOLDER is part of the deployment system and must be preserved**
- **The deployment scripts handle version replacement automatically**
- **Only modify VERSION_PLACEHOLDER if you're updating the deployment system itself**

### Local Development
```bash
# Start local MicroK8s cluster
microk8s start

# Enable required addons
microk8s enable dns storage ingress

# Configure kubectl
microk8s config > ~/.kube/config

# Verify connection
kubectl cluster-info --insecure-skip-tls-verify
```

### Local Deployment
```bash
# Deploy to local cluster
./scripts/deploy-local.sh

# Or manually deploy
kubectl --context=petrosa apply -f k8s/namespace.yaml

# Check deployment status
kubectl --context=petrosa get all -n petrosa-apps
```

## 🌐 Production Environment

### Kubernetes Cluster Connection

This repository connects to the **Petrosa MicroK8s cluster** using the centralized kubeconfig at `~/.kube/config`.

**Context name:** `petrosa`

#### 1. Quick Commands

```bash
# Check connection
kubectl --context=petrosa get nodes

# View petrosa-apps namespace
kubectl --context=petrosa get pods -n petrosa-apps

# Set as default context (optional)
kubectl config use-context petrosa

# Deploy this service
kubectl --context=petrosa apply -f k8s/
```

#### 2. Initial Setup

The MicroK8s cluster credentials should already be merged into your `~/.kube/config`. If not:

```bash
# 1. Generate fresh credentials
microk8s config > /tmp/microk8s-config.yaml

# 2. Merge with existing config
KUBECONFIG=~/.kube/config:/tmp/microk8s-config.yaml kubectl config view --flatten > ~/.kube/config.new
mv ~/.kube/config.new ~/.kube/config

# 3. Test connection
kubectl --context=petrosa get nodes
```

#### 3. Multiple Clusters

If you work with multiple clusters (dev, prod, petrosa), use context switching:

```bash
# List all contexts
kubectl config get-contexts

# Switch to petrosa
kubectl config use-context petrosa

# Or use --context flag
kubectl --context=petrosa get pods
```

#### 4. Common Connection Issues

**Issue: "Unable to connect to the server"**

**Solutions:**
```bash
# 1. Check if MicroK8s is running
microk8s status

# 2. Start MicroK8s if needed
microk8s start

# 3. Verify context exists
kubectl config get-contexts | grep petrosa

# 4. Test connection
kubectl --context=petrosa cluster-info
```

**Issue: "Certificate signed by unknown authority"**

**Solutions:**
```bash
# Use --insecure-skip-tls-verify flag
kubectl --context=petrosa --insecure-skip-tls-verify get nodes
```

#### 5. Security Notes

- **NEVER commit** `k8s/kubeconfig.yaml` to version control
- `k8s/kubeconfig.yaml` is in .gitignore to prevent credential exposure
- Use `k8s/kubeconfig.yaml.example` as reference only
- All cluster access should use `~/.kube/config` with context switching

### Local Deployment
```bash
# Deploy to local MicroK8s cluster
./scripts/deploy-local.sh

# Or manually deploy
kubectl --context=petrosa apply -f k8s/namespace.yaml

# Check deployment status
kubectl --context=petrosa get all -n petrosa-apps
```

## 🔍 Debugging and Troubleshooting

### Cluster Connection Issues

#### 1. Check Cluster Status
```bash
# Verify cluster is accessible
kubectl cluster-info

# Check nodes
kubectl get nodes

# Check namespaces
kubectl get namespaces
```

#### 2. Port Forwarding for Local Development
```bash
# Forward NATS service using repository kubeconfig
kubectl --context=petrosa port-forward -n nats svc/nats-server 4222:4222 &

# Forward database (if needed)
kubectl --context=petrosa port-forward -n petrosa-apps svc/your-db-service 3306:3306 &

# Check port forwarding
netstat -an | grep 4222
```

#### 3. Pod Debugging
```bash
# Get pod logs using repository kubeconfig
kubectl --context=petrosa logs -f deployment/binance-extractor -n petrosa-apps

# Execute into pod
kubectl --context=petrosa exec -it deployment/binance-extractor -n petrosa-apps -- /bin/bash

# Check pod status
kubectl --context=petrosa describe pod <pod-name> -n petrosa-apps
```

### Common Issues and Solutions

#### 1. Image Pull Errors
```bash
# Check image availability
docker pull your-username/petrosa-binance-extractor:latest

# Verify image in cluster
kubectl --context=petrosa describe pod <pod-name> -n petrosa-apps | grep -A 5 "Events:"

# Solution: Rebuild and push image
docker build -t your-username/petrosa-binance-extractor:latest .
docker push your-username/petrosa-binance-extractor:latest
```

#### 2. Database Connection Issues
```bash
# Test database connection from pod
kubectl --context=petrosa exec -it deployment/binance-extractor -n petrosa-apps -- python -c "
import os
from db.mysql_adapter import MySQLAdapter
try:
    adapter = MySQLAdapter(os.environ['MYSQL_URI'])
    adapter.connect()
    print('Database connection: OK')
except Exception as e:
    print(f'Database connection: FAILED - {e}')
"
```

#### 3. CronJob Issues
```bash
# Check CronJob status
kubectl --context=petrosa get cronjobs -n petrosa-apps

# View CronJob details
kubectl --context=petrosa describe cronjob <cronjob-name> -n petrosa-apps

# Check recent job executions
kubectl --context=petrosa get jobs -n petrosa-apps --sort-by=.metadata.creationTimestamp
```

## 🧪 Testing

### Run Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_extract_klines.py -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Integration Testing
```bash
# Test pipeline simulation
python scripts/test_pipeline_simulation.py

# Test production simulation
python scripts/test_production_simulation.py

# Test NATS messaging
python scripts/test_nats_messaging.py
```

## 📊 Monitoring and Logs

### View Logs
```bash
# Application logs
kubectl --context=petrosa logs -f deployment/binance-extractor -n petrosa-apps

# CronJob logs
kubectl --context=petrosa logs -f job/<job-name> -n petrosa-apps

# Recent logs with timestamps
kubectl --context=petrosa logs -l app=binance-extractor -n petrosa-apps --since=1h
```

### Monitor Resources
```bash
# Resource usage
kubectl --context=petrosa top pods -n petrosa-apps

# Events
kubectl --context=petrosa get events -n petrosa-apps --sort-by=.metadata.creationTimestamp

# Pod status
kubectl --context=petrosa get pods -n petrosa-apps -o wide
```

## 🚀 Development Workflow

### 1. Local Development
```bash
# Start local environment
microk8s start
./scripts/deploy-local.sh

# Run tests
python -m pytest tests/ -v

# Test locally
python jobs/extract_klines.py --symbol BTCUSDT --period 15m
```

### 2. Production Deployment
```bash
# Build and push image
./scripts/build-multiarch.sh

# Deploy to production
./scripts/deploy-production.sh

# Validate deployment
./scripts/validate-production.sh
```

### 3. Release Management
```bash
# Create new release
./scripts/create-release.sh

# Check version
python -c "import constants; print(constants.VERSION)"
```

## 📚 Additional Resources

### Documentation
- [Production Readiness](docs/PRODUCTION_READINESS.md)
- [Operations Guide](docs/OPERATIONS_GUIDE.md)
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [Local Deployment](docs/LOCAL_DEPLOY.md)

### Scripts Reference
- `./scripts/deploy-local.sh` - Local deployment
- `./scripts/deploy-production.sh` - Production deployment
- `./scripts/validate-production.sh` - Production validation
- `./scripts/build-multiarch.sh` - Multi-architecture builds
- `./scripts/create-release.sh` - Release management

### Useful Commands
```bash
# Quick status check
kubectl --context=petrosa get all -n petrosa-apps

# Check CronJobs
kubectl --context=petrosa get cronjobs -n petrosa-apps

# View recent jobs
kubectl --context=petrosa get jobs -n petrosa-apps --sort-by=.metadata.creationTimestamp

# Check logs
kubectl --context=petrosa logs -l app=binance-extractor -n petrosa-apps --tail=100
```

## 🔧 Troubleshooting Checklist

### Before Starting
- [ ] AWS SSO is configured and logged in
- [ ] kubectl is configured for correct cluster
- [ ] Docker is running
- [ ] Environment variables are set
- [ ] Virtual environment is activated

### Common Fixes
- **Cluster Connection**: `kubectl config use-context petrosa`
- **Certificate Issues**: Use `--insecure-skip-tls-verify` flag
- **MicroK8s Issues**: `microk8s start` and `microk8s status`
- **Image Issues**: Rebuild and push Docker image
- **Database Issues**: Check connection strings and credentials
- **CronJob Issues**: Check timezone and resource constraints

### Emergency Contacts
- **Cluster Issues**: Check MicroK8s status
- **Database Issues**: Verify RDS/MySQL connectivity
- **Application Issues**: Check pod logs and events
- **Deployment Issues**: Review deployment scripts and manifests
