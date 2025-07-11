# Local Deployment Guide

This guide helps you deploy the Petrosa Binance Data Extractor to your local MicroK8s cluster.

## Prerequisites

1. **MicroK8s** is installed and running
2. **Docker** is installed and running
3. **kubectl** is installed
4. **Environment variables** are set in `.env` file

## Quick Deployment

### Option 1: Automated Script (Recommended)

```bash
# Run the automated deployment script
./scripts/setup-dev.sh
```

### Option 2: Manual Step-by-Step

#### 1. Check Prerequisites

```bash
# Check MicroK8s status
microk8s status

# Check kubectl connection (using repo kubeconfig)
export KUBECONFIG=k8s/kubeconfig.yaml
kubectl get nodes

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

#### 4. Create Namespace (if needed)

```bash
# Create namespace (using repo kubeconfig)
kubectl --kubeconfig=k8s/kubeconfig.yaml create namespace petrosa-apps --dry-run=client -o yaml | kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f -
```

#### 5. Deploy Application

```bash
# Deploy using provided manifests
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/
```

#### 6. Port Forwarding Example

```bash
# Port forward NATS
kubectl --kubeconfig=k8s/kubeconfig.yaml port-forward -n nats svc/nats-server 4222:4222 &
```

## References
- See `docs/REPOSITORY_SETUP_GUIDE.md` for full setup and troubleshooting
- See `docs/QUICK_REFERENCE.md` for common commands