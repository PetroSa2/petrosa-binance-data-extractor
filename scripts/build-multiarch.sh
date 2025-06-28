#!/bin/bash
set -e

# Multi-architecture Docker build and push script
# Builds for amd64 (Intel/AMD) and arm64 (Apple Silicon, ARM servers)

# Configuration
DOCKER_HUB_USERNAME="${DOCKER_HUB_USERNAME:-}"
IMAGE_NAME="petrosa-binance-extractor"
VERSION="${VERSION:-latest}"
PLATFORMS="linux/amd64,linux/arm64"

# Build arguments
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
COMMIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo "🚀 Multi-Architecture Docker Build"
echo "=================================="
echo "Image: ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo "Platforms: ${PLATFORMS}"
echo "Build Date: ${BUILD_DATE}"
echo "Commit SHA: ${COMMIT_SHA}"
echo ""

# Check if Docker Hub username is provided
if [ -z "$DOCKER_HUB_USERNAME" ]; then
    echo "❌ Error: DOCKER_HUB_USERNAME environment variable is required"
    echo "Please set it with: export DOCKER_HUB_USERNAME=your-username"
    exit 1
fi

# Check if logged into Docker Hub
if ! docker info | grep -q "Username:"; then
    echo "❌ Error: Not logged into Docker Hub"
    echo "Please login with: docker login"
    exit 1
fi

# Create buildx builder if it doesn't exist
if ! docker buildx ls | grep -q "multiarch"; then
    echo "🔧 Creating multi-platform builder..."
    docker buildx create --name multiarch --driver docker-container --bootstrap
fi

# Use the multiarch builder
docker buildx use multiarch

# Build and push multi-platform image
echo "🏗️  Building multi-platform image..."
docker buildx build \
    --platform "${PLATFORMS}" \
    --target production \
    --build-arg VERSION="${VERSION}" \
    --build-arg COMMIT_SHA="${COMMIT_SHA}" \
    --build-arg BUILD_DATE="${BUILD_DATE}" \
    --tag "${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION}" \
    --tag "${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:latest" \
    --push \
    .

echo ""
echo "✅ Multi-platform build completed successfully!"
echo "📦 Image pushed to: ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo ""
echo "🔍 Image details:"
docker buildx imagetools inspect "${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION}"

echo ""
echo "🚀 To deploy, update your Kubernetes YAML with:"
echo "   image: ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION}"
