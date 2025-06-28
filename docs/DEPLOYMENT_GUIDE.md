# 🚀 Kubernetes Deployment Guide

This guide will help you deploy the Binance Data Extractor to your Kubernetes cluster using the automated GitHub Actions workflow.

## 📋 Prerequisites

### 1. **Kubernetes Cluster**
- Kubernetes v1.20+ 
- `kubectl` configured and connected to your cluster
- Sufficient resources (see resource requirements below)

### 2. **GitHub Repository Setup**
- This repository pushed to GitHub
- Docker Hub account and access token created

### 3. **Required Secrets**
You'll need to configure these secrets in your Kubernetes cluster and GitHub repository.

## 🔧 Setup Instructions

### Step 1: Configure GitHub Secrets

In your GitHub repository, go to **Settings → Secrets and Variables → Actions** and add:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `KUBE_CONFIG_DATA` | Base64 encoded kubeconfig file | `base64 < ~/.kube/config` |
| `DOCKERHUB_USERNAME` | Your Docker Hub username | `your-dockerhub-username` |
| `DOCKERHUB_TOKEN` | Docker Hub access token | `dckr_pat_...` |

**Creating Docker Hub Access Token:**
1. Go to [Docker Hub Account Settings](https://hub.docker.com/settings/security)
2. Click "New Access Token"
3. Give it a name like "GitHub Actions"
4. Copy the generated token to `DOCKERHUB_TOKEN` secret

### Step 2: Prepare Kubernetes Secrets

**Option A: Using the provided script (Recommended)**
```bash
# Run the secret encoding script
python scripts/encode_secrets.py

# This will create k8s/secrets-generated.yaml with your encoded credentials
kubectl apply -f k8s/secrets-generated.yaml
```

**Option B: Manual creation**
```bash
# Create API secrets
kubectl create secret generic binance-api-secret -n petrosa-apps \
  --from-literal=api-key=YOUR_BINANCE_API_KEY \
  --from-literal=api-secret=YOUR_BINANCE_API_SECRET

# Create database secret  
kubectl create secret generic database-secret -n petrosa-apps \
  --from-literal=mysql-uri="mysql+pymysql://user:pass@host:port/database"
```

### Step 3: Deploy via GitHub Actions

1. **Push to main branch** - The workflow will automatically trigger
2. **Monitor the deployment** in the GitHub Actions tab
3. **Verify deployment** in your cluster

```bash
# Check deployment status
kubectl get cronjobs -l app=binance-extractor -n petrosa-apps
kubectl get jobs -l app=binance-extractor -n petrosa-apps
```

### Step 4: Manual Testing (Optional)

Test the deployment with a one-time job:

```bash
# Run the test job
kubectl apply -f k8s/job.yaml

# Check job status
kubectl get jobs
kubectl logs job/python-test-job

# Run production extractor manually
kubectl logs job/binance-extractor-manual-job -f
```

## 📊 What Gets Deployed

### **CronJobs (Automated Extraction)**
| Name | Schedule | Description |
|------|----------|-------------|
| `binance-klines-m15-production` | Every 15 minutes | 15-minute klines |
| `binance-klines-h1-production` | Every hour at :05 | 1-hour klines |
| `binance-klines-d1-production` | Daily at 00:10 UTC | Daily klines |

### **Resource Requirements**
- **Memory**: 256Mi request, 512Mi limit per job
- **CPU**: 200m request, 500m limit per job  
- **Storage**: Minimal (logs only)

### **Security Features**
- ✅ Non-root containers
- ✅ Read-only root filesystem
- ✅ Dropped capabilities
- ✅ Secret management
- ✅ RBAC (if needed)

## 🔍 Monitoring & Troubleshooting

### **Check CronJob Status**
```bash
# List all CronJobs
kubectl get cronjobs -l app=binance-extractor -n petrosa-apps

# Check recent jobs
kubectl get jobs -l app=binance-extractor -n petrosa-apps --sort-by=.metadata.creationTimestamp

# View CronJob details
kubectl describe cronjob binance-klines-m15-production -n petrosa-apps
```

### **View Logs**
```bash
# Recent logs from any extraction job
kubectl logs -l component=klines-extractor -n petrosa-apps --tail=100

# Logs from specific job
kubectl logs job/binance-klines-m15-production-1234567890 -n petrosa-apps

# Follow logs in real-time
kubectl logs -l component=klines-extractor -n petrosa-apps -f
```

### **Common Issues**

**❌ Jobs failing with "ImagePullBackOff"**
- Check if Docker Hub credentials are correctly configured in GitHub secrets
- Verify the image exists: `docker pull your-username/petrosa-binance-extractor:latest`
- Ensure `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets are set

**❌ Jobs failing with "Secret not found"** 
- Ensure secrets are created: `kubectl get secrets -n petrosa-apps | grep binance`
- Verify secret names match the manifests

**❌ Database connection errors**
- Check MySQL URI in the database secret
- Verify database is accessible from cluster

## 🎯 Production Best Practices

### **Resource Optimization**
```bash
# Monitor resource usage
kubectl top pods -l app=binance-extractor -n petrosa-apps

# Adjust resource limits if needed
kubectl patch cronjob binance-klines-m15-production -n petrosa-apps -p '{"spec":{"jobTemplate":{"spec":{"template":{"spec":{"containers":[{"name":"klines-extractor","resources":{"limits":{"memory":"1Gi"}}}]}}}}}}'
```

### **Scaling**
```bash
# Increase worker count for faster processing
kubectl patch cronjob binance-klines-m15-production -n petrosa-apps -p '{"spec":{"jobTemplate":{"spec":{"template":{"spec":{"containers":[{"name":"klines-extractor","args":["--period=15m","--max-workers=10","--db-adapter=mysql"]}]}}}}}}'
```

### **Monitoring Alerts**
Consider setting up alerts for:
- Failed jobs (`kubectl get jobs -l app=binance-extractor -n petrosa-apps --field-selector=status.failed=1`)
- Long-running jobs (> 10 minutes for 15m extractions)
- Missing data in database

## 🔄 Updates & Maintenance

### **Updating the Application**
1. Push changes to the `main` branch
2. GitHub Actions will automatically build and push to Docker Hub
3. CronJobs will use the new image on next scheduled run

### **Manual Image Update**
```bash
# Force update to latest image
kubectl patch cronjob binance-klines-m15-production -n petrosa-apps -p '{"spec":{"jobTemplate":{"spec":{"template":{"spec":{"containers":[{"name":"klines-extractor","image":"your-username/petrosa-binance-extractor:latest"}]}}}}}}'
```

### **Backup & Recovery**
- Database backups are handled by your MySQL setup
- Configuration is stored in this Git repository
- Secrets should be backed up securely

## 🎉 Success Metrics

Your deployment is successful when:
- ✅ CronJobs are created and scheduled
- ✅ Jobs run every 15 minutes without failures  
- ✅ Data is being written to your MySQL database
- ✅ Logs show successful extractions with no errors
- ✅ Resource usage stays within limits

Monitor these with:
```bash
# Quick health check
kubectl get cronjobs,jobs,pods -l app=binance-extractor -n petrosa-apps
```

Your production Binance data extraction system is now fully automated! 🚀
