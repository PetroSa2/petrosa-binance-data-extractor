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


def main() -> None:
    print("🔐 Kubernetes Secret Encoder for Binance Extractor")
    print("=" * 60)

    print("\n" + "=" * 60)
    print("📋 No secrets to encode at this time.")
    print("=" * 60)

    print("💾 No secrets file generated.")
    print("⚠️  Remember to keep any secret files secure and don't commit them to git!")


if __name__ == "__main__":
    main()
