#!/bin/bash

# Script to implement VERSION_PLACEHOLDER protection across all Petrosa services
# This script will copy the protection system to all services in the workspace

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# List of services to implement protection for
SERVICES=(
    "petrosa-bot-ta-analysis"
    "petrosa-tradeengine"
    "petrosa-socket-client"
    "petrosa-realtime-strategies"
)

# Function to implement protection for a single service
implement_service_protection() {
    local service=$1
    local service_dir="../$service"

    print_status "🔧 Implementing VERSION_PLACEHOLDER protection for $service..."

    # Check if service directory exists
    if [ ! -d "$service_dir" ]; then
        print_warning "⚠️  Service directory $service_dir not found, skipping..."
        return 0
    fi

    # Create docs directory if it doesn't exist
    if [ ! -d "$service_dir/docs" ]; then
        mkdir -p "$service_dir/docs"
        print_status "Created docs directory for $service"
    fi

    # Copy Cursor AI rules
    if [ -f "docs/CURSOR_AI_VERSION_RULES.md" ]; then
        cp docs/CURSOR_AI_VERSION_RULES.md "$service_dir/docs/"
        print_success "Copied CURSOR_AI_VERSION_RULES.md to $service"
    fi

    # Create scripts directory if it doesn't exist
    if [ ! -d "$service_dir/scripts" ]; then
        mkdir -p "$service_dir/scripts"
        print_status "Created scripts directory for $service"
    fi

    # Copy version management scripts
    if [ -f "scripts/pre-commit-version-check.sh" ]; then
        cp scripts/pre-commit-version-check.sh "$service_dir/scripts/"
        chmod +x "$service_dir/scripts/pre-commit-version-check.sh"
        print_success "Copied pre-commit-version-check.sh to $service"
    fi

    if [ -f "scripts/install-git-hooks.sh" ]; then
        cp scripts/install-git-hooks.sh "$service_dir/scripts/"
        chmod +x "$service_dir/scripts/install-git-hooks.sh"
        print_success "Copied install-git-hooks.sh to $service"
    fi

    if [ -f "scripts/version-manager.sh" ]; then
        cp scripts/version-manager.sh "$service_dir/scripts/"
        chmod +x "$service_dir/scripts/version-manager.sh"
        print_success "Copied version-manager.sh to $service"
    fi

    # Update Makefile if it exists
    if [ -f "$service_dir/Makefile" ]; then
        print_status "Updating Makefile for $service..."

        # Check if version management commands already exist
        if ! grep -q "version-check" "$service_dir/Makefile"; then
            # Add to .PHONY line
            sed -i.bak 's/\.PHONY: \(.*\)/\.PHONY: \1 version-check version-info version-debug install-git-hooks/' "$service_dir/Makefile"

            # Add version management section to help
            sed -i.bak '/📊 Utilities:/a\
	@echo "🔢 Version Management:"\
	@echo "  version-check  - Check VERSION_PLACEHOLDER integrity"\
	@echo "  version-info   - Show version information"\
	@echo "  version-debug  - Debug version issues"\
	@echo "  install-git-hooks - Install VERSION_PLACEHOLDER protection hooks"' "$service_dir/Makefile"

            # Add version management commands at the end
            cat >> "$service_dir/Makefile" << 'EOF'

# Version Management
version-check:
	@echo "🔍 Checking VERSION_PLACEHOLDER integrity..."
	@if [ -f "scripts/version-manager.sh" ]; then \
		./scripts/version-manager.sh validate; \
	else \
		echo "❌ scripts/version-manager.sh not found"; \
		exit 1; \
	fi

version-info:
	@echo "📦 Version Information:"
	@if [ -f "scripts/version-manager.sh" ]; then \
		./scripts/version-manager.sh info; \
	else \
		echo "❌ scripts/version-manager.sh not found"; \
		exit 1; \
	fi

version-debug:
	@echo "🐛 Version Debug Information:"
	@if [ -f "scripts/version-manager.sh" ]; then \
		./scripts/version-manager.sh debug; \
	else \
		echo "❌ scripts/version-manager.sh not found"; \
		exit 1; \
	fi

install-git-hooks:
	@echo "🔧 Installing git hooks for VERSION_PLACEHOLDER protection..."
	@if [ -f "scripts/install-git-hooks.sh" ]; then \
		chmod +x scripts/install-git-hooks.sh; \
		./scripts/install-git-hooks.sh; \
	else \
		echo "❌ scripts/install-git-hooks.sh not found"; \
		exit 1; \
	fi
EOF

            rm -f "$service_dir/Makefile.bak"
            print_success "Updated Makefile for $service"
        else
            print_status "Version management commands already exist in $service Makefile"
        fi
    else
        print_warning "⚠️  Makefile not found in $service"
    fi

    # Update .cursorrules if it exists
    if [ -f "$service_dir/.cursorrules" ]; then
        print_status "Updating .cursorrules for $service..."

        # Check if VERSION_PLACEHOLDER rules already exist
        if ! grep -q "VERSION_PLACEHOLDER.*Never replace" "$service_dir/.cursorrules"; then
            # Add VERSION_PLACEHOLDER rules to the end
            cat >> "$service_dir/.cursorrules" << 'EOF'

## 🚨 VERSION_PLACEHOLDER RULES (CRITICAL)

### NEVER DO THESE:
- Replace VERSION_PLACEHOLDER with specific versions (v1.0.1, latest, etc.)
- Suggest "fixing" VERSION_PLACEHOLDER in Kubernetes manifests
- Commit manifests with real versions instead of placeholders
- Change VERSION_PLACEHOLDER to any other value

### ALWAYS DO THESE:
- Leave VERSION_PLACEHOLDER exactly as is in all k8s/ files
- Understand VERSION_PLACEHOLDER is intentional and correct
- Use version management scripts for version changes
- Help debug version issues without touching placeholders

### Version Management:
- Use `./scripts/create-release.sh` for version changes
- Use `make version-check` to verify version system
- Use `make version-info` to see version information
- VERSION_PLACEHOLDER gets replaced by CI/CD automatically

### If Asked About VERSION_PLACEHOLDER:
- Explain it's intentional and part of the deployment system
- Suggest using version management scripts instead
- Never suggest manual replacement
- Point to VERSION_PLACEHOLDER_GUIDE.md for details
EOF
            print_success "Updated .cursorrules for $service"
        else
            print_status "VERSION_PLACEHOLDER rules already exist in $service .cursorrules"
        fi
    else
        print_warning "⚠️  .cursorrules not found in $service"
    fi

    print_success "✅ VERSION_PLACEHOLDER protection implemented for $service"
}

# Main execution
main() {
    print_status "🚀 Implementing VERSION_PLACEHOLDER protection across all Petrosa services..."
    print_status "Services to process: ${SERVICES[*]}"
    echo ""

    # Implement protection for each service
    for service in "${SERVICES[@]}"; do
        implement_service_protection "$service"
        echo ""
    done

    print_success "🎉 VERSION_PLACEHOLDER protection implementation completed!"
    echo ""
    print_status "Next steps for each service:"
    echo "1. Navigate to the service directory"
    echo "2. Run: make install-git-hooks"
    echo "3. Test: make version-check"
    echo "4. Verify: make version-info"
    echo ""
    print_status "For more information, see: docs/CURSOR_AI_VERSION_RULES.md"
}

# Run main function
main "$@"
