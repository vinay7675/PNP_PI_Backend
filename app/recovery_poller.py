import asyncio
import httpx
from app.logger import app_logger, event_logger
from app.ws import ws_manager

# Global flag to track if we're in OUT_OF_SERVICE state
_is_out_of_service = False
_poller_task = None

async def check_server_health(server_url: str) -> bool:
    """Check if the server is reachable and responding"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            # Try a simple GET to the base URL or health endpoint
            # Adjust this based on your actual server's health check endpoint
            resp = await client.get(server_url.replace('/kiosk', '/health'), follow_redirects=True)
            return resp.status_code == 200
    except Exception as e:
        app_logger.debug(f"Server health check failed: {e}")
        return False

async def poll_server_recovery(server_url: str, interval: int = 10):
    """Poll the server until it's healthy again"""
    global _is_out_of_service
    
    event_logger.info("Starting server recovery polling")
    
    while _is_out_of_service:
        await asyncio.sleep(interval)
        
        app_logger.info("Checking server availability...")
        is_healthy = await check_server_health(server_url)
        
        if is_healthy:
            event_logger.info("Server is back online! Broadcasting HEALTHY event")
            _is_out_of_service = False
            
            try:
                await ws_manager.broadcast({"event": "HEALTHY"})
            except Exception as e:
                app_logger.error(f"Failed to broadcast HEALTHY event: {e}")
            
            break
        else:
            app_logger.debug(f"Server still unavailable, will retry in {interval}s")
    
    event_logger.info("Server recovery polling stopped")

def start_recovery_polling(server_url: str, interval: int = 10):
    """Start the recovery polling task"""
    global _is_out_of_service, _poller_task
    
    if _is_out_of_service:
        app_logger.info("Recovery polling already active")
        return
    
    _is_out_of_service = True
    
    # Create a background task for polling
    _poller_task = asyncio.create_task(poll_server_recovery(server_url, interval))

def is_in_recovery_mode() -> bool:
    """Check if system is currently in recovery mode"""
    return _is_out_of_service
