#!/bin/bash

# Cursor Helper Script
# This script automatically reads key documentation files and provides context

echo "=== CURSOR CONTEXT HELPER ==="
echo "Reading key documentation files..."
echo ""

# Read and display setup guide
echo "📖 REPOSITORY_SETUP_GUIDE.md:"
echo "----------------------------------------"
if [ -f "docs/REPOSITORY_SETUP_GUIDE.md" ]; then
    head -50 docs/REPOSITORY_SETUP_GUIDE.md
    echo "... (truncated for brevity)"
else
    echo "❌ File not found: docs/REPOSITORY_SETUP_GUIDE.md"
fi
echo ""

# Read and display quick reference
echo "📋 QUICK_REFERENCE.md:"
echo "----------------------------------------"
if [ -f "docs/QUICK_REFERENCE.md" ]; then
    head -50 docs/QUICK_REFERENCE.md
    echo "... (truncated for brevity)"
else
    echo "❌ File not found: docs/QUICK_REFERENCE.md"
fi
echo ""

# Check kubeconfig
echo "🔧 KUBECONFIG STATUS:"
echo "----------------------------------------"
if [ -f "k8s/kubeconfig.yaml" ]; then
    echo "✅ kubeconfig.yaml exists"
    echo "Use: export KUBECONFIG=k8s/kubeconfig.yaml"
else
    echo "❌ kubeconfig.yaml not found"
fi
echo ""

echo "=== END CONTEXT ==="
echo ""
echo "💡 TIP: Copy the output above into your Cursor prompt for automatic context!" 