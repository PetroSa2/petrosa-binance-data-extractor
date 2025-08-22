# VERSION_PLACEHOLDER Violation Fix

## 🚨 Issue Identified

During the socket-client NATS connection investigation, a critical violation of the `VERSION_PLACEHOLDER` rule was discovered.

### Problem
The socket-client deployment was using a hardcoded image version instead of the `VERSION_PLACEHOLDER`:
- **Violation**: `image: yurisa2/petrosa-socket-client:v1.0.65`
- **Correct**: `image: yurisa2/petrosa-socket-client:VERSION_PLACEHOLDER`

## 🔧 Root Cause

The deployment was created with a specific version tag instead of using the `VERSION_PLACEHOLDER` that should be automatically substituted by the CI/CD pipeline.

## ✅ Resolution

### 1. Created Proper Kubernetes Manifests

Created standardized Kubernetes manifests in `k8s/socket-client/` that follow the `VERSION_PLACEHOLDER` rule:

- **deployment.yaml**: Uses `VERSION_PLACEHOLDER` for image tag
- **service.yaml**: Uses `VERSION_PLACEHOLDER` for labels
- **hpa.yaml**: Uses `VERSION_PLACEHOLDER` for labels
- **network-policy.yaml**: Uses `VERSION_PLACEHOLDER` for labels
- **configmap.yaml**: Uses `VERSION_PLACEHOLDER` for labels

### 2. Key Changes Made

#### Deployment Template
```yaml
# ✅ CORRECT: Uses VERSION_PLACEHOLDER
image: yurisa2/petrosa-socket-client:VERSION_PLACEHOLDER

# ❌ INCORRECT: Hardcoded version
image: yurisa2/petrosa-socket-client:v1.0.65
```

#### Labels
```yaml
# ✅ CORRECT: Uses VERSION_PLACEHOLDER
labels:
  app: socket-client
  component: websocket-client
  version: VERSION_PLACEHOLDER

# ❌ INCORRECT: Hardcoded version
labels:
  app: socket-client
  component: websocket-client
  version: v1.0.65
```

#### OpenTelemetry Configuration
```yaml
# ✅ CORRECT: Uses VERSION_PLACEHOLDER
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "service.name=socket-client,service.version=VERSION_PLACEHOLDER"

# ❌ INCORRECT: Hardcoded version
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "service.name=socket-client,service.version=v1.0.65"
```

## 📋 VERSION_PLACEHOLDER Rules

### 1. Never Manually Change VERSION_PLACEHOLDER
- **Rule**: `VERSION_PLACEHOLDER` must never be manually replaced with specific version values
- **Reason**: It's automatically substituted by the CI/CD pipeline during deployment
- **Impact**: Manual changes break the automated versioning system

### 2. Always Use VERSION_PLACEHOLDER in Templates
- **Image tags**: `image: repository:VERSION_PLACEHOLDER`
- **Labels**: `version: VERSION_PLACEHOLDER`
- **Annotations**: `version: VERSION_PLACEHOLDER`
- **Environment variables**: `service.version=VERSION_PLACEHOLDER`

### 3. CI/CD Pipeline Responsibility
- **Substitution**: The CI/CD pipeline automatically replaces `VERSION_PLACEHOLDER` with actual version values
- **Consistency**: Ensures all resources use the same version
- **Automation**: Eliminates manual version management errors

## 🔄 Deployment Process

### 1. Using Centralized Manifests
```bash
# Deploy using centralized manifests
kubectl --kubeconfig=k8s/kubeconfig.yaml apply -f k8s/socket-client/

# The CI/CD pipeline will automatically substitute VERSION_PLACEHOLDER
```

### 2. Version Substitution
The CI/CD pipeline performs the following substitutions:
- `VERSION_PLACEHOLDER` → `v1.0.66` (or current version)
- All resources get consistent versioning
- No manual intervention required

## 🛡️ Prevention Measures

### 1. Template Validation
- **Pre-deployment checks**: Validate that `VERSION_PLACEHOLDER` is present
- **Automated testing**: CI/CD pipeline validates templates
- **Documentation**: Clear guidelines for all developers

### 2. Code Review Process
- **Mandatory check**: Reviewers must verify `VERSION_PLACEHOLDER` usage
- **Template compliance**: Ensure all new resources follow the pattern
- **Version consistency**: Verify no hardcoded versions

### 3. Monitoring and Alerts
- **Deployment monitoring**: Alert on manual version changes
- **Template validation**: Automated checks in CI/CD
- **Audit logging**: Track all version-related changes

## 📚 Related Documentation

- **[Troubleshooting and Best Practices](TROUBLESHOOTING_AND_BEST_PRACTICES.md)** - Comprehensive troubleshooting guide
- **[Architecture Guide](ARCHITECTURE.md)** - System architecture and design decisions
- **[CI/CD Configuration](CI_CD_CONFIGURATION.md)** - Deployment automation setup

## 🎯 Key Takeaways

### 1. Always Use VERSION_PLACEHOLDER
- Never hardcode version values in Kubernetes manifests
- Let the CI/CD pipeline handle version substitution
- Maintain consistency across all resources

### 2. Follow Template Standards
- Use centralized templates from `petrosa_k8s/k8s/`
- Ensure all resources follow the same pattern
- Validate templates before deployment

### 3. Automated Versioning
- Trust the CI/CD pipeline for version management
- Avoid manual version interventions
- Maintain audit trail of version changes

---

**Status**: ✅ **RESOLVED** - Proper templates created with VERSION_PLACEHOLDER
**Date**: 2025-08-22
**Impact**: Prevents future VERSION_PLACEHOLDER violations
