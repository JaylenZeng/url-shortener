# Day 6: Rate limiting
- 

# Day 4-5: Redis Pt 2 / ARQ
- arq is an asyncio-native distributed job queue for Python that uses Redis as its message broker and state backend            
- "Queueing decouples it: redirect enqueues a lightweight job and returns immediately. A separate worker process drains the queue and does the DB writes. Redirect stays sub-ms; analytics writes happen off to the side, can lag, can batch, can absorb bursts."
- Pieces of the puzzle:
  - Producer: Enqueues the payload for the worker to process (in the route)
  - Queue: Redis-backed via arq
  - Worker: separate process (see worker.py) and arq entry point. Consumes jobs and in this case writes to click_events
  - Table: click_events (link_id FK, clicked_at, user_agent, referrer, ip)
- Worker is a separate process so it can't use FastAPI's dependency injection. We create another engine/sessionmaker for the Worker and add it to its ctx (context) map.
- WorkerSettings include list of task functions, lifecycle hooks (on_startup/on_shutdown), and redis configuration settings.
- Don't pass rich objects (Pydantic models, ORM instances, datetimes) straight into a job queue. Serialize to plain JSON types on the producers side (via model_dump(mode="json")), enqueue the dict, then reconstruct and validate on the worker.
  - Serializer-agnostic: a dict survives any backend cleanly
  - Explicit trust boundary: revalidating on the worker means a malformed payload fails loudly at the edge
  - Type honesty: what crosses the wire is a dict; the worker's signature should say dict, then validate up to the real type.
- The queue is like a network boundary. The producer and worker are separate processes.
- You can implement idempotency by also enqueuing a stable unique id. On retry, the queue will reuse the same job + same ID which the insert can detect. In this project, I used on_conflict_do_nothing from postgres so the second unintended repeat passes without affecting anything.

# Day 3: Caching / Redis
- Redis is an in-memory key-value store. 
  - Data lives in RAM -> sub-millisecond reads (fast!).
  - Single-threaded, so commands execute atomically (atomicity means that an operation or a group of commands executes as a single, indivisible unit of work)
    - this also means no other client commands can interupt or run in the middle of it. It either completes or nothing happens meaning corrupted states are not possible.
  - Persists to disk optionally (RDB snapshots / AOF log)
  - For this project, I am using Redis as an ephemeral cache.
```
GET / SET key value — cache-aside for redirects
SET key value EX 3600 — TTL in seconds
DEL key — cache invalidation on update/delete
INCR + EXPIRE — rate limiting counters
List/stream ops — arq queue backing (handled by library)
```
- **Cache-Aside Pattern** (lazy-loading): Strategy for managing data caching to enhance system performance. 
  - When an application needs data, it first checks the cache.
    - If data is found (cache hit!), it's used directly.
    - If not found (cache miss...), application retrieves it from the main database and stores a copy in the cache for future use.
  - This pattern reduces database load, speeds up data access, and is widely used to improve the efficiency and scalability of applications by ensuring frequently accessed data is quickly available. 

- **Cache Eviction policy**: Since cache storage is limited, an eviction policy (such as Least Recently Used - LRU) is necessary to remove old or less frequently used data.
- **Data Consistency and Expiry**: Strategies must be in place to maintain data consistency between the cache and the database. This can include setting expiry times on cached data to ensure it is periodically refreshed or using cache invalidation techniques when data in the database changes.
- You should still cache negative results because if an attacker sends 10k requests/sec, they will all land on the DB. (CACHE PENETRATION).
- There is a risk of an original url being "__MISS__" or "__EXPIRED__". Since this is practically impossible, I stuck with raw sentinels. However, do note that the risk exists. I accepted the risk because the tradeoff meant doing 2 GETs and adding complexity where it wasn't needed.

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