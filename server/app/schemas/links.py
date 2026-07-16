from pydantic import BaseModel, ConfigDict, HttpUrl, Field
from datetime import datetime
import uuid

class CreateLinkRequest(BaseModel):
  original_url: HttpUrl
  custom_alias: str | None = Field(
    default=None, min_length=3, max_length=16, pattern=r"^[a-zA-Z0-9_-]+$"
  )
  expires_at: datetime | None = None

class LinkResponse(BaseModel):
  model_config = ConfigDict(from_attributes=True)
  
  id: uuid.UUID
  short_code: str
  original_url: str
  created_at: datetime
  expires_at: datetime | None