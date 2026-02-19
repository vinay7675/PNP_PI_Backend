import httpx
import tempfile
import os

SERVER_URL = "https://api.paynprint.com/api/kiosk" #apna url dalde idhar
KIOSK_ID= os.getenv("KIOSK_ID", "UNKNOWN")

class InvalidCode(Exception):
    pass

class UpstreamFailure(Exception):
    pass

async def fetch_print_job(code: str):
    async with httpx.AsyncClient(timeout=8) as client:
        try:
            target_url = f"{SERVER_URL}/{KIOSK_ID}/process-code"
            resp = await client.post(target_url, json={"code": code, "kiosk_id" : KIOSK_ID})
        except Exception:
            raise UpstreamFailure("SERVER_UNREACHABLE")

        if (resp.status_code == 404 or resp.status_code == 400):
            raise InvalidCode("INVALID_CODE")

        if resp.status_code != 200:
            raise UpstreamFailure("BAD_SERVER_RESPONSE")

        data = resp.json()
        file_id = data["data"]["file"]["id"]

        try:
            file_resp = await client.get(f"{SERVER_URL}/file/{file_id}")
            file_resp.raise_for_status()
        except Exception:
            raise UpstreamFailure("FILE_DOWNLOAD_FAILED")

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(file_resp.content)
        tmp.close()
        job_id = data["data"]["job"]["id"]
        job_data = data["data"]["job"]

        return {"file_path": tmp.name, "jobId2" : job_id, "colorMode": job_data["colorMode"], "duplex": job_data["duplex"], "copies" : job_data["copies"], "orientation" : ""}
