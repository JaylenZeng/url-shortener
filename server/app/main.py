from fastapi import FastAPI
from app.routes import auth_router, links_router, redirect_router
from app.errors import register_error_handlers

app = FastAPI(title="URL Shortener")

register_error_handlers(app)

app.include_router(auth_router)
app.include_router(links_router)

# make sure to include this route last to avoid collisions (redirect route lives on root)
app.include_router(redirect_router)