from jose import jwt, JWTError
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

def user_or_ip_key(request: Request) -> str:
  auth = request.headers.get("authorization", "")
  if auth.startswith("Bearer "):
    token = auth.removeprefix("Bearer ")
    try:
      payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
      sub = payload.get("sub")
      if sub:
        return f"user:{sub}"
    except JWTError:
      pass
  return f"ip:{get_remote_address(request)}"
  
  
limiter = Limiter(
  key_func=get_remote_address, # default: per IP
  storage_uri=settings.redis_url # shared counter
)