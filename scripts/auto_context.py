#!/usr/bin/env python3
"""
Auto Context Script for Cursor
Automatically reads key documentation and provides context
"""

import os
import sys


def read_file_safely(filepath, max_lines=30):
    """Read file safely with line limit"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join(lines[:max_lines]) + (
                "..." if len(lines) > max_lines else ""
            )
    except FileNotFoundError:
        return f"❌ File not found: {filepath}"
    except Exception as e:
        return f"❌ Error reading {filepath}: {e}"


def check_kubeconfig():
    """Check kubeconfig status"""
    kubeconfig_path = "k8s/kubeconfig.yaml"
    if os.path.exists(kubeconfig_path):
        return "✅ kubeconfig.yaml exists\nUse: export KUBECONFIG=k8s/kubeconfig.yaml"
    else:
        return "❌ kubeconfig.yaml not found"


def main():
    print("=== CURSOR AUTO CONTEXT ===")
    print("Reading key documentation files...")
    print()

    # Read setup guide
    print("📖 REPOSITORY_SETUP_GUIDE.md:")
    print("-" * 40)
    setup_content = read_file_safely("docs/REPOSITORY_SETUP_GUIDE.md")
    print(setup_content)
    print()

    # Read quick reference
    print("📋 QUICK_REFERENCE.md:")
    print("-" * 40)
    quick_content = read_file_safely("docs/QUICK_REFERENCE.md")
    print(quick_content)
    print()

    # Check kubeconfig
    print("🔧 KUBECONFIG STATUS:")
    print("-" * 40)
    print(check_kubeconfig())
    print()

    print("=== END CONTEXT ===")
    print()
    print("💡 TIP: Copy the output above into your Cursor prompt!")

    # If run with argument, include specific context
    if len(sys.argv) > 1:
        context_type = sys.argv[1].lower()
        print(f"\n🎯 CONTEXT FOR: {context_type.upper()}")
        print("-" * 40)

        if context_type in ["deploy", "deployment", "k8s", "kubernetes"]:
            print("Use kubectl with --kubeconfig=k8s/kubeconfig.yaml")
            print("Only use existing secret 'petrosa-sensitive-credentials'")
            print("Only use existing configmap 'petrosa-common-config'")
        elif context_type in ["pipeline", "ci", "cd"]:
            print(
                "Run tests: python -m pytest tests/ -v --cov=. --cov-report=term --tb=short"
            )
            print(
                "Fix linting: flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics"
            )
            print(
                "Use GitHub CLI with file output: gh command > /tmp/file.json && cat /tmp/file.json"
            )
        elif context_type in ["python", "code"]:
            print("Follow PEP 8 formatting")
            print("Use type hints")
            print("Add proper error handling with try/catch")
            print("Add logging for debugging")


if __name__ == "__main__":
    main()
