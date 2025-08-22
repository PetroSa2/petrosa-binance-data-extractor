# CI/CD Quick Reference Guide

## 🚨 Emergency Fixes

### Issue: ImagePullBackOff with VERSION_PLACEHOLDER

**Immediate Fix:**
```bash
# ✅ DEPLOY VIA CI/CD (Recommended)
git add .
git commit -m "Fix configuration"
git push origin main

# ❌ NEVER DO THIS - Manual replacement breaks CI/CD
# sed -i 's/VERSION_PLACEHOLDER/v1.0.71/g' k8s/*.yaml
```

### Issue: ConfigMap Key Not Found

**Immediate Fix:**
```bash
# Apply configmap first
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/configmap.yaml

# Verify keys exist
kubectl --kubeconfig=k8s/kubeconfig.yaml get configmap petrosa-binance-data-extractor-config -n petrosa-apps -o yaml
```

### Issue: Image Name Mismatch

**Immediate Fix:**
```bash
# Check current image names in manifests
grep -r "image:" k8s/*.yaml

# Check CI/CD image name
grep -r "images:" .github/workflows/deploy.yml

# Fix inconsistency and push
git add .
git commit -m "Fix image name consistency"
git push origin main
```

## 🔍 Quick Diagnostics

### Check Deployment Status
```bash
# Pod status
kubectl --kubeconfig=k8s/kubeconfig.yaml get pods -n petrosa-apps -l app=binance-data-extractor

# Pod events
kubectl --kubeconfig=k8s/kubeconfig.yaml describe pod -n petrosa-apps -l app=binance-data-extractor

# Configmap
kubectl --kubeconfig=k8s/kubeconfig.yaml get configmap petrosa-binance-data-extractor-config -n petrosa-apps -o yaml
```

### Check Image Issues
```bash
# Verify image exists
docker pull yurisa2/petrosa-binance-data-extractor:v1.0.71

# Check if VERSION_PLACEHOLDER is still in manifests
grep -r "VERSION_PLACEHOLDER" k8s/
```

## ✅ Correct Deployment Process

### 1. Local Testing
```bash
# Test locally first
make pipeline
make build
make run-docker
```

### 2. Production Deployment
```bash
# ✅ ONLY WAY - Deploy via CI/CD
git add .
git commit -m "Update configuration"
git push origin main
```

### 3. Verify Deployment
```bash
# Check CI/CD status on GitHub
# Wait for pipeline to complete
# Verify pods are running
kubectl --kubeconfig=k8s/kubeconfig.yaml get pods -n petrosa-apps -l app=binance-data-extractor
```

## 🚫 Common Mistakes to Avoid

1. **❌ Never manually replace VERSION_PLACEHOLDER**
2. **❌ Never manually apply manifests with VERSION_PLACEHOLDER**
3. **❌ Never use inconsistent image names**
4. **❌ Never reference non-existent configmap keys**
5. **❌ Never create new secrets (use existing ones)**

## ✅ Best Practices

1. **✅ Always deploy via CI/CD**
2. **✅ Test locally first with make pipeline**
3. **✅ Use consistent image names everywhere**
4. **✅ Validate all configmap keys exist**
5. **✅ Use service-specific configmaps**
6. **✅ Monitor deployment status after push**

## 🔧 Configuration Checklist

Before pushing to CI/CD:

- [ ] All configmap keys referenced in deployment exist
- [ ] Image names are consistent (CI/CD vs manifests)
- [ ] VERSION_PLACEHOLDER is used in all manifests
- [ ] No manual version replacements
- [ ] Local pipeline passes (`make pipeline`)

After CI/CD deployment:

- [ ] Pods are in Running state
- [ ] No ImagePullBackOff errors
- [ ] All environment variables are set
- [ ] Services are accessible
- [ ] Health checks are passing

## 📞 Emergency Contacts

- **CI/CD Issues**: Check GitHub Actions
- **Kubernetes Issues**: Check pod events and logs
- **Configuration Issues**: Verify configmap keys
- **Image Issues**: Check Docker Hub and image names

## 📚 Related Documentation

- [CI_CD_BEST_PRACTICES.md](CI_CD_BEST_PRACTICES.md) - Detailed best practices
- [EXTRACTOR_CONFIG_FIX_SUMMARY.md](EXTRACTOR_CONFIG_FIX_SUMMARY.md) - Configuration fixes
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - General deployment guide
