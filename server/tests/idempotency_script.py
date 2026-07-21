# quick script to attempt to enqueue the same payload twice with a fixed event_id
import asyncio, uuid
from datetime import datetime, timezone
from arq import create_pool
from arq.connections import RedisSettings
from app.config import settings

async def main():
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    fixed_id = str(uuid.uuid4())
    print(fixed_id)
    payload = {
        "link_id": "2b3075de-e786-49d8-9982-b942d902c004",
        "event_id": fixed_id,          # SAME id both times
        "clicked_at": datetime.now(timezone.utc).isoformat(),
        "user_agent": "test", "referrer": None, "ip": "1.2.3.4",
    }
    await pool.enqueue_job("record_click", payload)
    await pool.enqueue_job("record_click", payload)   # duplicate
    await pool.aclose()

asyncio.run(main())