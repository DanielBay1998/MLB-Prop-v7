from __future__ import annotations

import asyncio

from datetime import date

from jobs.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.services.context_enrichment import ContextEnrichmentService
from app.services.model_training import ModelTrainer
from app.services.odds_ingest import OddsIngestService
from app.services.schedule_sync import ScheduleSyncService


@celery_app.task(name="jobs.sync_schedule")
def sync_schedule(start_date: str, end_date: str) -> dict:
    async def _run() -> dict:
        async with AsyncSessionLocal() as db:
            return await ScheduleSyncService(db).sync_range(date.fromisoformat(start_date), date.fromisoformat(end_date))
    return asyncio.run(_run())


@celery_app.task(name="jobs.refresh_context")
def refresh_context() -> dict:
    async def _run() -> dict:
        async with AsyncSessionLocal() as db:
            service = ContextEnrichmentService(db)
            parks = await service.upsert_default_park_factors()
            weather = await service.refresh_weather()
            lineups = await service.confirm_lineups()
            return {"parks": parks, "weather": weather, "lineups": lineups}
    return asyncio.run(_run())


@celery_app.task(name="jobs.ingest_odds")
def ingest_odds() -> dict:
    async def _run() -> dict:
        async with AsyncSessionLocal() as db:
            return await OddsIngestService(db).ingest_current_player_props()
    return asyncio.run(_run())


@celery_app.task(name="jobs.train_models")
def train_models() -> list[dict]:
    async def _run() -> list[dict]:
        async with AsyncSessionLocal() as db:
            return await ModelTrainer(db).train_all()
    return asyncio.run(_run())
