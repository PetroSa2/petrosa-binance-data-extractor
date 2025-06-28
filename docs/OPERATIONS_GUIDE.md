# Production Operations Guide

This guide covers monitoring, maintenance, and troubleshooting of the Binance Data Extractor in production.

## 🔍 Monitoring Your Deployment

### Quick Status Check
```bash
# View all CronJobs
kubectl get cronjobs -l app=binance-extractor -n petrosa-apps -n petrosa-apps

# View recent jobs
kubectl get jobs -l app=binance-extractor -n petrosa-apps -n petrosa-apps --sort-by=.metadata.creationTimestamp | tail -10

# View current running jobs
kubectl get jobs -l app=binance-extractor -n petrosa-apps -n petrosa-apps --field-selector status.active=1

# Check pod status
kubectl get pods -l component=klines-extractor -n petrosa-apps --sort-by=.metadata.creationTimestamp | tail -5
```

### Detailed Monitoring
```bash
# View logs from the most recent job
kubectl logs -l component=klines-extractor -n petrosa-apps --tail=100

# View logs from a specific job
kubectl logs job/binance-klines-m5-production-<timestamp> -n petrosa-apps

# Follow logs in real-time
kubectl logs -l component=klines-extractor -n petrosa-apps -f

# View events (useful for troubleshooting)
kubectl get events -n petrosa-apps --sort-by=.metadata.creationTimestamp | grep binance
```

## 📊 CronJob Schedules

| Timeframe | Schedule | Description | Max Workers | Resources |
|-----------|----------|-------------|-------------|-----------|
| m5 | `*/5 * * * *` | Every 5 minutes | 15 | 512Mi/1Gi RAM, 300m/800m CPU |
| m15 | `2 */15 * * *` | Every 15 minutes at minute 2 | 12 | 384Mi/768Mi RAM, 250m/600m CPU |
| m30 | `5 */30 * * *` | Every 30 minutes at minute 5 | 10 | 320Mi/640Mi RAM, 200m/500m CPU |
| h1 | `10 * * * *` | Every hour at minute 10 | 8 | 256Mi/512Mi RAM, 200m/500m CPU |
| d1 | `15 0 * * *` | Daily at 00:15 UTC | 6 | 256Mi/512Mi RAM, 200m/500m CPU |

> **Note**: Schedules are staggered to avoid resource conflicts and API rate limiting.

## 🚀 Manual Operations

### Run a Manual Job
```bash
# Create a one-time job from the template
kubectl create job manual-extraction-$(date +%s) -n petrosa-apps --from=job/binance-klines-manual

# Run specific timeframe manually
kubectl create job manual-m15-$(date +%s) -n petrosa-apps --from=cronjob/binance-klines-m15-production
```

### Suspend/Resume CronJobs
```bash
# Suspend a specific CronJob (stops future executions)
kubectl patch cronjob binance-klines-m5-production -n petrosa-apps -p '{"spec":{"suspend":true}}'

# Resume a CronJob
kubectl patch cronjob binance-klines-m5-production -n petrosa-apps -p '{"spec":{"suspend":false}}'

# Suspend all CronJobs
kubectl patch cronjobs -l app=binance-extractor -n petrosa-apps -n petrosa-apps -p '{"spec":{"suspend":true}}'

# Resume all CronJobs
kubectl patch cronjobs -l app=binance-extractor -n petrosa-apps -n petrosa-apps -p '{"spec":{"suspend":false}}'
```

### Clean Up Old Jobs
```bash
# Delete completed jobs older than 1 hour
kubectl delete jobs -l app=binance-extractor -n petrosa-apps --field-selector status.conditions[0].type=Complete,status.conditions[0].status=True

# Delete failed jobs
kubectl delete jobs -l app=binance-extractor -n petrosa-apps --field-selector status.conditions[0].type=Failed

# Clean up all jobs (use with caution)
kubectl delete jobs -l app=binance-extractor -n petrosa-apps
```

## 🔧 Maintenance Tasks

### Update Symbols List
1. Edit `config/symbols.py` in your repository
2. Commit and push to trigger CI/CD
3. The new symbols will be used in the next scheduled run

### Update Docker Image
The CI/CD pipeline automatically builds and deploys new images on every push to main:

```bash
# Check current image
kubectl get cronjobs -l app=binance-extractor -n petrosa-apps -o jsonpath='{.items[0].spec.jobTemplate.spec.template.spec.containers[0].image}'

# Force update all CronJobs to latest image
kubectl patch cronjobs -l app=binance-extractor -n petrosa-apps -p '{"spec":{"jobTemplate":{"spec":{"template":{"spec":{"containers":[{"name":"klines-extractor","imagePullPolicy":"Always"}]}}}}}}'
```

### Scale Resources
```bash
# Update memory/CPU limits for a specific CronJob
kubectl patch cronjob binance-klines-m5-production -n petrosa-apps -p '{
  "spec": {
    "jobTemplate": {
      "spec": {
        "template": {
          "spec": {
            "containers": [{
              "name": "klines-extractor",
              "resources": {
                "limits": {"memory": "2Gi", "cpu": "1000m"},
                "requests": {"memory": "1Gi", "cpu": "500m"}
              }
            }]
          }
        }
      }
    }
  }
}'
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Jobs Failing with API Errors
```bash
# Check for API rate limiting in logs
kubectl logs -l component=klines-extractor -n petrosa-apps --tail=200 | grep -i "rate\|429\|limit"

# Solution: Reduce max-workers or increase delays
kubectl patch cronjob binance-klines-m5-production -n petrosa-apps -p '{
  "spec": {
    "jobTemplate": {
      "spec": {
        "template": {
          "spec": {
            "containers": [{
              "name": "klines-extractor",
              "args": ["--period=5m", "--max-workers=5", "--db-adapter=mysql"]
            }]
          }
        }
      }
    }
  }
}'
```

#### 2. Database Connection Issues
```bash
# Check database secret
kubectl get secret database-secret -o yaml

# Test database connectivity
kubectl run mysql-test --rm -it --image=mysql:8.0 -- mysql -h YOUR_HOST -u YOUR_USER -p

# Check recent database errors
kubectl logs -l component=klines-extractor --tail=200 | grep -i "mysql\|database\|connection"
```

#### 3. Out of Memory Errors
```bash
# Check pod resource usage
kubectl top pods -l component=klines-extractor -n petrosa-apps

# Increase memory limits
kubectl patch cronjob binance-klines-m5-production -n petrosa-apps -p '{
  "spec": {
    "jobTemplate": {
      "spec": {
        "template": {
          "spec": {
            "containers": [{
              "name": "klines-extractor",
              "resources": {
                "limits": {"memory": "2Gi"},
                "requests": {"memory": "1Gi"}
              }
            }]
          }
        }
      }
    }
  }
}'
```

#### 4. Jobs Taking Too Long
```bash
# Check active deadline seconds
kubectl get cronjobs -l app=binance-extractor -n petrosa-apps -o jsonpath='{range .items[*]}{.metadata.name}: {.spec.activeDeadlineSeconds}s{"\n"}{end}'

# Increase timeout for specific job
kubectl patch cronjob binance-klines-h1-production -n petrosa-apps -p '{"spec":{"activeDeadlineSeconds":1800}}'
```

### Health Checks

#### Data Freshness Check
```sql
-- Check if data is being updated (run against your MySQL)
SELECT 
    symbol,
    period,
    MAX(close_time) as last_update,
    COUNT(*) as total_records
FROM klines_m15 
GROUP BY symbol, period 
ORDER BY last_update DESC;
```

#### Job Success Rate
```bash
# Check job success rate over last 24 hours
kubectl get jobs -l app=binance-extractor -n petrosa-apps \
  --field-selector status.conditions[0].type=Complete \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.conditions[0].type}{"\t"}{.metadata.creationTimestamp}{"\n"}{end}' | \
  awk '{print $1, $2}' | sort | uniq -c
```

### Performance Monitoring

#### Resource Usage
```bash
# Monitor CPU/Memory usage
kubectl top pods -l component=klines-extractor -n petrosa-apps

# View resource limits
kubectl describe cronjobs -l app=binance-extractor -n petrosa-apps | grep -A 10 "Limits\|Requests"
```

#### API Rate Limiting
```bash
# Monitor API calls in logs
kubectl logs -l component=klines-extractor -n petrosa-apps --tail=500 | grep -E "(symbols processed|rate limit|429)" | tail -20
```

## 📈 Scaling for High Volume

### Horizontal Scaling (More Concurrent Jobs)
```bash
# Allow multiple jobs to run concurrently (use with caution)
kubectl patch cronjob binance-klines-m5-production -n petrosa-apps -p '{"spec":{"concurrencyPolicy":"Allow"}}'
```

### Vertical Scaling (More Resources)
```bash
# Scale up resources for high-frequency timeframes
kubectl patch cronjob binance-klines-m5-production -n petrosa-apps -p '{
  "spec": {
    "jobTemplate": {
      "spec": {
        "template": {
          "spec": {
            "containers": [{
              "name": "klines-extractor",
              "resources": {
                "limits": {"memory": "4Gi", "cpu": "2000m"},
                "requests": {"memory": "2Gi", "cpu": "1000m"}
              },
              "args": ["--period=5m", "--max-workers=20", "--db-adapter=mysql"]
            }]
          }
        }
      }
    }
  }
}'
```

### Symbol-Based Partitioning
If you have many symbols, consider creating separate CronJobs for different symbol groups:

```yaml
# Example: Separate CronJob for major pairs only
args:
- --period=5m
- --max-workers=10
- --db-adapter=mysql
- --symbols=BTCUSDT,ETHUSDT,BNBUSDT
```

## 🔔 Alerting Setup

### Basic Alerting (using kubectl)
```bash
# Create a simple monitoring script
cat > monitor-binance-extractor.sh << 'EOF'
#!/bin/bash
FAILED_JOBS=$(kubectl get jobs -l app=binance-extractor -n petrosa-apps --field-selector status.conditions[0].type=Failed -o name | wc -l)
if [ "$FAILED_JOBS" -gt 0 ]; then
  echo "⚠️ $FAILED_JOBS failed Binance extraction jobs detected!"
  kubectl get jobs -l app=binance-extractor -n petrosa-apps --field-selector status.conditions[0].type=Failed
fi
EOF

chmod +x monitor-binance-extractor.sh

# Run this script periodically via cron
echo "*/15 * * * * /path/to/monitor-binance-extractor.sh" | crontab -
```

### Advanced Monitoring (Prometheus/Grafana)
For production environments, consider setting up:
- Prometheus metrics collection
- Grafana dashboards for visualization
- AlertManager for notifications

Example metrics to monitor:
- Job success/failure rates
- Data extraction latency
- Database write performance
- API rate limit usage
- Resource consumption

## 📋 Maintenance Checklist

### Daily
- [ ] Check job success rates
- [ ] Verify data freshness
- [ ] Monitor resource usage

### Weekly
- [ ] Clean up old completed jobs
- [ ] Review and rotate logs
- [ ] Check for new symbols to add

### Monthly
- [ ] Review resource allocations
- [ ] Update dependencies if needed
- [ ] Performance optimization review

### Quarterly
- [ ] Full system health review
- [ ] Disaster recovery testing
- [ ] Security updates
