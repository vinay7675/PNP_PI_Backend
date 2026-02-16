import subprocess
import urllib.request
from app.logger import health_logger

# Known printer USB vendor IDs (hex)
PRINTER_USB_VENDORS = {
    "03f0",  # HP
    "04a9",  # Canon
    "04f9",  # Brother
}

def internet_ok(timeout=3) -> bool:
    try:
        urllib.request.urlopen("https://www.google.com", timeout)
        return True
    except Exception:
        health_logger.exception("Internet connection interupted")
        return False


def printer_connected() -> bool:
    try:
        result = subprocess.check_output(["/usr/bin/lsusb"], text=True)
        for line in result.splitlines():
            for vendor_id in PRINTER_USB_VENDORS:
                if f"ID {vendor_id}:" in line:
                    return True
        return False
    except Exception:
        health_logger.exception("Printer status not retrieved. Error occured while runing 'lsusb'")
        return False


def system_healthy() -> bool:
    return internet_ok() and printer_connected()
