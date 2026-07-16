
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models import Link
from app.exceptions import LinkNotFoundError
from datetime import datetime, timezone
from app.services.link_service import get_active_link_by_code

router = APIRouter(tags=["redirect"])

# Redirects person who clicked on link to original URL
@router.get("/{code}")
async def redirect_link(code: str, db: AsyncSession = Depends(get_db)):
  result = await get_active_link_by_code(db, code)
  if result is None:
    raise LinkNotFoundError()
  if result.expires_at is not None and result.expires_at < datetime.now(timezone.utc):
    raise HTTPException(
      status_code=status.HTTP_410_GONE, 
      detail="The link you requested is expired and no longer available")
  return RedirectResponse(url=result.original_url, status_code=307)