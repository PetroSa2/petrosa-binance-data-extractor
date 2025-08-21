#!/bin/bash

echo "🔧 Copying test script to pod..."
kubectl --kubeconfig=k8s/kubeconfig.yaml cp scripts/test_mysql_connectivity.py petrosa-apps/petrosa-binance-data-extractor-66f5b67c79-k8bp7:/tmp/test_mysql_connectivity.py

echo "🚀 Running connectivity test inside pod..."
kubectl --kubeconfig=k8s/kubeconfig.yaml exec -n petrosa-apps petrosa-binance-data-extractor-66f5b67c79-k8bp7 -- python3 /tmp/test_mysql_connectivity.py

echo "🧹 Cleaning up..."
kubectl --kubeconfig=k8s/kubeconfig.yaml exec -n petrosa-apps petrosa-binance-data-extractor-66f5b67c79-k8bp7 -- rm -f /tmp/test_mysql_connectivity.py
