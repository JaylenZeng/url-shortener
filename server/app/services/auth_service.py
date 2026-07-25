from datetime import datetime, timedelta, timezone
import uuid
import bcrypt
import dns.asyncresolver
import dns.resolver
import dns.exception
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.db import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
log = structlog.get_logger()


async def email_domain_accepts_mail(email: str) -> bool:
  """Return whether the email's domain can actually receive mail.

  Confirms the domain publishes an MX record (or, per RFC 5321, an A/AAAA
  record to fall back to). This catches made-up domains and typos like
  ``gmial.com`` without sending anything.

  Fails OPEN: DNS timeouts / nameserver errors return True so an infrastructure
  hiccup can't lock every new user out of registering. Only a definitive answer
  — the domain doesn't exist, or exists but publishes no mail records — is
  treated as undeliverable.
  """
  domain = email.rsplit("@", 1)[-1]
  resolver = dns.asyncresolver.Resolver()
  resolver.timeout = settings.email_verify_timeout
  resolver.lifetime = settings.email_verify_timeout

  try:
    answers = await resolver.resolve(domain, "MX")
    # A "null MX" (RFC 7505) is a single "." target meaning the domain
    # explicitly accepts no mail.
    return any(str(rec.exchange) != "." for rec in answers)
  except dns.resolver.NoAnswer:
    # No MX — RFC 5321 says fall back to an address record.
    for rdtype in ("A", "AAAA"):
      try:
        await resolver.resolve(domain, rdtype)
        return True
      except dns.resolver.NoAnswer:
        continue
      except dns.resolver.NXDOMAIN:
        return False
      except dns.exception.DNSException:
        return True  # network error → fail open
    return False
  except dns.resolver.NXDOMAIN:
    return False  # domain does not exist
  except dns.exception.DNSException as exc:
    # Timeout, no reachable nameservers, etc. — don't block the user.
    log.warning("email_deliverability_check_failed", domain=domain, error=str(exc))
    return True

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