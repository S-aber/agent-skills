from pydantic import BaseModel
from datetime import datetime


class UploadedFileInfo(BaseModel):
    filename: str
    path: str
    size: int
    uploaded_at: datetime
