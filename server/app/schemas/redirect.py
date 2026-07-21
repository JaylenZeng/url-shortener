from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class ClickEventPayload(BaseModel):
  link_id: uuid.UUID
  event_id: uuid.UUID
  request_id: uuid.UUID | None = None
  clicked_at: datetime
  user_agent: str | None = Field(default=None, max_length=512) 
  referrer: str | None = Field(default=None, max_length=2048)
  ip: str | None = Field(default=None, max_length=64)
  