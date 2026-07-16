# Day 2: Routing 
- Make sure to handle all possible errors. For example, an IntegrityError can be a null violation, FK violation, or anything hitting a constraint. A precise version inspects the constraint name on the error: `constraint = getattr(getattr(e.orig, "__cause__", None), "constraint_name", None)`
- Be careful when committing within a service. For a Transaction that requires multiple writes, you wil encounter problems. If you commit in create_link, but want to log an audit row, you won't be able to roll back both together in the event that something goes wrong
  - Therefore, services does db.flush(), then we delegate commits to the dependency: get_db()
  - Both the service and get_db() have to do db.rollback() because they cover different cases
    - service rolls back to recover and continue (retry)
    - get_db rolls back to abort the request (unhandled failure) 
- FastAPI's response_model filters the amount of fields the client can receive from the ORM object.
  - In FastAPI, the output is "whatever the schema declares". We need to control leaks by controlling the schema
  - Get into the habit of defining Response Schema
- **Don't put too much trust into Alembic auto-complete:** Ran into a bug where I updated a migration to replace a partial unique index, but auto-complete didn't recognize it and my routes weren't catching the correct error. Make sure to always double check and understand exactly the updates Alembic is making to the database.
- Comparing index vs no index on short_code lookup:
```                                                     QUERY PLAN                                                     
--------------------------------------------------------------------------------------------------------------------
 Gather  (cost=1000.00..21024.43 rows=1 width=94) (actual time=0.136..23.826 rows=1 loops=1)
   Workers Planned: 2
   Workers Launched: 2
   ->  Parallel Seq Scan on links  (cost=0.00..20024.33 rows=1 width=94) (actual time=7.091..14.045 rows=0 loops=3)
         Filter: ((short_code)::text = 'seed0100001'::text)
         Rows Removed by Filter: 333333
 Planning Time: 0.042 ms
 Execution Time: 23.840 ms
                                                             QUERY PLAN                                                             
-----------------------------------------------------------------------------------------------------------------------------------
 Index Scan using ix_links_short_code_active on links  (cost=0.42..8.44 rows=1 width=94) (actual time=0.017..0.017 rows=1 loops=1)
   Index Cond: ((short_code)::text = 'seed0100001'::text)
 Planning Time: 0.052 ms
 Execution Time: 0.027 ms
(4 rows)
 ```

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