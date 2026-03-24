from __future__ import annotations

import asyncio

from sqlalchemy import select, func

from app.database import AsyncSessionLocal, init_models
from app.models import Player


async def main() -> None:
    # Create tables first
    await init_models()

    # Optional demo seed check
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count(Player.id)))
        player_count = result.scalar_one()

        if player_count == 0:
            print("No players found yet. Skipping seed-dependent setup.")
        else:
            print(f"Players already exist: {player_count}")

    print("Render setup complete.")


if __name__ == "__main__":
    asyncio.run(main())