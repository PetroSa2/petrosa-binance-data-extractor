# Quick Reference Card

## 🚀 Essential Commands

### Cluster Connection
```bash
# Use repository's kubeconfig
export KUBECONFIG=k8s/kubeconfig.yaml

# Or use explicit flag
kubectl --kubeconfig=k8s/kubeconfig.yaml cluster-info

# Verify connection
kubectl --kubeconfig=k8s/kubeconfig.yaml get nodes
```

### Local Development
```bash
# Start MicroK8s
microk8s start
microk8s enable dns storage

# Deploy locally
./scripts/deploy-local.sh

# Port forward NATS
kubectl --kubeconfig=k8s/kubeconfig.yaml port-forward -n nats svc/nats-server 4222:4222 &
```

### Local Deployment
```bash
# Deploy to local cluster
./scripts/deploy-local.sh

# Or manually deploy
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/namespace.yaml

# Check status
kubectl --kubeconfig=k8s/kubeconfig.yaml get all -n petrosa-apps
```

## 🔍 Debugging Commands

### Check System Status
```bash
# Overall status
kubectl --kubeconfig=k8s/kubeconfig.yaml get all -n petrosa-apps

# CronJobs
kubectl --kubeconfig=k8s/kubeconfig.yaml get cronjobs -n petrosa-apps

# Recent jobs
kubectl --kubeconfig=k8s/kubeconfig.yaml get jobs -n petrosa-apps --sort-by=.metadata.creationTimestamp

# Pod logs
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -f deployment/binance-extractor -n petrosa-apps
```

### Common Issues

#### MicroK8s Connection Issues
```bash
# Check MicroK8s status
microk8s status

# Start MicroK8s if needed
microk8s start

# Test connection with kubeconfig
kubectl --kubeconfig=k8s/kubeconfig.yaml cluster-info
```

#### Certificate Issues
```bash
# Use insecure flag
kubectl --kubeconfig=k8s/kubeconfig.yaml --insecure-skip-tls-verify get nodes

# Or set environment variable
export KUBECONFIG=k8s/kubeconfig.yaml
kubectl --insecure-skip-tls-verify get nodes
```

#### Port Forwarding Issues
```bash
# Check if port is in use
netstat -an | grep 4222

# Kill existing port forwards
pkill -f "kubectl port-forward"

# Restart port forward with kubeconfig
kubectl --kubeconfig=k8s/kubeconfig.yaml port-forward -n nats svc/nats-server 4222:4222 &
```

## 🧪 Testing

### Run Tests
```bash
# All tests
python -m pytest tests/ -v

# Specific test
python -m pytest tests/test_extract_klines.py -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Integration Tests
```bash
# Pipeline simulation
python scripts/test_pipeline_simulation.py

# Production simulation
python scripts/test_production_simulation.py

# NATS messaging
python scripts/test_nats_messaging.py
```

## 📊 Monitoring

### View Logs
```bash
# Application logs
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -f deployment/binance-extractor -n petrosa-apps

# Job logs
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -f job/<job-name> -n petrosa-apps

# Recent logs
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -l app=binance-extractor -n petrosa-apps --since=1h
```

### Resource Monitoring
```bash
# Resource usage
kubectl --kubeconfig=k8s/kubeconfig.yaml top pods -n petrosa-apps

# Events
kubectl --kubeconfig=k8s/kubeconfig.yaml get events -n petrosa-apps --sort-by=.metadata.creationTimestamp

# Pod details
kubectl --kubeconfig=k8s/kubeconfig.yaml describe pod <pod-name> -n petrosa-apps
```

## 🔧 Environment Setup

### Prerequisites Checklist
- [ ] Python 3.11+ installed
- [ ] Docker running
- [ ] kubectl installed
- [ ] MicroK8s installed and running
- [ ] Virtual environment activated
- [ ] Environment variables set

### Environment Variables
```bash
# Required
DB_ADAPTER=mysql
MYSQL_URI=mysql+pymysql://username:password@localhost:3306/binance_data

# Optional
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
NATS_ENABLED=true
NATS_URL=nats://localhost:4222
```

## 🚨 Emergency Procedures

### Cluster Issues
1. Check MicroK8s status: `microk8s status`
2. Start MicroK8s if needed: `microk8s start`
3. Use repository kubeconfig: `export KUBECONFIG=k8s/kubeconfig.yaml`

### Application Issues
1. Check pod logs: `kubectl --kubeconfig=k8s/kubeconfig.yaml logs -f deployment/binance-extractor -n petrosa-apps`
2. Check pod status: `kubectl --kubeconfig=k8s/kubeconfig.yaml describe pod <pod-name> -n petrosa-apps`
3. Restart deployment: `kubectl --kubeconfig=k8s/kubeconfig.yaml rollout restart deployment/binance-extractor -n petrosa-apps`

### Database Issues
1. Test connection from pod
2. Verify credentials and connection string
3. Check database service status

## 📚 Useful Scripts

- `./scripts/deploy-local.sh` - Local deployment
- `./scripts/deploy-production.sh` - Production deployment
- `./scripts/validate-production.sh` - Production validation
- `./scripts/build-multiarch.sh` - Multi-architecture builds
- `./scripts/create-release.sh` - Release management

## 🔗 Quick Links

- [Full Setup Guide](REPOSITORY_SETUP_GUIDE.md)
- [Operations Guide](OPERATIONS_GUIDE.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Local Deployment](LOCAL_DEPLOY.md)
