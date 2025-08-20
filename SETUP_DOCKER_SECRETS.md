# Setting Up Docker Hub Secrets for Petrosa Socket Client

## Current Status
- ✅ KUBE_CONFIG_DATA - Already configured
- ❌ DOCKERHUB_USERNAME - Needs to be set
- ❌ DOCKERHUB_TOKEN - Needs to be set

## Method 1: Copy from petrosa-crypto-binance-socket (Recommended)

Since the `petrosa-crypto-binance-socket` repository already has these secrets configured:

1. **Go to GitHub Web Interface**:
   - Navigate to: https://github.com/PetroSa2/petrosa-crypto-binance-socket/settings/secrets/actions
   - Click on `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`
   - Copy the values

2. **Set the secrets in petrosa-socket-client**:
   ```bash
   cd /Users/yurisa2/petrosa/petrosa-socket-client

   # Set Docker Hub username
   gh secret set DOCKERHUB_USERNAME -b "your-dockerhub-username"

   # Set Docker Hub token
   gh secret set DOCKERHUB_TOKEN -b "your-dockerhub-token"
   ```

## Method 2: Create New Docker Hub Credentials

1. **Go to Docker Hub**:
   - Visit: https://hub.docker.com/settings/security
   - Click "New Access Token"
   - Give it a name (e.g., "Petrosa CI/CD")
   - Copy the token

2. **Set the secrets**:
   ```bash
   cd /Users/yurisa2/petrosa/petrosa-socket-client

   # Set Docker Hub username
   gh secret set DOCKERHUB_USERNAME -b "your-dockerhub-username"

   # Set Docker Hub token
   gh secret set DOCKERHUB_TOKEN -b "your-new-access-token"
   ```

## Verify Setup

After setting the secrets, verify they're configured:

```bash
gh secret list
```

You should see:
- ✅ KUBE_CONFIG_DATA
- ✅ DOCKERHUB_USERNAME
- ✅ DOCKERHUB_TOKEN

## Test Deployment

Once all secrets are configured, you can test the deployment by:

1. **Push to main branch** to trigger deployment
2. **Or create a test commit**:
   ```bash
   git add .
   git commit -m "test: trigger deployment"
   git push origin main
   ```

## Troubleshooting

If you encounter issues:

1. **Check secret names**: Ensure they match exactly (case-sensitive)
2. **Verify Docker Hub credentials**: Test with `docker login`
3. **Check GitHub Actions logs**: Look for authentication errors
4. **Verify repository permissions**: Ensure the repository can access the secrets
