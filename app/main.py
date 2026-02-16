import threading
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.ws import ws_manager
from app.models import PrintRequest
from app.server_api import fetch_print_job, InvalidCode, UpstreamFailure, SERVER_URL
from app.printer import print_document, PrinterUnavailable
from app.health import system_healthy
from app.health_watcher import start_health_watcher
from app.logger import app_logger, event_logger
from app.diagnostics import run_diagnostics
from app.recovery_poller import start_recovery_polling, is_in_recovery_mode

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Let /print handle its own exceptions
    if request.url.path == "/print":
        raise exc
    
    app_logger.exception(f"Unhandled exception in {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "status": "ERROR"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.on_event("startup")
def startup():
    threading.Thread(target=start_health_watcher, daemon=True).start()

@app.post("/log/frontend")
def frontend_log(payload: dict):
    app_logger.error("FRONTEND | %s", payload)
    return {"ok": True}

@app.get("/health")
async def health():
    return system_healthy()

@app.get("/owner/health")
def owner_health():
    result = run_diagnostics()
    return {
        "status": "OK" if all(result.values()) else "FAIL",
        "checks": result
    }

@app.post("/print")
async def start_print(req: PrintRequest):
    try:
        # Step 1: Validate & fetch
        event_logger.info(
            "Request received to fetch the document with code : %s", req.code)
        await ws_manager.broadcast({"event": "FETCHING"})
        job = await fetch_print_job(req.code)
        print_options = {
            "color_mode": job["colorMode"],
            "duplex": job["duplex"],
            "copies": job["copies"],
            "orientation": job["orientation"],
            }
        # Step 2: Print
        event_logger.info(
            "successfull dowloaded the document with code : %s", req.code)
        await ws_manager.broadcast({"event": "PRINTING"})
        print_document(job["file_path"], code=req.code, jobId1=job["jobId2"], print_options=print_options)
        #await ws_manager.broadcast({"event": "DONE"})
        
        return JSONResponse(
            status_code=200,
            content={"status": "DONE"}
        )
        
    except InvalidCode:
        app_logger.error(
            "Code entered is not valid. Resulted in invalid state")
        try:
            await ws_manager.broadcast({"event": "INVALID_CODE"})
        except Exception as e:
            app_logger.error(f"Failed to broadcast INVALID_CODE: {e}")
        return JSONResponse(
            status_code=400,
            content={"status": "INVALID_CODE"}
        )
        
    except (UpstreamFailure, PrinterUnavailable) as e:
        app_logger.error(
            f"Error invoked in print job: {e}"
        )
        try:
            await ws_manager.broadcast({"event": "OUT_OF_SERVICE"})
        except Exception as broadcast_err:
            app_logger.error(f"Failed to broadcast OUT_OF_SERVICE: {broadcast_err}")
        
        # Start recovery polling if not already active
        if not is_in_recovery_mode():
            start_recovery_polling(SERVER_URL, interval=300)  # Poll every 10 seconds
        
        return JSONResponse(
            status_code=503,
            content={"status": "OUT_OF_SERVICE"}
        )
        
    except Exception as e:
        app_logger.exception(
            "Error invoked in user request"
        )
        try:
            await ws_manager.broadcast({"event": "OUT_OF_SERVICE"})
        except Exception as broadcast_err:
            app_logger.error(f"Failed to broadcast OUT_OF_SERVICE: {broadcast_err}")
        
        # Start recovery polling if not already active
        if not is_in_recovery_mode():
            start_recovery_polling(SERVER_URL, interval=300)
        
        return JSONResponse(
            status_code=500,
            content={"status": "OUT_OF_SERVICE"}
        )

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except:
        event_logger.exception("Unable to establish websocket")
        ws_manager.disconnect(ws)
