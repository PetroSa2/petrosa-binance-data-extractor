# Production Deployment Guide

## 🚀 Step-by-Step Production Deployment

This guide provides detailed instructions for deploying the Petrosa Binance Data Extractor to production.

## 📋 Prerequisites

### Infrastructure Requirements
- [ ] Kubernetes cluster (v1.20+)
- [ ] Docker Hub account with repository access
- [ ] Data-manager API reachable from the cluster
- [ ] Binance API credentials
- [ ] kubectl installed

### Required Tools
- [ ] kubectl (v1.20+)
- [ ] Docker (for local builds if needed)
- [ ] Git (for repository access)

## 🔧 Pre-Deployment Setup

### 1. Repository Configuration

```bash
# Clone the repository
git clone https://github.com/your-org/petrosa-binance-data-extractor.git
cd petrosa-binance-data-extractor

git checkout main
```

### 2. Environment Configuration

Create a production environment file:

```bash
cat > .env.production << EOF
# Binance API Configuration
BINANCE_API_KEY=your_production_api_key
BINANCE_SECRET_KEY=your_production_secret_key

# Data-manager configuration
DB_ADAPTER=data_manager
DATA_MANAGER_URL=http://petrosa-data-manager:80

# OpenTelemetry Configuration (service names are now hardcoded)
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_LOGS_EXPORTER=otlp

# Application Configuration
LOG_LEVEL=INFO
DEFAULT_PERIOD=15m
DB_BATCH_SIZE=1000
EOF
```

### 3. Docker Hub Configuration

```bash
# Login to Docker Hub
docker login

# Set your Docker Hub username
export DOCKERHUB_USERNAME=your_dockerhub_username
```

## 🏗️ Deployment Steps

### Step 1: Create Namespace

```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml create namespace petrosa-apps
kubectl --kubeconfig=k8s/kubeconfig.yaml get namespace petrosa-apps
```

### Step 2: Create/Update Secrets

> **Note:** All sensitive credentials should be stored in a single secret (e.g., `petrosa-sensitive-credentials`).
> Update your manifests to mount or reference this secret as needed.

```bash
# Example: create/update secret with data-manager configuration
kubectl --kubeconfig=k8s/kubeconfig.yaml create secret generic petrosa-sensitive-credentials \
  --from-literal=DATA_MANAGER_URL="http://petrosa-data-manager:80" \
  -n petrosa-apps --dry-run=client -o yaml | kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f -

# Verify secret
kubectl --kubeconfig=k8s/kubeconfig.yaml get secrets -n petrosa-apps
```

### Step 3: Build and Push Docker Image

```bash
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --tag $DOCKERHUB_USERNAME/petrosa-binance-extractor:latest \
    --push .

docker pull $DOCKERHUB_USERNAME/petrosa-binance-extractor:latest
```

### Step 4: Update Kubernetes Manifests

```bash
find k8s/ -name "*.yaml" | xargs sed -i.bak "s|image: .*/petrosa-binance-extractor:.*|image: $DOCKERHUB_USERNAME/petrosa-binance-extractor:latest|g"
grep -r "image:" k8s/
```

### Step 5: Deploy Application

```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/ --recursive
kubectl --kubeconfig=k8s/kubeconfig.yaml get all -n petrosa-apps
```

## 🔍 Post-Deployment Verification

### 1. Check Resource Status

```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml get all -n petrosa-apps
```

### 2. Verify CronJobs

```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml get cronjobs -n petrosa-apps
kubectl --kubeconfig=k8s/kubeconfig.yaml get cronjob -n petrosa-apps -o jsonpath='{range .items[*]}{.metadata.name}: {.spec.schedule}{"\n"}{end}'
```

### 3. Test Manual Execution

```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml create job --from=cronjob/binance-klines-m15-production test-deployment-$(date +%s) -n petrosa-apps
kubectl --kubeconfig=k8s/kubeconfig.yaml get jobs -n petrosa-apps -w
```

### 4. Verify Logs

```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -l app=binance-extractor -n petrosa-apps --tail=50
```

## 📊 Monitoring Setup

### 1. OpenTelemetry Verification

```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -l app=binance-extractor -n petrosa-apps | grep -i "telemetry\|otel"
```

### 2. Data-manager Connectivity

```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml exec -it deployment/binance-extractor -n petrosa-apps -- sh -c \
  'curl "$DATA_MANAGER_URL/health"'
```

### 3. API Connectivity

```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml exec -it deployment/binance-extractor -n petrosa-apps -- python -c "
import os
from fetchers.client import BinanceClient
try:
    client = BinanceClient()
    response = client.get('/api/v3/ping')
    print('Binance API: SUCCESS')
except Exception as e:
    print(f'Binance API: FAILED - {e}')
"
```

## 🚨 Troubleshooting

### Common Deployment Issues

#### 1. Image Pull Errors

```bash
docker pull $DOCKERHUB_USERNAME/petrosa-binance-extractor:latest
kubectl --kubeconfig=k8s/kubeconfig.yaml get secret -n petrosa-apps
kubectl --kubeconfig=k8s/kubeconfig.yaml describe pod -l app=binance-extractor -n petrosa-apps
```

#### 2. Secret Issues

```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml get secrets -n petrosa-apps
kubectl --kubeconfig=k8s/kubeconfig.yaml describe secret petrosa-sensitive-credentials -n petrosa-apps
```

## References
- See `docs/INDEX.md` for the maintained documentation set
- See `AGENTS.md` for repository commands
