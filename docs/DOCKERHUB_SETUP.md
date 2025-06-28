# Docker Hub Integration Setup

This guide explains how to set up Docker Hub integration for the Binance Data Extractor CI/CD pipeline.

## 🐳 Docker Hub Setup

### Step 1: Create Docker Hub Access Token

1. **Login to Docker Hub**: Go to [hub.docker.com](https://hub.docker.com) and sign in
2. **Navigate to Security Settings**: Go to [Account Settings → Security](https://hub.docker.com/settings/security)
3. **Create New Access Token**:
   - Click "New Access Token"
   - Name: `GitHub Actions Binance Extractor`
   - Permissions: `Read, Write, Delete` (recommended) or `Read, Write` (minimum)
   - Click "Generate"
4. **Copy the Token**: Copy the generated token (starts with `dckr_pat_...`)

### Step 2: Configure GitHub Secrets

In your GitHub repository, go to **Settings → Secrets and Variables → Actions** and add:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `DOCKERHUB_USERNAME` | `your-docker-username` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | `dckr_pat_...` | The access token from Step 1 |
| `KUBE_CONFIG_DATA` | `base64 < ~/.kube/config` | Base64 encoded kubeconfig |

### Step 3: Verify Repository Settings

Ensure your Docker Hub repository will be created:
- **Repository Name**: `petrosa-binance-extractor`
- **Visibility**: Public (recommended) or Private
- **Auto-build**: Disabled (we use GitHub Actions)

## 🚀 How It Works

### CI/CD Pipeline Flow

1. **Trigger**: Push to `main` branch or manual workflow dispatch
2. **Build**: Docker image is built using the Dockerfile
3. **Tag**: Image is tagged with:
   - `latest` (for main branch)
   - `main-<commit-sha>` (for main branch)
   - `<commit-sha>` (always)
4. **Push**: Image is pushed to `your-username/petrosa-binance-extractor`
5. **Deploy**: Kubernetes manifests are updated and applied

### Image Naming Convention

```
your-username/petrosa-binance-extractor:latest
your-username/petrosa-binance-extractor:main-a1b2c3d
your-username/petrosa-binance-extractor:a1b2c3d
```

### Kubernetes Integration

The CI/CD pipeline automatically updates these manifests:
- `k8s/klines-all-timeframes-cronjobs.yaml`
- `k8s/klines-production-cronjobs.yaml`
- `k8s/job.yaml`

Image references are updated from:
```yaml
image: DOCKERHUB_USERNAME/petrosa-binance-extractor:latest
```

To:
```yaml
image: your-username/petrosa-binance-extractor:a1b2c3d
```

## 🔍 Troubleshooting

### Common Issues

#### 1. "Invalid credentials" Error
```bash
Error: buildx failed with: ERROR: failed to solve: failed to push
```
**Solution**: 
- Verify `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` are correctly set
- Ensure the access token has `Write` permissions
- Check that your Docker Hub account is active

#### 2. "Repository does not exist" Error
```bash
Error: repository does not exist or may require authorization
```
**Solution**:
- Create the repository manually on Docker Hub: `your-username/petrosa-binance-extractor`
- Ensure the repository name matches exactly
- Verify your username is correct

#### 3. "Rate limit exceeded" Error
```bash
Error: toomanyrequests: You have reached your pull rate limit
```
**Solution**:
- Upgrade to Docker Hub Pro (recommended for CI/CD)
- Use Docker Hub authentication in all pulls
- Implement image caching

### Verification Commands

```bash
# Check if image was pushed successfully
docker pull your-username/petrosa-binance-extractor:latest

# Verify image in Kubernetes
kubectl describe cronjob binance-klines-m5-production -n petrosa-apps | grep Image

# Check GitHub Actions logs
# Go to Actions tab → Latest workflow → Build and push Docker image
```

## 🔧 Local Development

### Building Locally

```bash
# Build the image locally
docker build -t your-username/petrosa-binance-extractor:dev .

# Test the image
docker run --rm -e ENVIRONMENT=development your-username/petrosa-binance-extractor:dev python -m jobs.extract_klines_production --help

# Push manually (if needed)
docker push your-username/petrosa-binance-extractor:dev
```

### Testing with Local Registry

```bash
# Run local registry
docker run -d -p 5000:5000 --name registry registry:2

# Build and push to local registry
docker build -t localhost:5000/petrosa-binance-extractor:test .
docker push localhost:5000/petrosa-binance-extractor:test

# Update manifests for testing
sed -i 's|your-username/petrosa-binance-extractor:latest|localhost:5000/petrosa-binance-extractor:test|g' k8s/job.yaml
kubectl apply -f k8s/job.yaml
```

## 📈 Best Practices

### Security
- ✅ Use access tokens instead of passwords
- ✅ Set minimal required permissions on tokens
- ✅ Rotate tokens regularly (every 6-12 months)
- ✅ Use GitHub secrets for sensitive data

### Performance
- ✅ Use multi-stage Docker builds (already implemented)
- ✅ Optimize image layers for caching
- ✅ Consider using Docker Hub Pro for faster builds
- ✅ Implement image scanning for vulnerabilities

### Operations
- ✅ Tag images with commit SHA for traceability
- ✅ Keep `latest` tag updated for easy rollbacks
- ✅ Monitor image pull metrics
- ✅ Set up automated vulnerability scanning

## 🎯 Migration from GHCR

If you were previously using GitHub Container Registry (GHCR):

1. **Update GitHub secrets**: Replace `GITHUB_TOKEN` workflow with Docker Hub credentials
2. **Update image references**: All manifests now use Docker Hub format
3. **Pull existing images**: `docker pull ghcr.io/old-repo:latest && docker tag ghcr.io/old-repo:latest your-username/petrosa-binance-extractor:latest && docker push your-username/petrosa-binance-extractor:latest`

Your Docker Hub integration is now ready for production-scale container distribution! 🚀
