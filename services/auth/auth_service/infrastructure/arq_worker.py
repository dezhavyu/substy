from arq.connections import RedisSettings


async def noop_task(ctx, payload: dict) -> dict:  # type: ignore[no-untyped-def]
    return {"status": "ok", "payload": payload}


class WorkerSettings:
    functions = [noop_task]
    redis_settings = RedisSettings(host="redis", port=6379)
