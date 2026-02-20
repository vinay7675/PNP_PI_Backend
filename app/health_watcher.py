import time
import asyncio
from app.health import system_healthy
from app.ws import ws_manager
from app.logger import health_logger, app_logger
from app.state import kiosk_state
from app.notification_queue import notification_queue

def start_health_watcher():
    """Background health monitor thread"""
    
    # Create event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    health_logger.info("started health watcher")
    
    last_state = None
    time.sleep(5)
    while True:
        try:
            healthy = system_healthy()
            #health_logger.info("in health watcher loop")
            if healthy != last_state:
                if healthy:
                    # Use loop.run_until_complete to run async function
                    try:
                        loop.run_until_complete(
                            ws_manager.broadcast({"event": "HEALTHY"})
                        )
                        loop.run_until_complete(
                            notification_queue.process_queue()
                        )
                    except Exception as e :
                        health_logger.error(f"Broadcast exception: {e}")
                    last_state = healthy
                else:
                    if kiosk_state.is_handling_print_error():
                        health_logger.error(f"Print job is handling the eror")
                        last_state = None
                    else:
                        try:
                            #health_logger.info("started health watcher")  # Use loop.run_until_complete to run async function
                            loop.run_until_complete(
                                ws_manager.broadcast({"event": "OUT_OF_SERVICE"})
                            )
                        except Exception as e :
                            health_logger.error(f"Broadcast exception: {e}")
                        loop.run_until_complete(
                                send_server_outOfService("Printer is offline or the system is out of service.")
                        )    
                        last_state = healthy
                # No state change - log current status periodically
        except Exception as e:
            health_logger.error(f"Health watcher error: {e}", exc_info=True)
        
        time.sleep(10)  # Check every 10 seconds

async def send_server_outOfService(message_str: str):
    import httpx
    from app.server_api import SERVER_URL, KIOSK_ID
    
    notify_url = f"{SERVER_URL}/{KIOSK_ID}/out_of_service"
    
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                notify_url,
                json={
                    "message": f"{message_str}  Kiosk ID : {KIOSK_ID}"
                }
            )
            
            if resp.status_code == 200:
                event_logger.info(f"Server notification for Out of Service Successful: {code}")
            else:
                app_logger.warning(f"Failed to notify out of service to server: {resp.status_code}")
                
    except Exception as e:
        app_logger.error(f"Failed to notify out of service to server: {e}")
