# CI/CD Best Practices for Petrosa Systems

## Overview

This document outlines the best practices for CI/CD deployment in the Petrosa ecosystem to prevent recurring issues and ensure consistent, reliable deployments.

## Critical Rules

### 1. **NEVER MANUALLY REPLACE VERSION_PLACEHOLDER**

**❌ WRONG - Never do this:**
```bash
# NEVER manually replace VERSION_PLACEHOLDER
sed -i 's/VERSION_PLACEHOLDER/v1.0.71/g' k8s/*.yaml
```

**✅ CORRECT - Let CI/CD handle it:**
```yaml
# In Kubernetes manifests, always use:
image: yurisa2/petrosa-binance-data-extractor:VERSION_PLACEHOLDER
```

**Why:** `VERSION_PLACEHOLDER` is automatically replaced by the CI/CD pipeline with the correct semantic version.

### 2. **CONSISTENT IMAGE NAMING**

**❌ WRONG - Inconsistent naming:**
```yaml
# CI/CD builds: petrosa-binance-extractor
# Manifests use: petrosa-binance-data-extractor
```

**✅ CORRECT - Consistent naming:**
```yaml
# Both CI/CD and manifests use the same name:
image: yurisa2/petrosa-binance-data-extractor:VERSION_PLACEHOLDER
```

### 3. **CONFIGMAP KEY CONSISTENCY**

**❌ WRONG - Missing keys:**
```yaml
# Deployment references keys that don't exist in configmap
- name: API_RATE_LIMIT_PER_MINUTE
  valueFrom:
    configMapKeyRef:
      name: petrosa-binance-data-extractor-config
      key: API_RATE_LIMIT_PER_MINUTE  # ❌ Key doesn't exist
```

**✅ CORRECT - All keys present:**
```yaml
# Configmap has all required keys
data:
  API_RATE_LIMIT_PER_MINUTE: "1200"
  REQUEST_DELAY_SECONDS: "0.1"
  MIN_BATCH_SIZE: "100"
  MAX_BATCH_SIZE: "5000"
```

## Deployment Process

### 1. **Local Development**

```bash
# ✅ CORRECT - Use local pipeline for testing
make pipeline

# ✅ CORRECT - Test with local Docker image
make build
make run-docker
```

### 2. **Production Deployment**

```bash
# ✅ CORRECT - Deploy via CI/CD only
git push origin main  # Triggers CI/CD pipeline

# ❌ WRONG - Never manually apply with VERSION_PLACEHOLDER
kubectl apply -f k8s/  # Will fail with VERSION_PLACEHOLDER
```

### 3. **CI/CD Pipeline Steps**

1. **Create Release**: Generates semantic version
2. **Build & Push**: Creates Docker image with version tag
3. **Deploy**: Replaces `VERSION_PLACEHOLDER` and applies manifests
4. **Verify**: Checks deployment status

## Common Issues and Solutions

### Issue 1: ImagePullBackOff with VERSION_PLACEHOLDER

**Symptoms:**
```
Failed to pull image "yurisa2/petrosa-binance-data-extractor:VERSION_PLACEHOLDER"
```

**Root Cause:** Manual deployment without CI/CD version replacement

**Solution:**
```bash
# ✅ CORRECT - Deploy via CI/CD
git push origin main

# ❌ WRONG - Don't manually apply
kubectl apply -f k8s/
```

### Issue 2: ConfigMap Key Not Found

**Symptoms:**
```
configmap "petrosa-binance-data-extractor-config" not found
```

**Root Cause:** Configmap not applied or missing keys

**Solution:**
```bash
# ✅ CORRECT - Apply configmap first
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/configmap.yaml

# ✅ CORRECT - Verify keys exist
kubectl --kubeconfig=k8s/kubeconfig.yaml get configmap petrosa-binance-data-extractor-config -n petrosa-apps -o yaml
```

### Issue 3: Image Name Mismatch

**Symptoms:**
```
Failed to pull image "yurisa2/petrosa-binance-extractor:v1.0.71"
```

**Root Cause:** CI/CD builds different image name than manifests expect

**Solution:**
```yaml
# ✅ CORRECT - Ensure consistency
# In .github/workflows/deploy.yml:
images: ${{ secrets.DOCKERHUB_USERNAME }}/petrosa-binance-data-extractor

# In k8s/*.yaml:
image: yurisa2/petrosa-binance-data-extractor:VERSION_PLACEHOLDER
```

## Configuration Management

### 1. **Service-Specific ConfigMaps**

Each service should have its own configmap:

```yaml
# ✅ CORRECT - Service-specific configmap
apiVersion: v1
kind: ConfigMap
metadata:
  name: petrosa-binance-data-extractor-config  # Service-specific name
  namespace: petrosa-apps
data:
  # Service-specific configuration
  BINANCE_API_URL: "https://fapi.binance.com"
  MAX_WORKERS: "4"
```

### 2. **Common Configuration**

Shared configuration goes in common configmap:

```yaml
# ✅ CORRECT - Common configmap
apiVersion: v1
kind: ConfigMap
metadata:
  name: petrosa-common-config
  namespace: petrosa-apps
data:
  # Shared configuration
  NATS_URL: "nats://nats-server.nats:4222"
  ENABLE_OTEL: "false"
```

### 3. **Secrets Management**

Sensitive data goes in secrets:

```yaml
# ✅ CORRECT - Use existing secrets
- name: MYSQL_URI
  valueFrom:
    secretKeyRef:
      name: petrosa-sensitive-credentials  # Use existing secret
      key: MYSQL_URI
```

## Validation Checklist

### Before Deployment

- [ ] All configmap keys referenced in deployment exist
- [ ] Image names are consistent between CI/CD and manifests
- [ ] `VERSION_PLACEHOLDER` is used in all manifests
- [ ] Secrets are properly configured
- [ ] Network policies allow required traffic

### After Deployment

- [ ] Pods are in Running state
- [ ] No ImagePullBackOff errors
- [ ] All environment variables are set correctly
- [ ] Services are accessible
- [ ] Health checks are passing

## Troubleshooting Commands

### Check Deployment Status

```bash
# Check pod status
kubectl --kubeconfig=k8s/kubeconfig.yaml get pods -n petrosa-apps -l app=binance-data-extractor

# Check pod events
kubectl --kubeconfig=k8s/kubeconfig.yaml describe pod -n petrosa-apps -l app=binance-data-extractor

# Check deployment status
kubectl --kubeconfig=k8s/kubeconfig.yaml rollout status deployment/petrosa-binance-data-extractor -n petrosa-apps
```

### Check Configuration

```bash
# Verify configmap
kubectl --kubeconfig=k8s/kubeconfig.yaml get configmap petrosa-binance-data-extractor-config -n petrosa-apps -o yaml

# Check environment variables
kubectl --kubeconfig=k8s/kubeconfig.yaml describe deployment petrosa-binance-data-extractor -n petrosa-apps
```

### Check Image Issues

```bash
# Verify image exists
docker pull yurisa2/petrosa-binance-data-extractor:v1.0.71

# Check image tags
docker images yurisa2/petrosa-binance-data-extractor
```

## Emergency Procedures

### Rollback Deployment

```bash
# Rollback to previous version
kubectl --kubeconfig=k8s/kubeconfig.yaml rollout undo deployment/petrosa-binance-data-extractor -n petrosa-apps

# Check rollback status
kubectl --kubeconfig=k8s/kubeconfig.yaml rollout status deployment/petrosa-binance-data-extractor -n petrosa-apps
```

### Fix Configuration Issues

```bash
# Apply updated configmap
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/configmap.yaml

# Restart deployment to pick up new config
kubectl --kubeconfig=k8s/kubeconfig.yaml rollout restart deployment/petrosa-binance-data-extractor -n petrosa-apps
```

## Best Practices Summary

1. **Always deploy via CI/CD** - Never manually apply manifests with `VERSION_PLACEHOLDER`
2. **Maintain image name consistency** - Ensure CI/CD and manifests use same image names
3. **Validate configmap keys** - All referenced keys must exist in configmap
4. **Use service-specific configmaps** - Each service has its own configuration
5. **Test locally first** - Use `make pipeline` for local testing
6. **Monitor deployment status** - Always verify pods are running after deployment
7. **Document changes** - Update documentation when configuration changes
8. **Use existing secrets** - Don't create new secrets, use `petrosa-sensitive-credentials`

## Related Documentation

- [EXTRACTOR_CONFIG_FIX_SUMMARY.md](EXTRACTOR_CONFIG_FIX_SUMMARY.md) - Specific fix for extractor configuration
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - General deployment guide
- [KUBERNETES_ISSUES_INVESTIGATION_AND_FIXES.md](KUBERNETES_ISSUES_INVESTIGATION_AND_FIXES.md) - Common Kubernetes issues
