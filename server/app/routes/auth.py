from fastapi import APIRouter, Depends, HTTPException
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models import User
from app.services.auth_service import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])
  
@router.post("/register", status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
  existing = await db.scalar(select(User).where(User.email == body.email))
  if existing:
    raise HTTPException(status_code=409, detail="Email already registered")
  user = User(email=body.email, password_hash=hash_password(body.password))
  db.add(user)
  await db.commit()
  return {"id": str(user.id), "email": user.email}

@router.post("/login", status_code=200)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
  user = await db.scalar(select(User).where(User.email == body.email))
  if not user or not verify_password(body.password, user.password_hash):
    raise HTTPException(status_code=401, detail="Invalid email or password")
  return TokenResponse(access_token=create_access_token(str(user.id)))
