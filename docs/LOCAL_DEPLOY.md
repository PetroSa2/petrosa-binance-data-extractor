# Local Deployment Guide

This guide helps you deploy the Petrosa Binance Data Extractor to your local MicroK8s cluster.

## Prerequisites

1. **MicroK8s** is installed and running
2. **Docker** is installed and running
3. **kubectl** is configured to access your MicroK8s cluster
4. **Environment variables** are set in `.env` file

## Quick Deployment

### Option 1: Automated Script (Recommended)

```bash
# Run the automated deployment script
./deploy-local.sh
```

### Option 2: Manual Step-by-Step

#### 1. Check Prerequisites

```bash
# Check MicroK8s status
microk8s status

# Check kubectl connection
kubectl cluster-info --insecure-skip-tls-verify

# Check Docker
docker info
```

#### 2. Load Environment Variables

```bash
# Load your .env file
export $(grep -v '^#' .env | xargs)
```

#### 3. Build and Import Docker Image

```bash
# Build the image
docker build -t petrosa-binance-extractor:local .

# Import to MicroK8s
docker save petrosa-binance-extractor:local | microk8s ctr image import -
```

#### 4. Create Namespace and Secrets

```bash
# Create namespace
kubectl create namespace petrosa-apps --dry-run=client -o yaml | kubectl apply -f - --insecure-skip-tls-verify
```