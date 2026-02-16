import subprocess
import socket
import urllib.request

PRINTER_USB_VENDORS = {
    "03f0",  # HP
    "04a9",  # Canon
    "04f9"  # Brother
}


def check_internet():
    try:
        urllib.request.urlopen("https://www.google.com", timeout=3)
        return True
    except Exception:
        return False


def check_backend():
    try:
        socket.create_connection(("127.0.0.1", 8000), timeout=2)
        return True
    except Exception:
        return False


def check_frontend():
    try:
        socket.create_connection(("127.0.0.1", 5173), timeout=2)
        return True
    except Exception:
        return False


def check_printer():
    try:
        result = subprocess.check_output(["/usr/bin/lsusb"], text=True)
        for line in result.splitlines():
            for vendor_id in PRINTER_USB_VENDORS:
                if f"ID {vendor_id}:" in line:
                    return True
        return False
    except Exception:
        return False
    '''try:
        result1 = subprocess.check_output(
            ["/usr/bin/lpstat", "-p"],
            #stdout=subprocess.PIPE,
            #stderr=subprocess.DEVNULL,
            timeout=4,
            text=True
        )
        #return out #or "enabled" in out"""
        return "HpQueue" in result1
    except Exception:
        print("exception")
        return False'''


def run_diagnostics():
    return {
        "internet": check_internet(),
        "backend": check_backend(),
        "frontend": check_frontend(),
        "printer": check_printer(),
    }
