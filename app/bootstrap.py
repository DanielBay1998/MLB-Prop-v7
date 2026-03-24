from __future__ import annotations

import asyncio

from app.database import init_models


async def bootstrap() -> None:
    await init_models()


if __name__ == "__main__":
    asyncio.run(bootstrap())
