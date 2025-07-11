# Operations Guide

## 🔧 Day-to-Day Operations

This guide covers the daily operations, monitoring, and troubleshooting for the Petrosa Binance Data Extractor in production.

## 📋 Daily Operations Checklist

### Morning Checks (9 AM)

```bash
# 1. Check overall system status
kubectl --kubeconfig=k8s/kubeconfig.yaml get all -n petrosa-apps

# 2. Verify CronJob status
kubectl --kubeconfig=k8s/kubeconfig.yaml get cronjobs -n petrosa-apps

# 3. Check recent job executions
kubectl --kubeconfig=k8s/kubeconfig.yaml get jobs -n petrosa-apps --sort-by=.metadata.creationTimestamp

# 4. Review error logs from last 24 hours
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -l app=binance-extractor -n petrosa-apps --since=24h | grep -i error
```

### Afternoon Monitoring (2 PM)

```bash
# 1. Check resource usage
kubectl --kubeconfig=k8s/kubeconfig.yaml top pods -n petrosa-apps

# 2. Verify gap filler execution (runs at 2 AM UTC)
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -l job-name=klines-gap-filler -n petrosa-apps --since=12h

# 3. Monitor API rate limiting
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -l app=binance-extractor -n petrosa-apps --since=6h | grep -i "rate limit\|429"
```

### Evening Review (6 PM)

```bash
# 1. Check daily data extraction summary
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -l app=binance-extractor -n petrosa-apps --since=24h | grep -i "extracted\|processed"

# 2. Verify database connectivity
kubectl --kubeconfig=k8s/kubeconfig.yaml exec -it deployment/binance-extractor -n petrosa-apps -- python -c "
import os
from db.mysql_adapter import MySQLAdapter
try:
    adapter = MySQLAdapter(os.environ['MYSQL_URI'])
    adapter.connect()
    print('Database connection: OK')
except Exception as e:
    print(f'Database connection: FAILED - {e}')
"
```

## 🔍 Monitoring Commands

### System Health

```bash
# Overall cluster health
kubectl --kubeconfig=k8s/kubeconfig.yaml get nodes
kubectl --kubeconfig=k8s/kubeconfig.yaml get pods -n petrosa-apps -o wide

# Resource usage
kubectl --kubeconfig=k8s/kubeconfig.yaml top nodes
kubectl --kubeconfig=k8s/kubeconfig.yaml top pods -n petrosa-apps

# Namespace events
kubectl --kubeconfig=k8s/kubeconfig.yaml get events -n petrosa-apps --sort-by=.metadata.creationTimestamp
```

### CronJob Monitoring

```bash
# Check all CronJobs
kubectl --kubeconfig=k8s/kubeconfig.yaml get cronjobs -n petrosa-apps

# Detailed CronJob information
kubectl --kubeconfig=k8s/kubeconfig.yaml describe cronjob binance-klines-m15-production -n petrosa-apps

# Recent job executions
kubectl --kubeconfig=k8s/kubeconfig.yaml get jobs -n petrosa-apps --sort-by=.metadata.creationTimestamp | tail -10

# Job logs
kubectl --kubeconfig=k8s/kubeconfig.yaml logs job/binance-klines-m15-production-1234567890 -n petrosa-apps
```

### Gap Filler Monitoring

```bash
# Check gap filler status
kubectl --kubeconfig=k8s/kubeconfig.yaml get cronjob klines-gap-filler -n petrosa-apps

# Recent gap filler executions
kubectl --kubeconfig=k8s/kubeconfig.yaml get jobs -l job-name=klines-gap-filler -n petrosa-apps --sort-by=.metadata.creationTimestamp

# Gap filler logs
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -l job-name=klines-gap-filler -n petrosa-apps --tail=100

# Gap filler details
kubectl --kubeconfig=k8s/kubeconfig.yaml describe cronjob klines-gap-filler -n petrosa-apps
```

## 🚨 Troubleshooting

### Common Issues

#### 1. CronJob Not Running

```bash
# Check CronJob controller
kubectl --kubeconfig=k8s/kubeconfig.yaml get events -n petrosa-apps | grep -i cronjob

# Verify timezone
kubectl --kubeconfig=k8s/kubeconfig.yaml describe cronjob -n petrosa-apps | grep -i schedule

# Check for resource constraints
kubectl --kubeconfig=k8s/kubeconfig.yaml describe cronjob -n petrosa-apps | grep -A 10 "Events:"
```

**Solutions:**
- Verify cluster timezone settings
- Check resource quotas
- Ensure CronJob controller is running

#### 2. Job Failures

```bash
# Check job status
kubectl --kubeconfig=k8s/kubeconfig.yaml get jobs -n petrosa-apps

# View job details
kubectl --kubeconfig=k8s/kubeconfig.yaml describe job <job-name> -n petrosa-apps

# Check pod logs
kubectl --kubeconfig=k8s/kubeconfig.yaml logs job/<job-name> -n petrosa-apps
```

**Common Causes:**
- API rate limiting
- Database connection issues
- Resource constraints
- Configuration errors

#### 3. Image Pull Issues

```bash
# Check image pull status
kubectl --kubeconfig=k8s/kubeconfig.yaml describe pod -l app=binance-extractor -n petrosa-apps | grep -A 5 "Events:"

# Verify image availability
docker pull your-username/petrosa-binance-extractor:latest
```

**Solutions:**
- Check Docker Hub credentials
- Verify image exists and is accessible
- Check network connectivity

#### 4. Database Connection Issues

```bash
# Test database connectivity
kubectl --kubeconfig=k8s/kubeconfig.yaml exec -it deployment/binance-extractor -n petrosa-apps -- python -c "
import os
from db.mysql_adapter import MySQLAdapter
try:
    adapter = MySQLAdapter(os.environ['MYSQL_URI'])
    adapter.connect()
    print('Database connection successful')
except Exception as e:
    print(f'Database connection failed: {e}')
"
```

**Solutions:**
- Verify database credentials
- Check network connectivity
- Ensure database is running

## 📊 Performance Monitoring

### Resource Usage

```bash
# Monitor CPU and memory usage
kubectl --kubeconfig=k8s/kubeconfig.yaml top pods -n petrosa-apps

# Check for resource pressure
kubectl --kubeconfig=k8s/kubeconfig.yaml describe nodes | grep -A 5 "Conditions:"

# Monitor storage usage
kubectl --kubeconfig=k8s/kubeconfig.yaml exec -it deployment/binance-extractor -n petrosa-apps -- df -h
```

### API Performance

```bash
# Monitor API response times
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -l app=binance-extractor -n petrosa-apps --since=1h | grep -i "api\|request"

# Check rate limiting
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -l app=binance-extractor -n petrosa-apps --since=1h | grep -i "429\|rate limit"
```

## 🚨 Emergency Procedures

### Service Outage

1. **Immediate Actions**:
   ```bash
   # Check system status
   kubectl --kubeconfig=k8s/kubeconfig.yaml get all -n petrosa-apps
   
   # Check recent events
   kubectl --kubeconfig=k8s/kubeconfig.yaml get events -n petrosa-apps --sort-by=.metadata.creationTimestamp
   ```

2. **Escalation**:
   - Contact on-call engineer
   - Check monitoring dashboards
   - Review recent deployments

### Data Loss

1. **Assessment**:
   ```bash
   # Check database connectivity
   kubectl --kubeconfig=k8s/kubeconfig.yaml exec -it deployment/binance-extractor -n petrosa-apps -- python -c "
   import os
   from db.mysql_adapter import MySQLAdapter
   adapter = MySQLAdapter(os.environ['MYSQL_URI'])
   adapter.connect()
   # Add data verification logic
   "
   ```

2. **Recovery**:
   - Restore from backup
   - Re-run gap filler
   - Verify data integrity

### Security Incident

1. **Immediate Response**:
   - Rotate API keys
   - Check for unauthorized access
   - Review audit logs

2. **Investigation**:
   - Analyze logs for suspicious activity
   - Check for data exfiltration
   - Review access patterns

## 📈 Reporting

### Daily Reports

```bash
# Generate daily summary
echo "=== Daily Operations Summary ==="
echo "Date: $(date)"
echo ""
echo "=== System Status ==="
kubectl --kubeconfig=k8s/kubeconfig.yaml get all -n petrosa-apps
echo ""
echo "=== Recent Jobs ==="
kubectl --kubeconfig=k8s/kubeconfig.yaml get jobs -n petrosa-apps --sort-by=.metadata.creationTimestamp | tail -5
echo ""
echo "=== Error Summary ==="
kubectl --kubeconfig=k8s/kubeconfig.yaml logs -l app=binance-extractor -n petrosa-apps --since=24h | grep -i error | wc -l
```

### Weekly Reports

- System uptime and availability
- Data extraction volumes
- Error rates and patterns
- Resource usage trends
- Performance metrics

## 📚 Related Documentation

- [Production Readiness](docs/PRODUCTION_READINESS.md) - Pre-deployment checklist
- [Deployment Complete](docs/DEPLOYMENT_COMPLETE.md) - Post-deployment verification
- [Local Deployment](docs/LOCAL_DEPLOY.md) - Local development setup
