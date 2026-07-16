from datetime import datetime, timedelta, timezone
import uuid
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(password: str) -> str:
  return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
  return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(user_id: str) -> str:
  expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
  return jwt.encode(
    {"sub": user_id, "exp": expire},
    settings.jwt_secret,
    algorithm=settings.jwt_algorithm
  )

async def get_current_user(
  token: str = Depends(oauth2_scheme),
  db: AsyncSession = Depends(get_db)
) -> User:
  credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, 
    detail="Invalid credentials",
    headers={"WWW-Authenticate": "Bearer"}
  )
  try:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = payload.get("sub")
    if user_id is None:
      raise credentials_exception
    user_uuid = uuid.UUID(user_id)
  except (JWTError, ValueError):
    raise credentials_exception
  
  user = await db.get(User, user_uuid)
  if user is None:
    raise credentials_exception
  return user