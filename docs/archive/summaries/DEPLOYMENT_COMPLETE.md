# Deployment Complete Guide

## ✅ Post-Deployment Verification

This guide covers the verification steps and next actions after successfully deploying the Petrosa Binance Data Extractor.

## 🔍 Verification Checklist

### 1. **Kubernetes Resources**

```bash
# Verify all resources are running
kubectl get all -n petrosa-apps

# Expected output:
# - CronJobs: 6 (5 timeframes + 1 gap filler)
# - No failed pods
# - All services healthy
```

### 2. **CronJob Status**

```bash
# Check CronJob status
kubectl get cronjobs -n petrosa-apps

# Verify gap filler CronJob
kubectl get cronjob klines-gap-filler -n petrosa-apps
```

### 3. **Secrets Verification**

```bash
# Verify secrets exist
kubectl get secrets -n petrosa-apps

# Expected secrets:
```

### 4. **Image Pull Status**

```bash
# Check if images pulled successfully
kubectl describe pod -l app=binance-extractor -n petrosa-apps

# Look for:
# - ImagePullBackOff: No
# - Ready: True
# - Status: Running
```

## 🧪 Functional Testing

### 1. **Manual Job Execution**

```bash
# Test a manual job execution
kubectl create job --from=cronjob/binance-klines-m15-production test-job-$(date +%s) -n petrosa-apps

# Monitor the job
kubectl get jobs -n petrosa-apps -w
```

### 2. **Log Verification**

```bash
# Check recent logs
kubectl logs -l app=binance-extractor --tail=100 -n petrosa-apps

# Look for:
# - Successful API connections
# - Data extraction messages
# - No critical errors
```

### 3. **Database Verification**

```bash
# Connect to your database and verify:
# - Tables created with correct naming
# - Data being inserted
# - Proper indexing
```

## 📊 Monitoring Setup

### 1. **OpenTelemetry Verification**

```bash
# Check if telemetry is working
kubectl logs -l app=binance-extractor -n petrosa-apps | grep -i "telemetry\|otel"

# Expected: Telemetry initialization messages
```

### 2. **Metrics Collection**

Verify that metrics are being collected:
- **Application Metrics**: Job execution times, success rates
- **System Metrics**: CPU, memory usage
- **Business Metrics**: Data extraction volumes

### 3. **Alerting Setup**

Configure alerts for:
- **Job Failures**: CronJob execution failures
- **Resource Usage**: High CPU/memory usage
- **Data Quality**: Missing data or gaps
- **API Issues**: Binance API rate limiting

## 🚨 Common Issues and Solutions

### 1. **CronJobs Not Running**

```bash
# Check CronJob controller
kubectl get events -n petrosa-apps | grep -i cronjob

# Verify timezone settings
kubectl describe cronjob -n petrosa-apps
```

### 2. **Image Pull Issues**

```bash
# Check image availability
docker pull your-username/petrosa-binance-extractor:latest

# Verify registry credentials
kubectl get secret -n petrosa-apps
```

### 3. **Database Connection Issues**

```bash
# Test database connectivity
kubectl exec -it deployment/binance-extractor -n petrosa-apps -- python -c "
import os
from db.mysql_adapter import MySQLAdapter
adapter = MySQLAdapter(os.environ['POSTGRES_CONNECTION_STRING'])
adapter.connect()
print('Database connection successful')
"
```

## 📈 Performance Monitoring

### 1. **Resource Usage**

```bash
# Monitor resource usage
kubectl top pods -n petrosa-apps

# Check for:
# - CPU usage < 80%
# - Memory usage < 80%
# - No OOM kills
```

### 2. **Job Performance**

Monitor job execution metrics:
- **Execution Time**: Should be within expected ranges
- **Success Rate**: Should be > 95%
- **Data Volume**: Verify expected data amounts

### 3. **API Rate Limiting**

Watch for Binance API rate limiting:
```bash
# Check for rate limit errors
kubectl logs -l app=binance-extractor -n petrosa-apps | grep -i "rate limit\|429"
```

## 🔄 Next Steps

### 1. **Immediate Actions (First 24 Hours)**

- [ ] **Monitor Job Executions**: Watch first few CronJob runs
- [ ] **Verify Data Quality**: Check extracted data in database
- [ ] **Set Up Alerts**: Configure monitoring alerts
- [ ] **Document Issues**: Log any problems encountered

### 2. **Short Term (First Week)**

- [ ] **Performance Tuning**: Optimize resource limits if needed
- [ ] **Data Validation**: Verify data completeness and accuracy
- [ ] **Backup Strategy**: Implement data backup procedures
- [ ] **Team Training**: Train operations team on monitoring

### 3. **Long Term (First Month)**

- [ ] **Capacity Planning**: Monitor growth and plan scaling
- [ ] **Security Review**: Regular security assessments
- [ ] **Documentation Updates**: Keep documentation current
- [ ] **Process Optimization**: Streamline operations

## 📋 Maintenance Schedule

### Daily
- [ ] Check CronJob execution status
- [ ] Review error logs
- [ ] Monitor resource usage

### Weekly
- [ ] Review data quality metrics
- [ ] Check for gaps in data
- [ ] Update monitoring dashboards

### Monthly
- [ ] Security updates and patches
- [ ] Performance review and optimization
- [ ] Documentation updates

## 🎯 Success Criteria

### Technical Success
- ✅ All CronJobs running successfully
- ✅ Data being extracted and stored correctly
- ✅ No critical errors in logs
- ✅ Resource usage within limits

### Business Success
- ✅ Required data available for analysis
- ✅ Data quality meets requirements
- ✅ System reliability > 99%
- ✅ Operational costs within budget

## 📚 Related Documentation

- [Operations Guide](OPERATIONS_GUIDE.md) - Day-to-day operations
- [Production Readiness](PRODUCTION_READINESS.md) - Pre-deployment checklist
- [Local Deployment](LOCAL_DEPLOY.md) - Local development setup
- [CI/CD Pipeline](CI_CD_PIPELINE_RESULTS.md) - Deployment automation
