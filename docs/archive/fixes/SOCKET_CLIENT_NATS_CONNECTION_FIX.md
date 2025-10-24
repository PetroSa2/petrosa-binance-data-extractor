# Socket Client NATS Connection Issue - Investigation & Resolution

## Issue Summary
The `petrosa-socket-client` deployment was experiencing severe issues on the Kubernetes cluster with multiple restarts and CrashLoopBackOff status. All three pods were failing to start properly.

## Initial Investigation

### Symptoms Observed
- **Pod Status**: All 3 pods in `CrashLoopBackOff` state
- **Restart Count**: 18 restarts per pod
- **Error Pattern**: Consistent connection failures to NATS

### Root Cause Analysis

#### 1. Error Logs Analysis
The primary error in the logs was:
```
Service failed: nats: no servers available for connection
Failed to connect to NATS: nats: no servers available for connection
```

#### 2. Configuration Issue Identified
The `NATS_URL` in `petrosa-common-config` was incorrectly configured:
- **Incorrect**: `nats://192.168.194.253:4222` (external IP)
- **Correct**: `nats://nats-server.nats:4222` (internal service name)

#### 3. Network Connectivity Verification
- NATS server was running properly in the `nats` namespace
- Network policies were correctly configured to allow egress to NATS
- The issue was purely configuration-related

## Resolution Steps

### 1. Fixed NATS URL Configuration
```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml patch configmap petrosa-common-config -n petrosa-apps \
  --patch '{"data":{"NATS_URL":"nats://nats-server.nats:4222"}}'
```

### 2. Restarted Deployment
```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml rollout restart deployment petrosa-socket-client -n petrosa-apps
```

### 3. Verified Resolution
- All 3 pods now running successfully
- Message processing confirmed (11,600+ messages processed)
- Health checks responding properly
- No connection errors in logs

## Final Status

### Deployment Health
```bash
NAME                    READY   UP-TO-DATE   AVAILABLE   AGE
petrosa-socket-client   3/3     3            3           2d13h
```

### Pod Status
```bash
NAME                                    READY   STATUS    RESTARTS   AGE
petrosa-socket-client-86f475578-gjjv9   1/1     Running   0          101s
petrosa-socket-client-86f475578-l28jf   1/1     Running   0          80s
petrosa-socket-client-86f475578-nd8c2   1/1     Running   0          60s
```

## Key Learnings

### 1. Internal vs External Service Discovery
- **Kubernetes Internal**: Use service names like `nats-server.nats:4222`
- **External Access**: Use external IPs like `192.168.194.253:4222`
- **Configuration**: Always use internal service names for inter-pod communication

### 2. Network Policy Verification
- Network policies were correctly configured
- The issue was not network-related but configuration-related
- Always verify both network policies AND service configuration

### 3. Log Analysis Importance
- Error logs clearly indicated NATS connection issues
- Circuit breaker patterns were working as expected
- Health checks were failing due to service startup failures

## Prevention Measures

### 1. Configuration Validation
- Implement configuration validation in CI/CD pipeline
- Verify service URLs use internal Kubernetes DNS names
- Add automated testing for service connectivity

### 2. Monitoring Improvements
- Add NATS connectivity monitoring
- Implement alerting for connection failures
- Monitor circuit breaker states

### 3. Documentation Updates
- Update deployment guides to emphasize internal service naming
- Document common configuration pitfalls
- Create troubleshooting guides for similar issues

## Related Files
- `k8s/deployment.yaml` - Socket client deployment configuration
- `k8s/common-configmap.yaml` - Common configuration including NATS URL
- Network policies in `petrosa-apps` namespace

## Commands Used for Investigation
```bash
# Check pod status
kubectl --kubeconfig=k8s/kubeconfig.yaml get pods -n petrosa-apps -l app=socket-client

# Check logs
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -n petrosa-apps <pod-name>

# Check deployment configuration
kubectl --kubeconfig=k8s/kubeconfig.yaml get deployment petrosa-socket-client -n petrosa-apps -o yaml

# Check configmaps
kubectl --kubeconfig=k8s/kubeconfig.yaml get configmap petrosa-common-config -n petrosa-apps -o yaml

# Check NATS service
kubectl --kubeconfig=k8s/kubeconfig.yaml get svc -n nats

# Check network policies
kubectl --kubeconfig=k8s/kubeconfig.yaml get networkpolicies -n petrosa-apps
```

## Resolution Date
**2025-08-22** - Issue identified and resolved within 30 minutes of investigation.

## Status
✅ **RESOLVED** - Socket client is now healthy and processing messages correctly.
