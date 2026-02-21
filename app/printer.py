import subprocess
import threading
import time
import asyncio
import os
from app.ws import ws_manager
from app.logger import app_logger, event_logger
from app.health import printer_connected
from app.state import kiosk_state
from app.notification_queue import notification_queue

class PrinterUnavailable(Exception):
    pass

def get_default_printer():
    """Get the default printer name"""
    try:
        result = subprocess.run(
            ["lpstat", "-d"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout:
            # Output: "system default destination: printer_name"
            default = result.stdout.strip().split(":")[-1].strip()
            return default
        else:
            # No default, get first available printer
            result = subprocess.run(
                ["lpstat", "-p"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and "printer" in result.stdout:
                # Extract first printer name
                first_line = result.stdout.split("\n")[0]
                printer_name = first_line.split()[1]
                return printer_name
            
            raise PrinterUnavailable("NO_PRINTER_FOUND")
            
    except subprocess.TimeoutExpired:
        raise PrinterUnavailable("PRINTER_CHECK_TIMEOUT")
    except Exception as e:
        app_logger.error(f"Error getting printer: {e}")
        raise PrinterUnavailable(f"PRINTER_ERROR: {e}")

def build_lp_command(printer: str, file_path: str, options: dict):
    """
    Build lp command with print options
    
    options dict can include:
    - color_mode: "color" or "monochrome"
    - duplex: "two-sided-long-edge" or "two-sided-short-edge" or "one-sided"
    - copies: integer (number of copies)
    - page_range: "1-5" (specific pages)
    - orientation: "portrait" or "landscape"
    - media: "A4" or "Letter"
    - quality: "draft", "normal", "high"
    """
    
    cmd = ["lp", "-d", printer]
    
    # Color mode
    if options.get("color_mode") == "monochrome":
        cmd.extend(["-o", "ColorModel=Gray"])
    elif options.get("color_mode") == "color":
        cmd.extend(["-o", "ColorModel=RGB"])
    
    # Duplex (double-sided printing)
    duplex = options.get("duplex", "one-sided")
    if duplex:
        cmd.extend(["-o", "sides=two-sided-long-edge"])
    else:
        cmd.extend(["-o", "sides=one-sided"])
    
    # Number of copies
    copies = options.get("copies", 1)
    if copies > 1:
        cmd.extend(["-n", str(copies)])
    
    # Page range
    if "page_range" in options:
        cmd.extend(["-P", options["page_range"]])
    
    # Orientation
    if options.get("orientation") == "landscape":
        cmd.extend(["-o", "landscape"])
    
    # Paper size
    if "media" in options:
        cmd.extend(["-o", f"media={options['media']}"])
    
    # Print quality
    quality = options.get("quality")
    if quality == "draft":
        cmd.extend(["-o", "print-quality=3"])
    elif quality == "high":
        cmd.extend(["-o", "print-quality=5"])
    
    # Add file path at the end
    cmd.append(file_path)
    
    return cmd

def print_document(file_path: str, code: str = None, jobId1: str = None, print_options: dict = None):
    """
    Print a document with specified options
    
    Args:
        file_path: Path to PDF file
        code: Print code for tracking
        job_id: Job ID from server
        print_options: Dict with printing preferences (color, duplex, etc.)
    """
	
    if print_options is None:
        print_options = {}
    
    try:
        if printer_connected():
        # Get printer
            printer = get_default_printer()
            event_logger.info(f"Using printer: {printer}")
        
        # Build command with options
            cmd = build_lp_command(printer, file_path, print_options)
        
        # Log the command for debugging
            app_logger.info(f"Print command: {' '.join(cmd)}")
        
        # Execute print command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
        
            if result.returncode != 0:
                app_logger.error(f"Print command failed: {result.stderr}")
                raise PrinterUnavailable(f"PRINT_FAILED: {result.stderr}")
        
        # Extract job ID from lp output
        # Output format: "request id is printer-123 (1 file(s))"
            lp_job_id = None
            if "request id is" in result.stdout:
                lp_job_id = result.stdout.split("request id is")[1].split()[0].strip()
                event_logger.info(f"Print job submitted: {lp_job_id} (code: {code}, server job: {jobId1})")
        
        # Start monitoring in background
            threading.Thread(
                target=monitor_job,
                args=(lp_job_id, code, jobId1, printer, file_path),
                daemon=True
            ).start()
        
            return lp_job_id
        else:
            app_logger.error("Print command timed out")
            delete_temp_file(file_path)
            raise PrinterUnavailable("PRINTER_OFFlINE")
    except subprocess.TimeoutExpired:
        app_logger.error("Print command timed out")
        delete_temp_file(file_path)
        raise PrinterUnavailable("PRINT_TIMEOUT")
    except Exception as e:
        app_logger.error(f"Failed to print: {e}")
        delete_temp_file(file_path)
        raise PrinterUnavailable(f"PRINT_ERROR: {e}")

def monitor_job(lp_job_id: str, code: str, server_job_id: str, printer_name: str, file_path: str):
    """Monitor print job status using lpstat"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    timeout = 300  # 5 minutes
    start_time = time.time()
    kiosk_state.set_handling_print_error(True)
    try:
        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                event_logger.error(f"Print job {lp_job_id} timed out")
                #kiosk_state.set_handling_print_error(True)
                # Cancel the job
                try:
                    subprocess.run(["cancel", lp_job_id], timeout=5)
                except:
                    pass
                
                loop.run_until_complete(
                    ws_manager.broadcast({"event": "PRINT_FAILED"})
                )
                
                if code:
                    loop.run_until_complete(
                        notify_server_failed(code, server_job_id, "Print Timed Out")
                    )
                time.sleep(30)
                kiosk_state.set_handling_print_error(False)
                break
            
            try:
                # Check if job still exists in queue
                result = subprocess.run(
                    ["lpstat", "-o", lp_job_id],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                # Job not found = completed or cancelled
                if result.returncode != 0 or not result.stdout:
                    # Check if it was cancelled or completed
                    # If we get here after reasonable time, assume completed
                    elapsed = time.time() - start_time
                    
                    if elapsed < 0:
                        # Job disappeared too quickly - likely error
                        event_logger.error(f"Print job {lp_job_id} failed immediately")
                        #kiosk_state.set_handling_print_error(True)
                        loop.run_until_complete(
                            ws_manager.broadcast({"event": "PRINT_FAILED"})
                        )
                        if code:
                            loop.run_until_complete(
                                notify_server_failed(code, server_job_id, "Job failed immediately")
                            )
                        time.sleep(30)
                        kiosk_state.set_handling_print_error(False)
                    else:
                        result_status = subprocess.run(
                        ["lpstat", "-W", "not-completed"],
                        capture_output=True,
                        text=True,
                        timeout=5
                            )
                        if lp_job_id in result_status.stdout:
                        # Job completed 
                            event_logger.info(result_status.stdout)
                            event_logger.info(f"Print job {lp_job_id} completed")
                        else:
                            if printer_connected():
                                #event_logger.info("broadcast karro hogaya")
                                #kiosk_state.set_handling_print_error(True)
                                loop.run_until_complete(
                                ws_manager.broadcast({"event": "DONE"})
                                )
                                if code:
                                    loop.run_until_complete(
                                        notify_server_success(code, server_job_id)
                                    )
                                time.sleep(10)
                                kiosk_state.set_handling_print_error(False)
                            else:
                                event_logger.info("Cups print job completed but printer connection interuppted #bhai cups ka job huva lekin printer band hogaya")
                                #kiosk_state.set_handling_print_error(True)
                                loop.run_until_complete(
                                    ws_manager.broadcast({"event": "PRINT_FAILED"})
                                )
                                if code:
                                    loop.run_until_completed(
                                        notify_server_failed(code, server_job_id, "Cups print job completed but printer connection interuppted")
                                    )
                                time.sleep(30)
                                kiosk_state.set_handling_print_error(False)
                            break
                
                # Job still in queue - check state
                output = result.stdout.lower()
                
                if "error" in output or "aborted" in output:
                    event_logger.error(f"Print job {lp_job_id} error: {result.stdout}")
                    
                    # Cancel it
                    try:
                        subprocess.run(["cancel", lp_job_id], timeout=5)
                    except:
                        pass
                    #kiosk_state.set_handling_print_error(True)
                    loop.run_until_complete(
                        ws_manager.broadcast({"event": "PRINT_FAILED"})
                    )
                    
                    if code:
                        loop.run_until_complete(
                            notify_server_failed(code, server_job_id, "Print error")
                        )
                    time.sleep(30)
                    kiosk_state.set_handling_print_error(False)
                    break
                
            except subprocess.TimeoutExpired:
                app_logger.error(f"lpstat timeout for job {lp_job_id}")
            except Exception as e:
                app_logger.error(f"Error monitoring job {lp_job_id}: {e}")
            
            time.sleep(2)  # Check every 2 seconds
            
    except Exception as e:
        app_logger.exception(f"Fatal error monitoring job {lp_job_id}")
        kiosk_state.set_handling_print_error(True)
        loop.run_until_complete(
            ws_manager.broadcast({"event": "PRINT_FAILED"})
        )
        time.sleep(30)
        kiosk_state.set_handling_print_error(False)
    finally:
        loop.close()
        delete_temp_file(file_path)
async def notify_server_success(code: str, job_id: str):
    """Notify server of successful print"""
    import httpx
    from app.server_api import SERVER_URL, KIOSK_ID
    
    success_url = f"{SERVER_URL}/{KIOSK_ID}/job/{job_id}/status"
    payload = {
        "code": code,
        "job_id": job_id,
        "kiosk_id": KIOSK_ID,
        "status": "completed",
        "message": f"Print Job Completed"
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(success_url, json=payload)
            if resp.status_code == 200:
                event_logger.info(f"Server notified of success: {code}")
            else:
                app_logger.warning(f"Server notification failed: {resp.status_code}")
                notification_queue.add(success_url, payload)
                
    except Exception as e:
        app_logger.error(f"Failed to notify server: {e}")
        notification_queue.add(success_url, payload)

async def notify_server_failed(code: str, job_id: str, fail_message: str):
    """Notify server of failed print"""
    import httpx
    from app.server_api import SERVER_URL, KIOSK_ID
    
    fail_url = f"{SERVER_URL}/{KIOSK_ID}/job/{job_id}/status"
    payload = {
        "code": code,
        "job_id": job_id,
        "kiosk_id": KIOSK_ID,
        "status": "failed",
        "message": f"Print failed: {fail_message}"
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(fail_url, json=payload)
            
            if resp.status_code == 200:
                event_logger.info(f"Server notified of failure: {code}")
            else:
                app_logger.warning(f"Server notification failed: {resp.status_code}")
                payload 
                notification_queue.add(fail_url, payload)
                
    except Exception as e:
        app_logger.error(f"Failed to notify server: {e}")

def delete_temp_file(file_path: str):
    """Safely delete temporary PDF file"""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            event_logger.info(f"Temp file deleted: {file_path}")
        else:
            app_logger.warning(f"Temp file not found: {file_path}")
    except Exception as e:
        app_logger.error(f"Failed to delete temp file {file_path}: {e}")
