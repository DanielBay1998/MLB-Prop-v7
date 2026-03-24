from __future__ import annotations

from datetime import date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Game


class ScheduleSyncService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_range(self, start: date, end: date) -> dict:
        params = {"sportId": 1, "startDate": start.isoformat(), "endDate": end.isoformat(), "hydrate": "probablePitcher,venue"}
        games_upserted = 0
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{settings.mlb_stats_api_base}/schedule", params=params)
            response.raise_for_status()
            payload = response.json()
        for day in payload.get("dates", []):
            for item in day.get("games", []):
                existing = await self.db.scalar(select(Game).where(Game.external_game_id == str(item.get("gamePk"))))
                teams = item.get("teams", {})
                away = teams.get("away", {})
                home = teams.get("home", {})
                row = existing or Game(external_game_id=str(item.get("gamePk")))
                row.game_date = date.fromisoformat(day["date"])
                row.start_time_utc = datetime.fromisoformat(item["gameDate"].replace("Z", "+00:00")) if item.get("gameDate") else None
                row.away_team = away.get("team", {}).get("abbreviation") or away.get("team", {}).get("name", "AWY")[:3].upper()
                row.home_team = home.get("team", {}).get("abbreviation") or home.get("team", {}).get("name", "HME")[:3].upper()
                row.probable_away_pitcher = away.get("probablePitcher", {}).get("fullName")
                row.probable_home_pitcher = home.get("probablePitcher", {}).get("fullName")
                venue = item.get("venue", {})
                row.venue_name = venue.get("name")
                row.venue_id = venue.get("id")
                row.ballpark_key = (venue.get("name") or row.home_team or "park").lower().replace(" ", "-")
                if not existing:
                    self.db.add(row)
                games_upserted += 1
        await self.db.commit()
        return {"status": "ok", "games_upserted": games_upserted, "start_date": start.isoformat(), "end_date": end.isoformat()}
