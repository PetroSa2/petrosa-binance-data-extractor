# Production Deployment Guide

## 🚀 Step-by-Step Production Deployment

This guide provides detailed instructions for deploying the Petrosa Binance Data Extractor to production.

## 📋 Prerequisites

### Infrastructure Requirements
- [ ] Kubernetes cluster (v1.20+)
- [ ] Docker Hub account with repository access
- [ ] Database instance (MySQL/MongoDB)
- [ ] Binance API credentials
- [ ] kubectl configured for target cluster

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

# Switch to production branch
git checkout main
```

### 2. Environment Configuration

Create a production environment file:

```bash
# Create production environment file
cat > .env.production << EOF
# Binance API Configuration
BINANCE_API_KEY=your_production_api_key
BINANCE_SECRET_KEY=your_production_secret_key

# Database Configuration
POSTGRES_CONNECTION_STRING=postgresql://user:password@host:port/database
MYSQL_URI=mysql+pymysql://user:password@host:port/database
MONGODB_URI=mongodb://user:password@host:port/database

# OpenTelemetry Configuration
OTEL_SERVICE_NAME_KLINES=prod-binance-klines-extractor
OTEL_SERVICE_NAME_FUNDING=prod-binance-funding-extractor
OTEL_SERVICE_NAME_TRADES=prod-binance-trades-extractor
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
# Create production namespace
kubectl create namespace petrosa-apps

# Verify namespace creation
kubectl get namespace petrosa-apps
```

### Step 2: Create Secrets

```bash
# Load environment variables
export $(grep -v '^#' .env.production | xargs)

# Verify secrets
kubectl get secrets -n petrosa-apps
```

### Step 3: Build and Push Docker Image

```bash
# Build multi-architecture image
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --tag $DOCKERHUB_USERNAME/petrosa-binance-extractor:latest \
    --push .

# Verify image push
docker pull $DOCKERHUB_USERNAME/petrosa-binance-extractor:latest
```

### Step 4: Update Kubernetes Manifests

```bash
# Update image references in manifests
find k8s/ -name "*.yaml" | xargs sed -i.bak "s|image: .*/petrosa-binance-extractor:.*|image: $DOCKERHUB_USERNAME/petrosa-binance-extractor:latest|g"

# Verify changes
grep -r "image:" k8s/
```

### Step 5: Deploy Application

```bash
# Apply all Kubernetes manifests
kubectl apply -f k8s/ --recursive

# Verify deployment
kubectl get all -n petrosa-apps
```

## 🔍 Post-Deployment Verification

### 1. Check Resource Status

```bash
# Verify all resources are running
kubectl get all -n petrosa-apps

# Expected output:
# - 6 CronJobs (5 timeframes + 1 gap filler)
# - No failed pods
# - All services healthy
```

### 2. Verify CronJobs

```bash
# Check CronJob status
kubectl get cronjobs -n petrosa-apps

# Verify schedules
kubectl get cronjob -n petrosa-apps -o jsonpath='{range .items[*]}{.metadata.name}: {.spec.schedule}{"\n"}{end}'
```

### 3. Test Manual Execution

```bash
# Test a manual job execution
kubectl create job --from=cronjob/binance-klines-m15-production test-deployment-$(date +%s) -n petrosa-apps

# Monitor the job
kubectl get jobs -n petrosa-apps -w
```

### 4. Verify Logs

```bash
# Check application logs
kubectl logs -l app=binance-extractor -n petrosa-apps --tail=50

# Look for:
# - Successful startup messages
# - OpenTelemetry initialization
# - Database connection success
# - No critical errors
```

## 📊 Monitoring Setup

### 1. OpenTelemetry Verification

```bash
# Check telemetry initialization
kubectl logs -l app=binance-extractor -n petrosa-apps | grep -i "telemetry\|otel"

# Expected output:
# - Telemetry setup messages
# - Service name configuration
# - Exporter configuration
```

### 2. Database Connectivity

```bash
# Test database connection
kubectl exec -it deployment/binance-extractor -n petrosa-apps -- python -c "
import os
from db.mysql_adapter import MySQLAdapter
try:
    adapter = MySQLAdapter(os.environ['POSTGRES_CONNECTION_STRING'])
    adapter.connect()
    print('Database connection: SUCCESS')
except Exception as e:
    print(f'Database connection: FAILED - {e}')
"
```

### 3. API Connectivity

```bash
# Test Binance API access
kubectl exec -it deployment/binance-extractor -n petrosa-apps -- python -c "
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
# Check image availability
docker pull $DOCKERHUB_USERNAME/petrosa-binance-extractor:latest

# Verify registry credentials
kubectl get secret -n petrosa-apps

# Check image pull status
kubectl describe pod -l app=binance-extractor -n petrosa-apps
```

#### 2. Secret Issues

```bash
# Verify secrets exist
kubectl get secrets -n petrosa-apps

# Check secret content (base64 encoded)
kubectl get secret petrosa-sensitive-credentials -n petrosa-apps -o jsonpath='{.data.MYSQL_URI}' | base64 -d
```

#### 3. Resource Constraints

```bash
# Check resource quotas
kubectl describe resourcequota -n petrosa-apps

# Check node resources
kubectl describe nodes | grep -A 10 "Allocated resources"
```

#### 4. Network Issues

```bash
# Test network connectivity
kubectl exec -it deployment/binance-extractor -n petrosa-apps -- curl -I https://api.binance.com

# Check DNS resolution
kubectl exec -it deployment/binance-extractor -n petrosa-apps -- nslookup api.binance.com
```

## 🔄 Rollback Procedures

### Quick Rollback

```bash
# Rollback to previous deployment
kubectl rollout undo deployment/binance-extractor -n petrosa-apps

# Or rollback to specific revision
kubectl rollout undo deployment/binance-extractor -n petrosa-apps --to-revision=1
```

### Complete Rollback

```bash
# Delete current deployment
kubectl delete -f k8s/ --recursive

# Apply previous version
kubectl apply -f k8s-previous/ --recursive
```

## 📈 Performance Optimization

### Resource Tuning

```bash
# Monitor resource usage
kubectl top pods -n petrosa-apps

# Adjust resource limits if needed
kubectl patch cronjob binance-klines-m15-production -n petrosa-apps -p '
{
  "spec": {
    "jobTemplate": {
      "spec": {
        "template": {
          "spec": {
            "containers": [{
              "name": "binance-extractor",
              "resources": {
                "requests": {"cpu": "1", "memory": "1Gi"},
                "limits": {"cpu": "2", "memory": "2Gi"}
              }
            }]
          }
        }
      }
    }
  }
}'
```

### Scaling Configuration

```bash
# Adjust parallel workers
kubectl patch cronjob binance-klines-m15-production -n petrosa-apps -p '
{
  "spec": {
    "jobTemplate": {
      "spec": {
        "parallelism": 5
      }
    }
  }
}'
```

## 📋 Deployment Checklist

### Pre-Deployment
- [ ] Infrastructure requirements met
- [ ] Environment variables configured
- [ ] Secrets created and verified
- [ ] Docker image built and pushed
- [ ] Kubernetes manifests updated

### Deployment
- [ ] Namespace created
- [ ] Secrets applied
- [ ] Manifests deployed
- [ ] Resources verified
- [ ] Manual test executed

### Post-Deployment
- [ ] All CronJobs running
- [ ] Logs showing success
- [ ] Database connectivity verified
- [ ] API connectivity verified
- [ ] Monitoring configured

## 📚 Related Documentation

- [Production Readiness](PRODUCTION_READINESS.md) - Pre-deployment checklist
- [Operations Guide](OPERATIONS_GUIDE.md) - Day-to-day operations
- [Deployment Complete](DEPLOYMENT_COMPLETE.md) - Post-deployment verification
- [Local Deployment](LOCAL_DEPLOY.md) - Local development setup
- [CI/CD Pipeline](CI_CD_PIPELINE_RESULTS.md) - Automated deployment results
