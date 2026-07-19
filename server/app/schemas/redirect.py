from pydantic import BaseModel, ConfigDict, HttpUrl, Field
from datetime import datetime
import uuid

class ClickEventPayload(BaseModel):
  link_id: uuid.UUID
  clicked_at: datetime
  user_agent: str | None = Field(default=None, max_length=512) 
  referrer: str | None = Field(default=None, max_length=2048)
  ip: str | None = Field(default=None, max_length=64)
  