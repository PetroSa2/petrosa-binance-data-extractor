# Cursor Prompt Template

Copy this template when asking Cursor for help:

```
Please help me with [YOUR REQUEST].

IMPORTANT: Follow these rules from .cursorrules:
- Use kubectl with --kubeconfig=k8s/kubeconfig.yaml
- Only use existing secret 'petrosa-sensitive-credentials' and configmap 'petrosa-common-config'
- For GitHub CLI, use: gh command > /tmp/file.json && cat /tmp/file.json
- Follow PEP 8 for Python code
- Add proper error handling and logging
- Check docs/REPOSITORY_SETUP_GUIDE.md and docs/QUICK_REFERENCE.md first

[YOUR SPECIFIC REQUEST HERE]
```

## Example Usage:

```
Please help me deploy the application to the cluster.

IMPORTANT: Follow these rules from .cursorrules:
- Use kubectl with --kubeconfig=k8s/kubeconfig.yaml
- Only use existing secret 'petrosa-sensitive-credentials' and configmap 'petrosa-common-config'
- For GitHub CLI, use: gh command > /tmp/file.json && cat /tmp/file.json
- Follow PEP 8 for Python code
- Add proper error handling and logging
- Check docs/REPOSITORY_SETUP_GUIDE.md and docs/QUICK_REFERENCE.md first

I need to deploy the latest version of the data extractor service.
```
