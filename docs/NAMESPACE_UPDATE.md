# Kubernetes Namespace Setup Guide

## 🏗️ Namespace Configuration

This guide covers Kubernetes namespace setup, migration, and management for the Petrosa Binance Data Extractor.

## 📋 Namespace Overview

### Current Namespace: `petrosa-apps`

The application is deployed in the `petrosa-apps` namespace to provide:
- **Resource Isolation**: Separate from other applications
- **Security Boundaries**: RBAC and network policies
- **Resource Management**: CPU and memory limits
- **Monitoring**: Namespace-specific metrics

## 🔧 Namespace Setup

### 1. Create Namespace

```bash
# Create namespace
kubectl create namespace petrosa-apps

# Verify creation
kubectl get namespace petrosa-apps
```

### 2. Set Default Namespace

```bash
# Set as default for current context
kubectl config set-context --current --namespace=petrosa-apps

# Verify default namespace
kubectl config view --minify --output 'jsonpath={..namespace}'
```

### 3. Namespace Resource Quotas

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: petrosa-apps-quota
  namespace: petrosa-apps
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    pods: "20"
```

## 🔐 Security Configuration

### 1. Service Account

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: binance-extractor
  namespace: petrosa-apps
```

### 2. RBAC Configuration

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: binance-extractor-role
  namespace: petrosa-apps
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["batch"]
  resources: ["jobs", "cronjobs"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: binance-extractor-rolebinding
  namespace: petrosa-apps
subjects:
- kind: ServiceAccount
  name: binance-extractor
  namespace: petrosa-apps
roleRef:
  kind: Role
  name: binance-extractor-role
  apiGroup: rbac.authorization.k8s.io
```

## 🔄 Migration from Default Namespace

### If Deployed in Default Namespace

1. **Export Resources**:
   ```bash
   # Export current resources
   kubectl get all -l app=binance-extractor -o yaml > current-deployment.yaml
   ```

2. **Update Namespace**:
   ```bash
   # Update namespace in manifests
   sed -i 's/namespace: default/namespace: petrosa-apps/g' current-deployment.yaml
   ```

3. **Delete Old Resources**:
   ```bash
   # Delete from default namespace
   kubectl delete all -l app=binance-extractor
   ```

4. **Deploy to New Namespace**:
   ```bash
   # Apply to new namespace
   kubectl apply -f current-deployment.yaml
   ```

## 📊 Resource Management

### Resource Limits

Each CronJob has appropriate resource limits:

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "512Mi"
  limits:
    cpu: "2"
    memory: "2Gi"
```

### Horizontal Pod Autoscaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: binance-extractor-hpa
  namespace: petrosa-apps
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: binance-extractor
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## 🔍 Monitoring and Logging

### Namespace-Specific Monitoring

```bash
# View all resources in namespace
kubectl get all -n petrosa-apps

# View CronJob status
kubectl get cronjobs -n petrosa-apps

# View recent pods
kubectl get pods -n petrosa-apps --sort-by=.metadata.creationTimestamp

# View logs
kubectl logs -l app=binance-extractor -n petrosa-apps
```

### Prometheus Monitoring

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: binance-extractor-monitor
  namespace: petrosa-apps
spec:
  selector:
    matchLabels:
      app: binance-extractor
  endpoints:
  - port: metrics
    interval: 30s
```

## 🛠️ Troubleshooting

### Common Namespace Issues

1. **Resource Quota Exceeded**:
   ```bash
   # Check quota usage
   kubectl describe resourcequota -n petrosa-apps
   
   # Check resource usage
   kubectl top pods -n petrosa-apps
   ```

2. **Permission Denied**:
   ```bash
   # Check service account
   kubectl get serviceaccount -n petrosa-apps
   
   # Check RBAC
   kubectl auth can-i create jobs --namespace petrosa-apps
   ```

3. **Namespace Not Found**:
   ```bash
   # List all namespaces
   kubectl get namespaces
   
   # Create if missing
   kubectl create namespace petrosa-apps
   ```

### Debug Commands

```bash
# Check namespace status
kubectl get namespace petrosa-apps -o yaml

# View namespace events
kubectl get events -n petrosa-apps

# Check resource usage
kubectl describe namespace petrosa-apps
```

## 📚 Related Documentation

- [Local Deployment](LOCAL_DEPLOY.md) - Local development setup
- [Deployment Guide](DEPLOYMENT_GUIDE.md) - Production deployment
- [Operations Guide](OPERATIONS_GUIDE.md) - Day-to-day operations
- [Kubernetes Manifests](../k8s/) - Deployment configurations
