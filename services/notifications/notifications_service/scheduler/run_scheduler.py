import asyncio

from notifications_service.core.entrypoints import run_scheduler_process


if __name__ == "__main__":
    asyncio.run(run_scheduler_process())
