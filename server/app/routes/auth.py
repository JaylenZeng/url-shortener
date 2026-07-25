from fastapi import APIRouter, Depends, HTTPException
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.models import User
from app.core.config import settings
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    email_domain_accepts_mail,
)

router = APIRouter(prefix="/auth", tags=["auth"])
  
@router.post("/register", status_code=201, response_model=UserResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
  existing = await db.scalar(select(User).where(User.email == body.email))
  if existing:
    raise HTTPException(status_code=409, detail="Email already registered")
  if settings.verify_email_deliverability and not await email_domain_accepts_mail(body.email):
    raise HTTPException(
      status_code=422,
      detail="That email domain can't receive mail — please check for typos",
    )
  user = User(email=body.email, password_hash=hash_password(body.password))
  db.add(user)
  try:
    await db.flush()
  except IntegrityError:
    await db.rollback()
    raise HTTPException(status_code=409, detail="Email already registered")
  return user

@router.post("/login", status_code=200)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
  user = await db.scalar(select(User).where(User.email == body.email))
  if not user or not verify_password(body.password, user.password_hash):
    raise HTTPException(status_code=401, detail="Invalid email or password")
  return TokenResponse(access_token=create_access_token(str(user.id)))
