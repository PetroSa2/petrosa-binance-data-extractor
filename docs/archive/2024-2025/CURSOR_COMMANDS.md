# Cursor Commands for Automatic Context

## Quick Context Commands

### 1. Get Documentation Context
```bash
# Run this before asking Cursor for help
./scripts/cursor_helper.sh
```

### 2. Get Current Status
```bash
# Check what's currently deployed
kubectl --kubeconfig=k8s/kubeconfig.yaml get pods -A
```

### 3. Get Pipeline Status
```bash
# Check GitHub Actions pipeline status
gh run list --json status,conclusion,url,createdAt > /tmp/runs.json && cat /tmp/runs.json
```

### 4. Get Test Status
```bash
# Run tests and get status
python -m pytest tests/ -v --cov=. --cov-report=term --tb=short
```

## Automated Context Prompts

### For Deployment Issues:
```bash
./scripts/cursor_helper.sh && echo "Now help me with deployment issues"
```

### For Pipeline Issues:
```bash
gh run list --json status,conclusion,url,createdAt > /tmp/runs.json && cat /tmp/runs.json && echo "Now help me fix pipeline issues"
```

### For Kubernetes Issues:
```bash
kubectl --kubeconfig=k8s/kubeconfig.yaml get pods -A && echo "Now help me with Kubernetes issues"
```

## One-Liner Context
```bash
# Copy this output into your Cursor prompt
echo "Context: $(./scripts/cursor_helper.sh)" && echo "Now help me with [YOUR ISSUE]"
```
