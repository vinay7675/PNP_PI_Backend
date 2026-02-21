import asyncio
import httpx
import json
import os
from datetime import datetime
from app.logger import app_logger, event_logger

QUEUE_FILE = "/home/vinay/backend/notification_queue.json"

class NotificationQueue:
    def __init__(self):
        self.queue = []
        self.load_queue()
    
    def load_queue(self):
        """Load pending notifications from disk"""
        try:
            if os.path.exists(QUEUE_FILE):
                with open(QUEUE_FILE, 'r') as f:
                    self.queue = json.load(f)
                app_logger.info(f"Loaded {len(self.queue)} pending notifications")
        except Exception as e:
            app_logger.error(f"Failed to load notification queue: {e}")
            self.queue = []
    
    def save_queue(self):
        """Save pending notifications to disk"""
        try:
            with open(QUEUE_FILE, 'w') as f:
                json.dump(self.queue, f, indent=2)
        except Exception as e:
            app_logger.error(f"Failed to save notification queue: {e}")
    
    def add(self, url: str, payload: dict):
        """Add a notification to the queue"""
        notification = {
            "url": url,
            "payload": payload,
            "timestamp": datetime.now().isoformat(),
            "attempts": 0
        }
        self.queue.append(notification)
        self.save_queue()
        app_logger.info(f"Added notification to queue: {payload.get('code')}")
    
    async def process_queue(self):
        """Try to send all pending notifications"""
        if not self.queue:
            return
        
        app_logger.info(f"Processing {len(self.queue)} pending notifications...")
        
        sent = []
        for notification in self.queue:
            notification["attempts"] += 1
            
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.post(
                        notification["url"],
                        json=notification["payload"]
                    )
                    
                    if resp.status_code == 200:
                        event_logger.info(f"✅ Sent queued notification: {notification['payload'].get('code')} to {notification['url']}")
                        sent.append(notification)
                    else:
                        app_logger.warning(f"Server returned {resp.status_code} for queued notification")
                        
            except Exception as e:
                app_logger.error(f"Failed to send queued notification (attempt {notification['attempts']}): {e}")
            
            # Give up after 10 attempts
            if notification["attempts"] >= 10:
                app_logger.error(f"Giving up on notification after 10 attempts: {notification['payload'].get('code')}")
                sent.append(notification)  # Remove it from queue
        
        # Remove successfully sent notifications
        for notification in sent:
            self.queue.remove(notification)
        
        self.save_queue()
        app_logger.info(f"Queue processed. Remaining: {len(self.queue)}")

# Global instance
notification_queue = NotificationQueue()
