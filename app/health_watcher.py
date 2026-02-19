import time
import asyncio
from app.health import system_healthy
from app.ws import ws_manager
from app.logger import health_logger
from app.state import kiosk_state

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
                    except Exception as e :
                        health_logger.error(f"Broadcast exception: {e}")
                else:
                    if kiosk_state.is_handling_print_error():
                        health_logger.error(f"Print job is handling the eror")
                    else:
                        try:
                            #health_logger.info("started health watcher")  # Use loop.run_until_complete to run async function
                            loop.run_until_complete(
                                ws_manager.broadcast({"event": "OUT_OF_SERVICE"})
                            )
                        except Exception as e :
                            health_logger.error(f"Broadcast exception: {e}")
                
                last_state = healthy
                # No state change - log current status periodically
        except Exception as e:
            health_logger.error(f"Health watcher error: {e}", exc_info=True)
        
        time.sleep(10)  # Check every 10 seconds
