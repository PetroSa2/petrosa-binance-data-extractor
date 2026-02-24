# NATS Kubernetes Best Practices

This document provides comprehensive guidance on configuring NATS connections in Kubernetes environments for all Petrosa systems.

## ⚠️ **CRITICAL RULE: Always Use Kubernetes Service Names**

**NEVER use external IP addresses for NATS connections in Kubernetes. Always use Kubernetes service names.**

## Service Name Configuration

### ✅ **Correct Configuration (Recommended)**

```yaml
# ConfigMap configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: petrosa-common-config
  namespace: petrosa-apps
data:
  NATS_URL: "nats://nats-server.nats.svc.cluster.local:4222"  # ✅ Best: Full DNS name
  NATS_ENABLED: "true"
```

### ✅ **Correct Configuration (Alternative)**

```yaml
# ConfigMap configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: petrosa-common-config
  namespace: petrosa-apps
data:
  NATS_URL: "nats://nats-server:4222"  # ✅ Acceptable: Short service name
  NATS_ENABLED: "true"
```

### ❌ **Incorrect Configuration**

```yaml
# ConfigMap configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: petrosa-common-config
  namespace: petrosa-apps
data:
  NATS_URL: "nats://192.168.194.253:4222"  # ❌ Wrong: External IP
  NATS_ENABLED: "true"
```

## Service Name Formats

### 1. **Cross-Namespace (Recommended)**
```bash
nats://nats-server.nats.svc.cluster.local:4222
```

### 2. **Cross-Namespace (Short Form)**
```bash
nats://nats-server.nats:4222
```

### 3. **Different Namespace (Full DNS)**
```bash
nats://nats-server.nats-namespace.svc.cluster.local:4222
```

### 4. **Cross-Namespace (Short Form)**
```bash
nats://nats-server.nats-namespace:4222
```

## Why Full DNS Names Are Better

### **Advantages of Full DNS Names**
1. **Explicit and Clear**: No ambiguity about which service is being referenced
2. **DNS Resolution**: Guaranteed to work even if short names have conflicts
3. **Debugging**: Easier to troubleshoot DNS resolution issues
4. **Portability**: Works consistently across different cluster configurations
5. **Documentation**: Self-documenting - shows exact namespace and service
6. **Future-Proof**: Less likely to break with cluster configuration changes

## Benefits of Using Kubernetes Service Names

### 1. **Automatic Service Discovery**
- Kubernetes DNS automatically resolves service names
- No need to hardcode IP addresses
- Survives pod restarts and scaling events

### 2. **Load Balancing**
- Traffic automatically distributed across NATS replicas
- Built-in health checking and failover
- No manual load balancer configuration needed

### 3. **Network Security**
- Stays within cluster network
- Works with Kubernetes network policies
- Avoids external network dependencies

### 4. **Environment Portability**
- Same configuration works across dev, staging, prod
- No environment-specific IP addresses
- Consistent behavior across deployments

### 5. **Reliability**
- Survives node failures and pod restarts
- Automatic reconnection to healthy endpoints
- No manual IP address updates required

## Configuration Examples

### **Deployment Configuration**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: petrosa-binance-data-extractor
spec:
  template:
    spec:
      containers:
      - name: data-extractor
        env:
        - name: NATS_ENABLED
          valueFrom:
            configMapKeyRef:
              name: petrosa-common-config
              key: NATS_ENABLED
        - name: NATS_URL
          valueFrom:
            configMapKeyRef:
              name: petrosa-common-config
              key: NATS_URL  # Should be nats://nats-server.nats.svc.cluster.local:4222
```

### **ConfigMap Configuration**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: petrosa-common-config
  namespace: petrosa-apps
data:
  # ✅ Best NATS configuration (Full DNS name)
  NATS_URL: "nats://nats-server.nats.svc.cluster.local:4222"
  NATS_ENABLED: "true"
  NATS_SUBJECT_PREFIX: "binance"
  NATS_SUBJECT_PREFIX_PRODUCTION: "binance.production"
  NATS_SUBJECT_PREFIX_GAP_FILLER: "binance.gap_filler"
```

## Troubleshooting

### **1. Check NATS Service Exists**
```bash
# Check if NATS service exists in the namespace
kubectl get svc -n petrosa-apps | grep nats

# Check NATS service details
kubectl describe svc nats-server -n petrosa-apps

# Check NATS service endpoints
kubectl get endpoints -n petrosa-apps nats-server
```

### **2. Test DNS Resolution**
```bash
# Test DNS resolution from a pod
kubectl run test-nats --rm -it --image=busybox -- nslookup nats-server

# Test connectivity from a pod
kubectl run test-nats --rm -it --image=busybox -- nc -zv nats-server 4222
```

### **3. Check Network Policies**
```bash
# Check network policies that might block NATS
kubectl get networkpolicy -n petrosa-apps

# Check if NATS traffic is allowed
kubectl describe networkpolicy -n petrosa-apps
```

### **4. Verify Configuration**
```bash
# Check current NATS URL in configmap
kubectl get configmap petrosa-common-config -n petrosa-apps -o yaml

# Check environment variables in running pods
kubectl exec -it <pod-name> -- env | grep NATS
```

### **5. Check NATS Pods**
```bash
# Check if NATS pods are running
kubectl get pods -n petrosa-apps | grep nats

# Check NATS pod logs
kubectl logs -n petrosa-apps <nats-pod-name>

# Check NATS pod status
kubectl describe pod -n petrosa-apps <nats-pod-name>
```

## Common Issues and Solutions

### **Issue 1: NATS Service Not Found**
```bash
# Error: nslookup: can't resolve 'nats-server'
# Solution: Check if NATS service exists
kubectl get svc -n petrosa-apps nats-server
```

### **Issue 2: Connection Refused**
```bash
# Error: Connection refused to nats-server:4222
# Solution: Check NATS pods and service endpoints
kubectl get endpoints -n petrosa-apps nats-server
kubectl get pods -n petrosa-apps | grep nats
```

### **Issue 3: Network Policy Blocking**
```bash
# Error: Connection timeout to nats-server:4222
# Solution: Check network policies
kubectl get networkpolicy -n petrosa-apps
```

### **Issue 4: Wrong Namespace**
```bash
# Error: Service 'nats-server' not found
# Solution: Use full DNS name for cross-namespace
# nats://nats-server.nats-namespace.svc.cluster.local:4222
```

## Migration Guide

### **From External IP to Kubernetes Service**

1. **Update ConfigMap**
```yaml
# Before
NATS_URL: "nats://192.168.194.253:4222"

# After
NATS_URL: "nats://nats-server:4222"
```

2. **Apply Configuration**
```bash
kubectl apply -f k8s/common-configmap.yaml
```

3. **Restart Deployments**
```bash
kubectl rollout restart deployment petrosa-binance-data-extractor -n petrosa-apps
```

4. **Verify Connection**
```bash
kubectl logs -f deployment/petrosa-binance-data-extractor -n petrosa-apps
```

## Best Practices Checklist

- [ ] Use `nats://nats-server:4222` instead of external IP addresses
- [ ] Store NATS configuration in ConfigMaps, not hardcoded in deployments
- [ ] Use the same service name across all applications
- [ ] Test connectivity before deploying to production
- [ ] Monitor NATS connection health in application logs
- [ ] Use network policies to secure NATS traffic
- [ ] Document NATS service dependencies

## Monitoring and Alerting

### **Connection Health Checks**
```python
# Example health check for NATS connection
import nats
import asyncio

async def check_nats_health():
    try:
        nc = await nats.connect("nats://nats-server:4222")
        await nc.close()
        return True
    except Exception as e:
        logger.error(f"NATS health check failed: {e}")
        return False
```

### **Log Monitoring**
Look for these log patterns:
- `"Connected to NATS server"` - Successful connection
- `"Failed to connect to NATS"` - Connection failure
- `"NATS connection lost"` - Connection dropped

### **Metrics to Monitor**
- NATS connection status
- Message publish success/failure rates
- Connection latency
- Reconnection attempts

## Security Considerations

### **Network Policies**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-nats
  namespace: petrosa-apps
spec:
  podSelector:
    matchLabels:
      app: binance-data-extractor
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: nats
    ports:
    - protocol: TCP
      port: 4222
```

### **Service Account Permissions**
Ensure service accounts have minimal required permissions for NATS access.

## References

- [Kubernetes Service Documentation](https://kubernetes.io/docs/concepts/services-networking/service/)
- [NATS Documentation](https://docs.nats.io/)
- [Kubernetes DNS Documentation](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
