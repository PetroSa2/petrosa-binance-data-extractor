"""
Standardized Heartbeat Service for Petrosa components.
Publishes a heartbeat to NATS every 30 seconds.
"""

import asyncio
import json
import logging
import os
import time
from typing import Optional

import nats
import nats.aio.client
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("heartbeat")


class HeartbeatMessage(BaseModel):
    """Standardized heartbeat message model."""
    service: str
    timestamp: float = Field(default_factory=time.time)
    version: str = os.getenv("VERSION", "1.0.0")
    status: str = "healthy"
    metadata: dict = Field(default_factory=dict)


class HeartbeatPublisher:
    """Publishes periodic heartbeats to NATS."""

    def __init__(self, service_name: str, nats_url: str):
        self.service_name = service_name
        self.nats_url = nats_url
        self.subject = f"heartbeat.{service_name}"
        self.interval = 30.0  # seconds
        self.nats_client: Optional[nats.aio.client.Client] = None
        self.is_running = False

    async def start(self):
        """Start the heartbeat publication loop."""
        self.is_running = True
        while self.is_running:
            try:
                if not self.nats_client or not self.nats_client.is_connected:
                    logger.info(f"Connecting to NATS at {self.nats_url}")
                    self.nats_client = await nats.connect(self.nats_url)

                message = HeartbeatMessage(service=self.service_name)
                await self.nats_client.publish(
                    self.subject, 
                    message.model_dump_json().encode()
                )
                logger.debug(f"Published heartbeat to {self.subject}")
                
            except Exception as e:
                logger.error(f"Error publishing heartbeat: {e}")
                self.nats_client = None  # Force reconnection next loop
            
            await asyncio.sleep(self.interval)

    def stop(self):
        """Stop the heartbeat loop."""
        self.is_running = False


async def main():
    service_name = os.getenv("SERVICE_NAME", "data-extractor")
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    
    logger.info(f"🚀 Starting heartbeat service for {service_name}")
    publisher = HeartbeatPublisher(service_name, nats_url)
    await publisher.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
