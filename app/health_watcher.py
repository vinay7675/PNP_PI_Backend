import time
import asyncio
from app.health import system_healthy
from app.ws import ws_manager
from app.logger import health_logger

def start_health_watcher():
    last_state = None

    while True:
        healthy = system_healthy()

        if healthy != last_state:
            if healthy:
                health_logger.info("System HEALTHY")
                ws_manager.broadcast({"event": "HEALTHY"})
            else:
                health_logger.error("System OUT_OF_SERVICE")
                ws_manager.broadcast({"event": "OUT_OF_SERVICE"})
            last_state = healthy

        time.sleep(10)  # check every 10 seconds
