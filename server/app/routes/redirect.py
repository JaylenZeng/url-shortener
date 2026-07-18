
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db, get_redis
from app.services.redirect_service import get_original

router = APIRouter(tags=["redirect"])

# Redirects person who clicked on link to original URL
@router.get("/{code}")
async def redirect_link(code: str, r: Redis = Depends(get_redis), db: AsyncSession = Depends(get_db)):
  original_url = await get_original(code, r, db)
  return RedirectResponse(url=original_url, status_code=307)

