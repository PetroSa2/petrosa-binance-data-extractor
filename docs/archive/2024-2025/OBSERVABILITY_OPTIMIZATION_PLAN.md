# Observability Optimization Plan

## Current State Analysis

### Cluster Resources
- **Single Node**: Ubuntu with 6 CPU cores, 16GB RAM
- **Resource Usage**: 86% CPU allocated, 98% memory allocated
- **Critical Issue**: Cluster is overcommitted and running out of resources

### Current Observability Stack
1. **New Relic** (Namespace: `newrelic`)
   - 10 pods consuming significant resources
   - Hitting free tier limits
   - High resource consumption: ~1.7GB memory, ~1.5 CPU cores

2. **Prometheus/Grafana Stack** (Namespace: `base`)
   - Kube-prometheus-stack with Grafana
   - 6 pods running
   - Resource consumption: ~1GB memory, ~500m CPU

3. **OpenTelemetry Collector** (Namespace: `observability`)
   - Jaeger, Grafana, Prometheus
   - 3 pods running
   - Resource consumption: ~1.5GB memory, ~500m CPU

4. **Additional OTEL Collector** (Namespace: `petrosa-system`)
   - 1 pod running
   - Minimal resource usage

## Recommended Solution: Lightweight Local Stack

### Option 1: Minimal Prometheus + Grafana (Recommended)

**Resource Requirements**: ~512MB RAM, ~200m CPU
**Cost**: $0 (completely free)

#### Components:
1. **Prometheus** (single instance)
   - Scrape interval: 30s (instead of 15s)
   - Retention: 7 days (instead of 30 days)
   - Storage: Local storage only

2. **Grafana** (single instance)
   - Built-in dashboards
   - Local authentication
   - No external dependencies

3. **Node Exporter** (already running)
   - System metrics collection

#### Benefits:
- ✅ Completely free
- ✅ Low resource usage
- ✅ No external dependencies
- ✅ Full control over data
- ✅ No data limits

#### Implementation:
```yaml
# Minimal prometheus-config.yaml
global:
  scrape_interval: 30s
  evaluation_interval: 30s

storage:
  tsdb:
    retention.time: 7d
    retention.size: 1GB

scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

### Option 2: Elastic Stack (Cloud)

**Resource Requirements**: External (no cluster resources)
**Cost**: Elastic Cloud free tier (500MB/day, 7 days retention)

#### Components:
1. **Elasticsearch** (cloud)
2. **Kibana** (cloud)
3. **Filebeat** (minimal resource usage)

#### Benefits:
- ✅ No cluster resource usage
- ✅ Professional logging and metrics
- ✅ Good free tier limits
- ✅ Easy setup

#### Considerations:
- ⚠️ 500MB/day limit (may be sufficient)
- ⚠️ 7-day retention limit
- ⚠️ External dependency

### Option 3: Hybrid Approach (Best of Both)

**Resource Requirements**: ~256MB RAM, ~100m CPU
**Cost**: $0 + optional Elastic Cloud

#### Components:
1. **Minimal Prometheus** (local, basic metrics)
2. **Filebeat** (logs to Elastic Cloud)
3. **Custom metrics endpoint** (application metrics)

## Implementation Plan

### Phase 1: Remove New Relic (Immediate - 30 minutes)

```bash
# Remove New Relic completely
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml delete namespace newrelic

# Update OTEL configuration to point to local collector
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml patch configmap petrosa-common-config -n petrosa-apps \
  --type='merge' \
  -p='{"data":{"OTEL_EXPORTER_OTLP_ENDPOINT":"http://otel-collector.observability.svc.cluster.local:4317"}}'
```

**Resource Savings**: ~1.7GB RAM, ~1.5 CPU cores

### Phase 2: Optimize Existing Stack (1 hour)

```bash
# Scale down existing prometheus
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml scale deployment kube-prometheus-stack-1747-prometheus -n base --replicas=1

# Optimize prometheus configuration
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml patch prometheus kube-prometheus-stack-1747-prometheus -n base \
  --type='merge' \
  -p='{"spec":{"retention":"7d","storage":{"volumeClaimTemplate":{"spec":{"resources":{"requests":{"storage":"1Gi"}}}}}}}'
```

**Resource Savings**: ~500MB RAM, ~200m CPU

### Phase 3: Implement Lightweight Solution (2 hours)

#### 3.1 Create Minimal Prometheus Configuration

```yaml
# k8s/monitoring/minimal-prometheus.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: minimal-prometheus-config
  namespace: observability
data:
  prometheus.yml: |
    global:
      scrape_interval: 30s
      evaluation_interval: 30s

    storage:
      tsdb:
        retention.time: 7d
        retention.size: 1GB

    scrape_configs:
      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
            action: replace
            target_label: __metrics_path__
            regex: (.+)
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: $1:$2
            target_label: __address__
          - source_labels: [__meta_kubernetes_namespace]
            action: replace
            target_label: kubernetes_namespace
          - source_labels: [__meta_kubernetes_pod_name]
            action: replace
            target_label: kubernetes_pod_name
          - source_labels: [__meta_kubernetes_pod_label_app]
            action: replace
            target_label: app
```

#### 3.2 Create Minimal Prometheus Deployment

```yaml
# k8s/monitoring/minimal-prometheus-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minimal-prometheus
  namespace: observability
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minimal-prometheus
  template:
    metadata:
      labels:
        app: minimal-prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:v2.45.0
        args:
          - '--config.file=/etc/prometheus/prometheus.yml'
          - '--storage.tsdb.path=/prometheus'
          - '--storage.tsdb.retention.time=7d'
          - '--storage.tsdb.retention.size=1GB'
          - '--web.console.libraries=/etc/prometheus/console_libraries'
          - '--web.console.templates=/etc/prometheus/consoles'
          - '--web.enable-lifecycle'
        ports:
        - containerPort: 9090
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "200m"
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        - name: storage
          mountPath: /prometheus
      volumes:
      - name: config
        configMap:
          name: minimal-prometheus-config
      - name: storage
        emptyDir: {}
```

### Phase 4: Application Metrics Integration (1 hour)

#### 4.1 Update Application Configurations

```yaml
# Update petrosa-common-config.yaml
data:
  # Remove New Relic specific configs
  OTEL_EXPORTER_OTLP_ENDPOINT: "http://otel-collector.observability.svc.cluster.local:4317"
  OTEL_EXPORTER_OTLP_HEADERS: ""  # Remove New Relic headers
  ENABLE_OTEL: "true"

  # Add Prometheus metrics endpoint
  PROMETHEUS_ENABLED: "true"
  PROMETHEUS_PORT: "9090"
```

#### 4.2 Create Service Monitors

```yaml
# k8s/monitoring/service-monitors.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: petrosa-services
  namespace: observability
spec:
  selector:
    matchLabels:
      app: petrosa
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

### Phase 5: Monitoring and Alerting (30 minutes)

#### 5.1 Basic Alerts

```yaml
# k8s/monitoring/basic-alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: petrosa-basic-alerts
  namespace: observability
spec:
  groups:
  - name: petrosa.rules
    rules:
    - alert: PodDown
      expr: up == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "Pod {{ $labels.pod }} is down"

    - alert: HighMemoryUsage
      expr: (container_memory_usage_bytes / container_spec_memory_limit_bytes) > 0.8
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High memory usage on {{ $labels.pod }}"

    - alert: HighCPUUsage
      expr: (rate(container_cpu_usage_seconds_total[5m]) / container_spec_cpu_quota) > 0.8
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High CPU usage on {{ $labels.pod }}"
```

## Resource Optimization Summary

### Before Optimization:
- **New Relic**: 1.7GB RAM, 1.5 CPU cores
- **Prometheus Stack**: 1GB RAM, 500m CPU
- **Observability Stack**: 1.5GB RAM, 500m CPU
- **Total**: 4.2GB RAM, 2.5 CPU cores

### After Optimization:
- **Minimal Prometheus**: 512MB RAM, 200m CPU
- **Optimized Observability**: 1GB RAM, 300m CPU
- **Total**: 1.5GB RAM, 500m CPU

### Resource Savings:
- **Memory**: 2.7GB saved (64% reduction)
- **CPU**: 2 cores saved (80% reduction)

## Implementation Commands

### Step 1: Remove New Relic
```bash
# Backup current config
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml get configmap petrosa-common-config -n petrosa-apps -o yaml > backup-config.yaml

# Remove New Relic
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml delete namespace newrelic

# Update OTEL endpoint
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml patch configmap petrosa-common-config -n petrosa-apps \
  --type='merge' \
  -p='{"data":{"OTEL_EXPORTER_OTLP_ENDPOINT":"http://otel-collector.observability.svc.cluster.local:4317","OTEL_EXPORTER_OTLP_HEADERS":""}}'
```

### Step 2: Deploy Minimal Monitoring
```bash
# Apply minimal monitoring stack
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml apply -f k8s/monitoring/

# Verify deployment
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml get pods -n observability
```

### Step 3: Update Applications
```bash
# Restart applications to pick up new config
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml rollout restart deployment petrosa-tradeengine -n petrosa-apps
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml rollout restart deployment petrosa-socket-client -n petrosa-apps
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml rollout restart deployment petrosa-ta-bot -n petrosa-apps
```

## Monitoring Dashboard Setup

### Grafana Dashboards
1. **Cluster Overview**: Node metrics, pod status
2. **Application Metrics**: Custom business metrics
3. **Resource Usage**: CPU, memory, disk usage
4. **Error Rates**: Application error tracking

### Key Metrics to Monitor
- Pod restart counts
- Memory usage per pod
- CPU usage per pod
- Application-specific metrics (trading volume, API calls)
- Error rates and response times

## Cost Analysis

### Current Costs:
- **New Relic**: Free tier exceeded (potential charges)
- **Cluster Resources**: High utilization

### Optimized Costs:
- **Monitoring**: $0 (completely free)
- **Storage**: $0 (local storage)
- **Bandwidth**: $0 (no external data transfer)

### Optional Elastic Cloud:
- **Free Tier**: 500MB/day, 7 days retention
- **Cost**: $0 (within free tier limits)

## Next Steps

1. **Immediate**: Remove New Relic to free up resources
2. **Week 1**: Deploy minimal monitoring stack
3. **Week 2**: Set up dashboards and alerts
4. **Week 3**: Evaluate if Elastic Cloud is needed for logs
5. **Ongoing**: Monitor resource usage and optimize further

## Rollback Plan

If issues arise:
```bash
# Restore New Relic (if needed)
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml apply -f backup-config.yaml

# Scale up existing prometheus
kubectl --kubeconfig=petrosa_k8s/k8s/kubeconfig.yaml scale deployment kube-prometheus-stack-1747-prometheus -n base --replicas=3
```

This plan provides a cost-effective, resource-efficient observability solution while maintaining comprehensive monitoring capabilities.
