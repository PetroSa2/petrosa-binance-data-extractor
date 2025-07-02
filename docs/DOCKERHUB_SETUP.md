# Docker Hub Setup Guide

## 🐳 Docker Hub Integration

This guide explains how to set up Docker Hub integration for automated container builds and deployments.

## 📋 Prerequisites

### Docker Hub Account
- Create a Docker Hub account at [hub.docker.com](https://hub.docker.com)
- Verify your email address
- Enable two-factor authentication (recommended)

### Repository Setup
- Create a new repository: `petrosa-binance-extractor`
- Set repository visibility (public or private)
- Enable automated builds (optional)

## 🔧 CI/CD Configuration

### GitHub Secrets Setup

Add the following secrets to your GitHub repository:

```bash
# Required for Docker Hub authentication
DOCKERHUB_USERNAME=your_dockerhub_username
DOCKERHUB_TOKEN=your_dockerhub_access_token

# Optional: Repository-specific settings
DOCKERHUB_REPOSITORY=petrosa-binance-extractor
```

### Docker Hub Access Token

1. **Generate Access Token**:
   - Go to Docker Hub → Account Settings → Security
   - Click "New Access Token"
   - Name: `github-actions`
   - Permissions: Read & Write
   - Copy the token immediately

2. **Add to GitHub Secrets**:
   - Go to your GitHub repository → Settings → Secrets and variables → Actions
   - Add `DOCKERHUB_TOKEN` with the generated token

## 🏗️ Multi-Architecture Builds

### Supported Architectures
- `linux/amd64` (Intel/AMD 64-bit)
- `linux/arm64` (ARM 64-bit, Apple Silicon)

### Build Configuration

The CI/CD pipeline automatically builds for multiple architectures:

```yaml
platforms: linux/amd64,linux/arm64
```

### Build Arguments

```dockerfile
ARG VERSION
ARG COMMIT_SHA
ARG BUILD_DATE
```

## 📦 Image Tagging Strategy

### Version Tags
- **Latest**: `latest` (always points to most recent build)
- **Versioned**: `v1`, `v2`, etc. (semantic versioning)
- **Commit**: `sha-{commit_hash}` (for debugging)

### Tagging Rules
- **Main branch**: `latest` + version tag
- **Tags**: Version tag only
- **Feature branches**: No automatic tagging

## 🔄 Automated Builds

### GitHub Actions Workflow

The CI/CD pipeline automatically:

1. **Builds** multi-architecture images
2. **Pushes** to Docker Hub
3. **Tags** with appropriate version
4. **Updates** Kubernetes manifests

### Build Triggers
- **Push to main**: Builds and pushes `latest`
- **Git tags**: Builds and pushes versioned tags
- **Pull requests**: Builds for testing (no push)

## 🚀 Deployment Integration

### Kubernetes Manifests

Update image references in Kubernetes manifests:

```yaml
image: your-username/petrosa-binance-extractor:latest
```

### Environment-Specific Images

```yaml
# Development
image: your-username/petrosa-binance-extractor:dev

# Staging
image: your-username/petrosa-binance-extractor:staging

# Production
image: your-username/petrosa-binance-extractor:v1.0.0
```

## 🔍 Monitoring and Maintenance

### Image Security
- **Vulnerability Scanning**: Enable Docker Hub security scanning
- **Base Image Updates**: Regular updates to base images
- **Dependency Updates**: Monitor for security patches

### Storage Management
- **Image Cleanup**: Remove old images periodically
- **Storage Limits**: Monitor Docker Hub storage usage
- **Cost Optimization**: Use appropriate repository plans

## 🛠️ Troubleshooting

### Common Issues

1. **Authentication Failed**
   ```bash
   # Verify token is correct
   docker login -u your-username -p your-token
   ```

2. **Build Failures**
   ```bash
   # Check build logs
   docker build --platform linux/amd64 -t test-image .
   ```

3. **Push Failures**
   ```bash
   # Verify repository permissions
   docker push your-username/petrosa-binance-extractor:test
   ```

### Debug Commands

```bash
# Test Docker Hub connection
docker login

# List local images
docker images | grep petrosa-binance-extractor

# Test multi-arch build
docker buildx build --platform linux/amd64,linux/arm64 -t test .
```

## 📚 Related Documentation

- [CI/CD Pipeline Results](CI_CD_PIPELINE_RESULTS.md) - Build and deployment results
- [Local Deployment](LOCAL_DEPLOY.md) - Local development setup
- [Deployment Guide](DEPLOYMENT_GUIDE.md) - Production deployment
- [Dockerfile](../Dockerfile) - Container build configuration
