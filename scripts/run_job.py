from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta

from app.database import AsyncSessionLocal, init_models
from app.services.context_enrichment import ContextEnrichmentService
from app.services.model_training import ModelTrainer
from app.services.odds_ingest import OddsIngestService
from app.services.schedule_sync import ScheduleSyncService


async def main(job_name: str) -> None:
    await init_models()
    async with AsyncSessionLocal() as db:
        if job_name == "schedule-sync":
            result = await ScheduleSyncService(db).sync_range(date.today(), date.today() + timedelta(days=2))
        elif job_name == "refresh-context":
            service = ContextEnrichmentService(db)
            result = {
                "parks_updated": await service.upsert_default_park_factors(),
                "weather_snapshots": await service.refresh_weather(),
                "lineup_slots": await service.confirm_lineups(),
            }
        elif job_name == "train-models":
            result = await ModelTrainer(db).train_all()
        elif job_name == "ingest-odds":
            result = await OddsIngestService(db).ingest_current_player_props()
        else:
            raise SystemExit(f"Unknown job: {job_name}")
        print(result)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/run_job.py <schedule-sync|refresh-context|train-models|ingest-odds>")
    asyncio.run(main(sys.argv[1]))
