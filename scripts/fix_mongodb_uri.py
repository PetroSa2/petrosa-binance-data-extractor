#!/usr/bin/env python3
"""
Script to fix MongoDB URI references in Kubernetes manifests to use the secret instead of configmap
"""

import os
import re


def fix_mongodb_uri_in_file(file_path):
    """Fix MongoDB URI references to use secret instead of configmap."""

    with open(file_path) as f:
        content = f.read()

    # Replace configmap reference with secret reference
    old_pattern = r"(\s*-\s*name:\s*MONGODB_URI\s*\n\s*valueFrom:\s*\n\s*configMapKeyRef:\s*\n\s*name:\s*petrosa-common-config\s*\n\s*key:\s*MONGODB_URI\s*\n)"
    new_replacement = """            - name: MONGODB_URI
              valueFrom:
                secretKeyRef:
                  name: petrosa-sensitive-credentials
                  key: mongodb-connection-string
"""

    # Replace all occurrences
    new_content = re.sub(old_pattern, new_replacement, content)

    # Write the updated content back to the file
    with open(file_path, "w") as f:
        f.write(new_content)

    print(f"✅ Updated {file_path}")


def main():
    """Main function to update all MongoDB production files."""

    # List of files to update
    files_to_update = ["k8s/klines-mongodb-production.yaml"]

    for file_path in files_to_update:
        if os.path.exists(file_path):
            fix_mongodb_uri_in_file(file_path)
        else:
            print(f"❌ File not found: {file_path}")

    print("🎉 MongoDB URI references updated to use secret!")


if __name__ == "__main__":
    main()
