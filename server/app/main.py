from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

from app.db import close_arq_pool, init_arq_pool
from app.routes import auth_router, links_router, redirect_router
from app.errors import register_error_handlers

@asynccontextmanager
async def lifespan(app: FastAPI):
  await init_arq_pool() # startup
  yield
  await close_arq_pool() # shutdown
  
app = FastAPI(title="URL Shortener", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

register_error_handlers(app)

app.include_router(auth_router)
app.include_router(links_router)

# make sure to include this route last to avoid collisions (redirect route lives on root)
app.include_router(redirect_router)