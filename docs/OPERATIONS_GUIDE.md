# Operations Guide

## 🔧 Day-to-Day Operations

This guide covers the daily operations, monitoring, and troubleshooting for the Petrosa Binance Data Extractor in production.

## 📋 Daily Operations Checklist

### Morning Checks (9 AM)

```bash
# 1. Check overall system status
kubectl get all -n petrosa-apps

# 2. Verify CronJob status
kubectl get cronjobs -n petrosa-apps

# 3. Check recent job executions
kubectl get jobs -n petrosa-apps --sort-by=.metadata.creationTimestamp

# 4. Review error logs from last 24 hours
kubectl logs -l app=binance-extractor -n petrosa-apps --since=24h | grep -i error
```

### Afternoon Monitoring (2 PM)

```bash
# 1. Check resource usage
kubectl top pods -n petrosa-apps

# 2. Verify gap filler execution (runs at 2 AM UTC)
kubectl logs -l job-name=klines-gap-filler -n petrosa-apps --since=12h

# 3. Monitor API rate limiting
kubectl logs -l app=binance-extractor -n petrosa-apps --since=6h | grep -i "rate limit\|429"
```

### Evening Review (6 PM)

```bash
# 1. Check daily data extraction summary
kubectl logs -l app=binance-extractor -n petrosa-apps --since=24h | grep -i "extracted\|processed"

# 2. Verify database connectivity
kubectl exec -it deployment/binance-extractor -n petrosa-apps -- python -c "
import os
from db.mysql_adapter import MySQLAdapter
try:
    adapter = MySQLAdapter(os.environ['POSTGRES_CONNECTION_STRING'])
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
kubectl get nodes
kubectl get pods -n petrosa-apps -o wide

# Resource usage
kubectl top nodes
kubectl top pods -n petrosa-apps

# Namespace events
kubectl get events -n petrosa-apps --sort-by=.metadata.creationTimestamp
```

### CronJob Monitoring

```bash
# Check all CronJobs
kubectl get cronjobs -n petrosa-apps

# Detailed CronJob information
kubectl describe cronjob binance-klines-m15-production -n petrosa-apps

# Recent job executions
kubectl get jobs -n petrosa-apps --sort-by=.metadata.creationTimestamp | tail -10

# Job logs
kubectl logs job/binance-klines-m15-production-1234567890 -n petrosa-apps
```

### Gap Filler Monitoring

```bash
# Check gap filler status
kubectl get cronjob klines-gap-filler -n petrosa-apps

# Recent gap filler executions
kubectl get jobs -l job-name=klines-gap-filler -n petrosa-apps --sort-by=.metadata.creationTimestamp

# Gap filler logs
kubectl logs -l job-name=klines-gap-filler -n petrosa-apps --tail=100

# Gap filler details
kubectl describe cronjob klines-gap-filler -n petrosa-apps
```

## 🚨 Troubleshooting

### Common Issues

#### 1. CronJob Not Running

```bash
# Check CronJob controller
kubectl get events -n petrosa-apps | grep -i cronjob

# Verify timezone
kubectl describe cronjob -n petrosa-apps | grep -i schedule

# Check for resource constraints
kubectl describe cronjob -n petrosa-apps | grep -A 10 "Events:"
```

**Solutions:**
- Verify cluster timezone settings
- Check resource quotas
- Ensure CronJob controller is running

#### 2. Job Failures

```bash
# Check job status
kubectl get jobs -n petrosa-apps

# View job details
kubectl describe job <job-name> -n petrosa-apps

# Check pod logs
kubectl logs job/<job-name> -n petrosa-apps
```

**Common Causes:**
- API rate limiting
- Database connection issues
- Resource constraints
- Configuration errors

#### 3. Image Pull Issues

```bash
# Check image pull status
kubectl describe pod -l app=binance-extractor -n petrosa-apps | grep -A 5 "Events:"

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
kubectl exec -it deployment/binance-extractor -n petrosa-apps -- python -c "
import os
from db.mysql_adapter import MySQLAdapter
try:
    adapter = MySQLAdapter(os.environ['POSTGRES_CONNECTION_STRING'])
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
kubectl top pods -n petrosa-apps

# Check for resource pressure
kubectl describe nodes | grep -A 5 "Conditions:"

# Monitor storage usage
kubectl exec -it deployment/binance-extractor -n petrosa-apps -- df -h
```

### API Performance

```bash
# Check API response times
kubectl logs -l app=binance-extractor -n petrosa-apps | grep -i "response time\|duration"

# Monitor rate limiting
kubectl logs -l app=binance-extractor -n petrosa-apps | grep -i "rate limit\|429\|retry"
```

### Data Quality

```bash
# Check data extraction volumes
kubectl logs -l app=binance-extractor -n petrosa-apps | grep -i "extracted\|processed\|records"

# Monitor data gaps
kubectl logs -l job-name=klines-gap-filler -n petrosa-apps | grep -i "gap\|missing"
```

## 🔄 Maintenance Tasks

### Weekly Tasks

```bash
# 1. Review resource usage trends
kubectl top pods -n petrosa-apps --sort-by=cpu
kubectl top pods -n petrosa-apps --sort-by=memory

# 2. Check for outdated images
kubectl get pods -n petrosa-apps -o jsonpath='{.items[*].spec.containers[*].image}' | tr ' ' '\n' | sort | uniq

# 3. Review error patterns
kubectl logs -l app=binance-extractor -n petrosa-apps --since=168h | grep -i error | sort | uniq -c | sort -nr
```

### Monthly Tasks

```bash
# 1. Security updates
kubectl get pods -n petrosa-apps -o jsonpath='{.items[*].spec.containers[*].image}' | tr ' ' '\n' | sort | uniq

# 2. Performance review
kubectl top pods -n petrosa-apps --sort-by=cpu | head -10
kubectl top pods -n petrosa-apps --sort-by=memory | head -10

# 3. Capacity planning
kubectl describe nodes | grep -A 10 "Allocated resources"
```

## 🚨 Emergency Procedures

### Service Outage

1. **Immediate Actions**:
   ```bash
   # Check system status
   kubectl get all -n petrosa-apps
   
   # Check recent events
   kubectl get events -n petrosa-apps --sort-by=.metadata.creationTimestamp
   ```

2. **Escalation**:
   - Contact on-call engineer
   - Check monitoring dashboards
   - Review recent deployments

### Data Loss

1. **Assessment**:
   ```bash
   # Check database connectivity
   kubectl exec -it deployment/binance-extractor -n petrosa-apps -- python -c "
   import os
   from db.mysql_adapter import MySQLAdapter
   adapter = MySQLAdapter(os.environ['POSTGRES_CONNECTION_STRING'])
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
kubectl get all -n petrosa-apps
echo ""
echo "=== Recent Jobs ==="
kubectl get jobs -n petrosa-apps --sort-by=.metadata.creationTimestamp | tail -5
echo ""
echo "=== Error Summary ==="
kubectl logs -l app=binance-extractor -n petrosa-apps --since=24h | grep -i error | wc -l
```

### Weekly Reports

- System uptime and availability
- Data extraction volumes
- Error rates and patterns
- Resource usage trends
- Performance metrics

## 📚 Related Documentation

- [Production Readiness](PRODUCTION_READINESS.md) - Pre-deployment checklist
- [Deployment Complete](DEPLOYMENT_COMPLETE.md) - Post-deployment verification
- [Local Deployment](LOCAL_DEPLOY.md) - Local development setup
- [CI/CD Pipeline](CI_CD_PIPELINE_RESULTS.md) - Automated deployment results
