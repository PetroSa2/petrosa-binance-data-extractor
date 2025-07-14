# Cursor Rules Reference

When working with this repository, ALWAYS follow these rules:

## Kubernetes Commands
- Always use: `kubectl --kubeconfig=k8s/kubeconfig.yaml [command]`
- For port forwarding: `kubectl --kubeconfig=k8s/kubeconfig.yaml port-forward [service] [port]`
- For certificate issues: Add `--insecure-skip-tls-verify` flag

## Kubernetes Resources
- **ONLY use existing secret**: `petrosa-sensitive-credentials`
- **ONLY use existing configmap**: `petrosa-common-config`
- **NEVER create new secrets or configmaps**

## GitHub CLI
- **ALWAYS use file-based approach**: `gh command > /tmp/file.json && cat /tmp/file.json`
- Example: `gh run list --json status,conclusion,url,createdAt > /tmp/runs.json && cat /tmp/runs.json`

## CI/CD Pipeline
- **Continue until GitHub Actions pipeline passes**
- Run tests locally first: `python -m pytest tests/ -v --cov=. --cov-report=term --tb=short`
- Fix linting: `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`

## Python Code
- Follow PEP 8 formatting
- Use type hints
- Add proper error handling with try/catch
- Add logging for debugging

## Common Mistakes to Avoid
- Don't suggest AWS EKS commands (this is MicroK8s)
- Don't create new Kubernetes secrets/configmaps
- Don't run GitHub CLI commands directly without file output

## Key Files to Check
- `docs/REPOSITORY_SETUP_GUIDE.md`
- `docs/QUICK_REFERENCE.md`
- `k8s/kubeconfig.yaml` 