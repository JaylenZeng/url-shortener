import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.exceptions import AliasTakenError, CodeGenerationError, LinkExpiredError, LinkNotFoundError

logger = logging.getLogger(__name__)

def register_error_handlers(app: FastAPI) -> None:
  
  @app.exception_handler(LinkExpiredError)
  async def link_not_found_handler(request: Request, exc: LinkExpiredError):
    return JSONResponse(status_code=410, content={"error": "Link not found", "status_code": 404})
  
  
  @app.exception_handler(LinkNotFoundError)
  async def link_not_found_handler(request: Request, exc: LinkNotFoundError):
    return JSONResponse(status_code=404, content={"error": "Link not found", "status_code": 404})
  
  @app.exception_handler(AliasTakenError)
  async def alias_taken_handler(request: Request, exc: AliasTakenError):
      return JSONResponse(
          status_code=409,
          content={"error": "Alias already taken", "status_code": 409},
      )

  @app.exception_handler(CodeGenerationError)
  async def code_generation_handler(request: Request, exc: CodeGenerationError):
      return JSONResponse(
          status_code=500,
          content={"error": "Could not generate unique code, try again", "status_code": 500},
      )

  @app.exception_handler(RequestValidationError)
  async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation failed", "detail": exc.errors(), "status_code": 422},
    )

  @app.exception_handler(HTTPException)
  async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )

  @app.exception_handler(Exception)
  async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandeled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500},
    )
    