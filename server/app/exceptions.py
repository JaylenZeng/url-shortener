class AppError(Exception):
  """Base for domain exceptions mapped to HTTP responses."""

class AliasTakenError(AppError):
  """Custom alias collides with an existing short_code."""


class CodeGenerationError(AppError):
  """Exhausted retries generating a unique short_code."""
  
class LinkNotFoundError(AppError):
    """Link doesn't exist, or isn't owned by the requesting user."""