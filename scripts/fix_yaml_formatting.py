#!/usr/bin/env python3
"""
Script to fix YAML formatting issues in MongoDB production manifest
"""

import re

def fix_yaml_formatting(file_path):
    """Fix YAML formatting issues in the MongoDB production manifest."""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix missing newlines between environment variables
    # Pattern: key: BINANCE_API_SECRET\n              valueFrom:\n                secretKeyRef:\n                  name: petrosa-sensitive-credentials\n                  key: BINANCE_API_SECRET            - name: MONGODB_URI
    # Replace with proper formatting
    pattern1 = r'(key: BINANCE_API_SECRET\s*\n\s*valueFrom:\s*\n\s*secretKeyRef:\s*\n\s*name: petrosa-sensitive-credentials\s*\n\s*key: BINANCE_API_SECRET)\s*-\s*name:\s*MONGODB_URI'
    replacement1 = r'\1\n            - name: MONGODB_URI'
    
    content = re.sub(pattern1, replacement1, content)
    
    # Also fix the simpler pattern
    pattern2 = r'(key: BINANCE_API_SECRET)\s*-\s*name:\s*MONGODB_URI'
    replacement2 = r'\1\n            - name: MONGODB_URI'
    
    content = re.sub(pattern2, replacement2, content)
    
    # Write the updated content back to the file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed YAML formatting in {file_path}")

def main():
    """Main function to fix YAML formatting."""
    
    files_to_fix = [
        'k8s/klines-mongodb-production.yaml'
    ]
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            fix_yaml_formatting(file_path)
        else:
            print(f"❌ File not found: {file_path}")
    
    print("🎉 YAML formatting fixed!")

if __name__ == "__main__":
    import os
    main() 