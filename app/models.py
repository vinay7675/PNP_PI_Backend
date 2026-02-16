from pydantic import BaseModel

class PrintRequest(BaseModel):
    code: str
