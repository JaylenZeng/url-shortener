# Day 1: Project Setup
- Initialized project with UV, alembic
- Setup docker containers for Postgres and Redis
- Learned about the functionalty of different Python libraries for web development
  - sqlalchemy: orm/query toolkit. Allows you to define Python classes as DB tables and writes queries in Python
  - alembic: migration tool that pairs with sqlalchemy. Tracks schema changes as versioned scripts
  - pydantic-settings: loads config (.env) into typed Python objects
  - fastapi: web framework that handles routing, request/response validation, and auto0generates /docs
  - uvicorn: ASGI server. This is what actually runs the FastAPI app and listens for requests
- Learned how to use sqlalchemy to define DB tables
  - optional "relationship()" function that doesn't create a column, but allows us to navigate between objects in Python without writing manual queries. If we want the owning user of a link, we can just get that by asking SQLalchemy to fetch it for us.
  - Mapped[x]: maps Python type to SQL type
  - mapped_column: function that actually makes the column
- Learned basic routing and syntax in FastAPI
- Learned how to communicate with Postgres through SQLAlchemy.ext.asyncio
  - SessionMaker is the factory that churns out AsyncSessions for our routes to use
- "Depends" keyword is FastAPI's dependency injection marker. It tells FastAPI to wait for a function to be ran before running a route
- How to use alembic:
```
# 1. Edit models.py (add a column, new table, etc.)

# 2. Generate a migration — alembic diffs your models against current DB state
uv run alembic revision --autogenerate -m "add expires_at to links"

# 3. Review the generated file in alembic/versions/ — autogenerate isn't perfect,
#    especially with renamed columns, index changes, or type migrations

# 4. Apply it
uv run alembic upgrade head

# Other useful commands
uv run alembic current        # what migration is the DB currently at
uv run alembic history        # list all migrations
uv run alembic downgrade -1   # roll back one migration (undo)
```