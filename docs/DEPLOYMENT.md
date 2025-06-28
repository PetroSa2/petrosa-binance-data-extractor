# Deployment Guide

This guide explains how to set up and deploy the Petrosa Binance Data Extractor to your MicroK8s cluster using GitHub Actions CI/CD.

## Prerequisites

1. **MicroK8s cluster** running and accessible
2. **Docker Hub account** for storing container images
3. **GitHub repository** with Actions enabled
4. **Database setup** (PostgreSQL/MySQL and optionally MongoDB)

## Required GitHub Secrets

You need to configure the following secrets in your GitHub repository settings (`Settings` → `Secrets and variables` → `Actions`):

### Docker Hub Credentials
- `DOCKERHUB_USERNAME`: Your Docker Hub username
- `DOCKERHUB_TOKEN`: Your Docker Hub access token (not password)

### Kubernetes Configuration
- `KUBE_CONFIG_DATA`: Base64-encoded kubeconfig file for your MicroK8s cluster

### Application Secrets
- `BINANCE_API_KEY`: Your Binance API key
- `BINANCE_SECRET_KEY`: Your Binance API secret key
- `POSTGRES_CONNECTION_STRING`: PostgreSQL connection string
- `MONGO_CONNECTION_STRING`: MongoDB connection string (optional)
- `REDIS_URL`: Redis connection URL (optional)

## Setting Up GitHub Secrets

### 1. Docker Hub Setup

1. Create a Docker Hub access token:
   - Go to Docker Hub → Account Settings → Security
   - Click "New Access Token"
   - Give it a name (e.g., "GitHub Actions")
   - Copy the generated token

2. Add to GitHub secrets:
   - `DOCKERHUB_USERNAME`: Your Docker Hub username
   - `DOCKERHUB_TOKEN`: The access token from step 1

### 2. Kubernetes Configuration

1. Get your MicroK8s kubeconfig:
   ```bash
   microk8s config > ~/.kube/microk8s-config
   ```

2. Base64 encode the kubeconfig:
   ```bash
   cat ~/.kube/microk8s-config | base64 -w 0
   ```

3. Add to GitHub secrets:
   - `KUBE_CONFIG_DATA`: The base64-encoded kubeconfig from step 2

### 3. Application Configuration

Add the following secrets with your actual values:

```bash
# Binance API credentials
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_SECRET_KEY=your_binance_secret_key_here

# Database connections
POSTGRES_CONNECTION_STRING=postgresql://user:password@host:port/database
MONGO_CONNECTION_STRING=mongodb://user:password@host:port/database
REDIS_URL=redis://host:port/0
```

## Deployment Architecture

The CI/CD pipeline deploys the following components to your MicroK8s cluster:

### Namespace
- `petrosa-apps`: Dedicated namespace for the application

### CronJobs
- `binance-klines-m15-production`: Fetches 15-minute klines data
- `binance-klines-h1-production`: Fetches 1-hour klines data  
- `binance-klines-d1-production`: Fetches daily klines data
- Additional CronJobs for different timeframes

### Secrets
- `binance-api-secret`: Contains Binance API credentials
- `database-secret`: Contains database connection strings

### ConfigMaps
- `binance-extractor-config`: Application configuration

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci-cd.yml`) performs the following steps:

1. **Test**: Runs unit tests with pytest and mypy type checking
2. **Build**: Creates Docker image and pushes to Docker Hub
3. **Deploy**: Deploys to MicroK8s cluster using kubectl

### Triggers

The pipeline runs on:
- Push to `main` branch
- Pull requests to `main` branch
- Git tags starting with `v` (e.g., `v1.0.0`)

### Image Tagging

- `main` branch: Tagged as `latest`
- Git tags: Tagged with the tag name (e.g., `v1.0.0`)
- Other branches: Tagged with commit SHA

## Manual Deployment Steps

If you need to deploy manually:

1. **Build and push the Docker image:**
   ```bash
   docker build -t your-dockerhub-username/petrosa-binance-extractor:latest .
   docker push your-dockerhub-username/petrosa-binance-extractor:latest
   ```

2. **Update image references in Kubernetes manifests:**
   ```bash
   find k8s/ -name "*.yaml" | xargs sed -i "s|DOCKERHUB_USERNAME|your-dockerhub-username|g"
   ```

3. **Apply the manifests:**
   ```bash
   kubectl apply -f k8s/
   ```

## Monitoring and Troubleshooting

### Check Deployment Status
```bash
# List all resources in the namespace
kubectl get all -n petrosa-apps

# Check CronJob status
kubectl get cronjobs -n petrosa-apps

# View recent jobs
kubectl get jobs -n petrosa-apps --sort-by=.metadata.creationTimestamp

# Check pod logs
kubectl logs -l app=binance-extractor -n petrosa-apps --tail=100
```

### Common Issues

1. **Image pull errors**: Verify Docker Hub credentials and image name
2. **Secret not found**: Ensure all required secrets are created
3. **CronJob not running**: Check schedule syntax and cluster time
4. **Database connection errors**: Verify connection strings and network access

### Debug a Failed Job
```bash
# Get failed job details
kubectl describe job <job-name> -n petrosa-apps

# Check pod logs for the failed job
kubectl logs <pod-name> -n petrosa-apps

# Get events
kubectl get events -n petrosa-apps --sort-by=.metadata.creationTimestamp
```

## Environment Variables

The application uses the following environment variables (configured via Kubernetes secrets):

- `BINANCE_API_KEY`: Binance API key
- `BINANCE_SECRET_KEY`: Binance API secret
- `POSTGRES_CONNECTION_STRING`: PostgreSQL database URL
- `MONGO_CONNECTION_STRING`: MongoDB database URL (optional)
- `REDIS_URL`: Redis cache URL (optional)
- `ENVIRONMENT`: Set to "production"

## Security Considerations

1. **API Keys**: Store in Kubernetes secrets, never in code
2. **Network Policies**: Limit egress to required endpoints only
3. **RBAC**: Use least-privilege service accounts
4. **Image Security**: Regularly update base images and scan for vulnerabilities

## Scaling

The application is designed to run as scheduled jobs (CronJobs). To scale:

1. **Adjust schedules** in CronJob manifests
2. **Add more symbols** to the production symbols list
3. **Increase job parallelism** if needed
4. **Monitor resource usage** and adjust limits/requests

## Backup and Recovery

Ensure you have backups of:
1. Database data (PostgreSQL/MongoDB)
2. Kubernetes manifests and secrets
3. Docker images in your registry

## Support

For issues or questions:
1. Check the logs using kubectl commands above
2. Review the GitHub Actions workflow logs
3. Verify all secrets are properly configured
4. Ensure your MicroK8s cluster is healthy and accessible
