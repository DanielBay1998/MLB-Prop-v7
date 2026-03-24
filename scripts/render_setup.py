from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta

from sqlalchemy import func, select

from app.database import AsyncSessionLocal, init_models
from app.models import Game, ModelArtifact, Player
from app.services.context_enrichment import ContextEnrichmentService
from app.services.model_training import ModelTrainer
from app.services.odds_ingest import OddsIngestService
from app.services.schedule_sync import ScheduleSyncService
from scripts.seed_demo import seed_demo_data


def truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


async def main() -> None:
    await init_models()
    async with AsyncSessionLocal() as db:
        player_count = int((await db.scalar(select(func.count(Player.id)))) or 0)
        game_count = int((await db.scalar(select(func.count(Game.id)))) or 0)

        if truthy(os.getenv("SEED_DEMO_DATA"), True) and player_count == 0 and game_count == 0:
            print(await seed_demo_data(db))

        if truthy(os.getenv("SYNC_SCHEDULE_ON_BOOT"), False):
            try:
                print(await ScheduleSyncService(db).sync_range(date.today(), date.today() + timedelta(days=2)))
            except Exception as exc:
                print({"schedule_sync": "skipped", "reason": str(exc)})

        context = ContextEnrichmentService(db)
        try:
            print({
                "parks_updated": await context.upsert_default_park_factors(),
                "weather_snapshots": await context.refresh_weather(),
                "lineup_slots": await context.confirm_lineups(),
            })
        except Exception as exc:
            print({"context_refresh": "skipped", "reason": str(exc)})

        active_models = int((await db.scalar(select(func.count(ModelArtifact.id)).where(ModelArtifact.is_active.is_(True)))) or 0)
        if truthy(os.getenv("TRAIN_MODELS_ON_BOOT"), True) and active_models == 0:
            try:
                print(await ModelTrainer(db).train_all())
            except Exception as exc:
                print({"model_training": "skipped", "reason": str(exc)})

        if truthy(os.getenv("INGEST_ODDS_ON_BOOT"), False):
            try:
                print(await OddsIngestService(db).ingest_current_player_props())
            except Exception as exc:
                print({"odds_ingest": "skipped", "reason": str(exc)})


if __name__ == "__main__":
    asyncio.run(main())
