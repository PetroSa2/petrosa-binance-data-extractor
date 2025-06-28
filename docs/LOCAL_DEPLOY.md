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

# Create Binance API secret
kubectl create secret generic binance-api-secret \
    --from-literal=api-key="$BINANCE_API_KEY" \
    --from-literal=api-secret="$BINANCE_SECRET_KEY" \
    --namespace=petrosa-apps \
    --dry-run=client -o yaml | kubectl apply -f - --insecure-skip-tls-verify

# Create database secret
kubectl create secret generic database-secret \
    --from-literal=mysql-uri="$POSTGRES_CONNECTION_STRING" \
    --namespace=petrosa-apps \
    --dry-run=client -o yaml | kubectl apply -f - --insecure-skip-tls-verify
```

#### 5. Update and Apply Manifests

```bash
# Update image references in manifests
find k8s/ -name "*.yaml" | xargs sed -i.bak 's|image: DOCKERHUB_USERNAME/petrosa-binance-extractor:.*|image: petrosa-binance-extractor:local|g'

# Apply manifests
kubectl apply -f k8s/ --recursive --insecure-skip-tls-verify
```

## Monitoring Your Deployment

### Check Deployment Status

```bash
# View all resources
kubectl get all -n petrosa-apps --insecure-skip-tls-verify

# Check CronJobs
kubectl get cronjobs -n petrosa-apps --insecure-skip-tls-verify

# Check recent pods
kubectl get pods -n petrosa-apps --sort-by=.metadata.creationTimestamp --insecure-skip-tls-verify
```

### View Logs

```bash
# View logs from any running pods
kubectl logs -l app=binance-extractor -n petrosa-apps --insecure-skip-tls-verify

# Follow logs in real-time
kubectl logs -l app=binance-extractor -n petrosa-apps -f --insecure-skip-tls-verify
```

### Manual Job Testing

```bash
# Trigger a manual job from a CronJob
kubectl create job --from=cronjob/binance-klines-m15-production manual-test-$(date +%s) -n petrosa-apps --insecure-skip-tls-verify

# Watch the job
kubectl get jobs -n petrosa-apps -w --insecure-skip-tls-verify
```

## Troubleshooting

### Common Issues

1. **Image pull errors**: Make sure the image was imported correctly
   ```bash
   microk8s ctr images ls | grep petrosa-binance-extractor
   ```

2. **Secret not found**: Verify secrets were created
   ```bash
   kubectl get secrets -n petrosa-apps --insecure-skip-tls-verify
   ```

3. **Pod crashes**: Check logs for errors
   ```bash
   kubectl describe pod <pod-name> -n petrosa-apps --insecure-skip-tls-verify
   kubectl logs <pod-name> -n petrosa-apps --insecure-skip-tls-verify
   ```

### Cleanup

```bash
# Remove all resources
kubectl delete namespace petrosa-apps --insecure-skip-tls-verify

# Remove local Docker image
docker rmi petrosa-binance-extractor:local
```

## Environment Variables Required

Make sure your `.env` file contains at least:

```env
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here
POSTGRES_CONNECTION_STRING=postgresql://user:password@host:port/database
```

## Next Steps

1. **Monitor CronJobs**: They will run according to their schedules
2. **Check logs**: Look for any errors or successful data extraction
3. **Verify data**: Check your database for extracted data
4. **Scale if needed**: Adjust CronJob schedules or add more symbols
