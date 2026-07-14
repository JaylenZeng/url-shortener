from fastapi import FastAPI
from app.routes import auth_router
from app.errors import register_error_handlers

app = FastAPI(title="URL Shortener")

register_error_handlers(app)

app.include_router(auth_router)