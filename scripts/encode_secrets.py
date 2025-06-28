#!/usr/bin/env python3
"""
Utility script to encode secrets for Kubernetes deployment.
This script helps encode API keys and database URIs to base64 for use in Kubernetes secrets.
"""

import base64
import getpass


def encode_secret(value: str) -> str:
    """Encode a string to base64."""
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


def main():
    print("🔐 Kubernetes Secret Encoder for Binance Extractor")
    print("=" * 60)

    # Binance API Key
    api_key = getpass.getpass("Enter Binance API Key: ")
    api_key_encoded = encode_secret(api_key)
    print(f"✅ Encoded API Key: {api_key_encoded}")

    # Binance API Secret
    api_secret = getpass.getpass("Enter Binance API Secret: ")
    api_secret_encoded = encode_secret(api_secret)
    print(f"✅ Encoded API Secret: {api_secret_encoded}")

    # MySQL URI
    mysql_uri = getpass.getpass("Enter MySQL URI: ")
    mysql_uri_encoded = encode_secret(mysql_uri)
    print(f"✅ Encoded MySQL URI: {mysql_uri_encoded}")

    print("\n" + "=" * 60)
    print("📋 Copy the following values to your secrets.yaml:")
    print("=" * 60)

    secrets_yaml = f"""
apiVersion: v1
kind: Secret
metadata:
  name: binance-api-secret
  namespace: petrosa-apps
type: Opaque
data:
  api-key: {api_key_encoded}
  api-secret: {api_secret_encoded}

---
apiVersion: v1
kind: Secret
metadata:
  name: database-secret
  namespace: petrosa-apps
type: Opaque
data:
  mysql-uri: {mysql_uri_encoded}
"""

    print(secrets_yaml)

    # Save to file
    with open("k8s/secrets-generated.yaml", "w") as f:
        f.write(secrets_yaml)

    print("💾 Secrets saved to: k8s/secrets-generated.yaml")
    print("⚠️  Remember to keep this file secure and don't commit it to git!")


if __name__ == "__main__":
    main()
