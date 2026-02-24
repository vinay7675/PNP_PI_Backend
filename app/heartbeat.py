import time
import asyncio
from app.health import system_healthy
from app.ws import ws_manager
from app.logger import health_logger, app_logger
from app.state import kiosk_state
from app.notification_queue import notification_queue

def start_heartbeat():
    """Background health monitor thread"""
    
    # Create event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    health_logger.info("started heartbeat")
    
    '''time.sleep(6)'''
    while True:
        try:
            loop.run_until_complete(
                send_server_heartbeat("Tiger Zinda Hai")
            )
        except Exception as e:
            health_logger.error(f"Heartbeat error: {e}", exc_info=True)
        
        time.sleep(300)  # Send every 300 seconds

async def send_server_heartbeat(message_str: str):
    import httpx
    from app.server_api import SERVER_URL, KIOSK_ID
    
    notify_url = f"{SERVER_URL}/{KIOSK_ID}/heartbeat"
    
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                notify_url,
                json={
                    "message": f"{message_str}  Kiosk ID : {KIOSK_ID}"
                }
            )
            
            if resp.status_code == 200:
                '''event_logger.info(f"Server to send heartbeat: {code}")'''
            else:
                '''app_logger.warning(f"Failed to send heartbeat: {resp.status_code}")'''
                
    except Exception as e:
        app_logger.error(f"Failed to send heartbeat: {e}")
