#!/usr/bin/env python3
"""
NATS Message Monitor
Monitors binance extraction messages from NATS server
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import nats
except ImportError:
    print("nats-py not found. Installing...")
    os.system("pip install nats-py")
    import nats

async def monitor_nats_messages():
    """Monitor NATS messages for binance extraction events"""
    
    # NATS server URL - try different options
    nats_urls = [
        "nats://localhost:4222",  # If port-forward is working
        "nats://nats-server.nats.svc.cluster.local:4222",  # Direct cluster DNS
        "nats://10.152.183.189:4222"  # Direct IP
    ]
    
    nc = None
    for url in nats_urls:
        try:
            print(f"Attempting to connect to {url}...")
            nc = await nats.connect(url)
            print(f"✅ Connected to NATS at {url}")
            break
        except Exception as e:
            print(f"❌ Failed to connect to {url}: {e}")
            continue
    
    if nc is None:
        print("❌ Could not connect to any NATS server")
        return
    
    try:
        # Subscribe to all binance extraction messages
        subscription = await nc.subscribe("binance.extraction.klines.*")
        
        print("🔍 Monitoring NATS messages...")
        print("📡 Waiting for binance extraction messages...")
        print("💡 To generate messages, run a binance extraction job")
        print("=" * 60)
        
        async for msg in subscription.messages:
            try:
                # Parse the message data
                data = json.loads(msg.data.decode())
                
                # Extract useful information
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                subject = msg.subject
                
                print(f"\n📨 [{timestamp}] Message received:")
                print(f"   Subject: {subject}")
                print(f"   Data: {json.dumps(data, indent=2)}")
                print("-" * 60)
                
            except json.JSONDecodeError:
                print(f"📨 Raw message: {msg.data.decode()}")
            except Exception as e:
                print(f"❌ Error processing message: {e}")
    
    except Exception as e:
        print(f"❌ Error in message monitoring: {e}")
    finally:
        await nc.close()

if __name__ == "__main__":
    print("🚀 Starting NATS Message Monitor")
    print("=" * 60)
    
    try:
        asyncio.run(monitor_nats_messages())
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}") 