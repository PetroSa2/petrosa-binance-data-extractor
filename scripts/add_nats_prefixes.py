#!/usr/bin/env python3
"""
Script to add NATS subject prefix environment variables to Kubernetes cronjob files
"""

import os
import re

def add_nats_prefixes_to_file(file_path):
    """Add NATS subject prefix environment variables to a Kubernetes YAML file."""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Define the NATS subject prefix variables to add
    nats_prefixes = '''            - name: NATS_SUBJECT_PREFIX
              valueFrom:
                configMapKeyRef:
                  name: petrosa-common-config
                  key: NATS_SUBJECT_PREFIX
            - name: NATS_SUBJECT_PREFIX_PRODUCTION
              valueFrom:
                configMapKeyRef:
                  name: petrosa-common-config
                  key: NATS_SUBJECT_PREFIX_PRODUCTION
            - name: NATS_SUBJECT_PREFIX_GAP_FILLER
              valueFrom:
                configMapKeyRef:
                  name: petrosa-common-config
                  key: NATS_SUBJECT_PREFIX_GAP_FILLER'''
    
    # Pattern to find NATS_ENABLED and add the new variables after it
    pattern = r'(\s*-\s*name:\s*NATS_ENABLED\s*\n\s*valueFrom:\s*\n\s*configMapKeyRef:\s*\n\s*name:\s*petrosa-common-config\s*\n\s*key:\s*NATS_ENABLED\s*\n)'
    
    # Replace all occurrences
    new_content = re.sub(pattern, r'\1' + nats_prefixes + '\n', content)
    
    # Write the updated content back to the file
    with open(file_path, 'w') as f:
        f.write(new_content)
    
    print(f"✅ Updated {file_path}")

def main():
    """Main function to update all cronjob files."""
    
    # List of files to update
    files_to_update = [
        'k8s/klines-mongodb-production.yaml',
        'k8s/klines-all-timeframes-cronjobs.yaml',
        'k8s/klines-gap-filler-cronjob.yaml'
    ]
    
    for file_path in files_to_update:
        if os.path.exists(file_path):
            add_nats_prefixes_to_file(file_path)
        else:
            print(f"❌ File not found: {file_path}")
    
    print("🎉 NATS subject prefixes added to all cronjob files!")

if __name__ == "__main__":
    main() 