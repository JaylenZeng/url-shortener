from pydantic import BaseModel, ConfigDict, HttpUrl, Field
from datetime import date, datetime
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
  click_count: int = 0

class DailyClicks(BaseModel):
  date: date
  clicks: int

class ReferrerCount(BaseModel):
  # None represents clicks with no referrer header (e.g. direct visits).
  referrer: str | None
  clicks: int

class UserAgentCount(BaseModel):
  user_agent: str | None
  clicks: int

class LinkStatsResponse(BaseModel):
  link_id: uuid.UUID
  short_code: str
  total_clicks: int
  clicks_by_day: list[DailyClicks]
  top_referrers: list[ReferrerCount]
  top_user_agents: list[UserAgentCount]