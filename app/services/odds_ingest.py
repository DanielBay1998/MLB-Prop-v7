from __future__ import annotations

from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Game, Player, SportsbookLine

MARKETS = ["hits", "total_bases", "home_runs", "batter_strikeouts", "pitcher_strikeouts", "hits_allowed"]


class OddsIngestService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_current_player_props(self) -> dict:
        if not settings.odds_api_key:
            return {"status": "missing_api_key", "lines_upserted": 0}

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{settings.odds_api_base}/sports/baseball_mlb/odds",
                params={"apiKey": settings.odds_api_key, "regions": settings.odds_regions, "markets": ",".join(MARKETS), "oddsFormat": "american"},
            )
            resp.raise_for_status()
            payload = resp.json()

        upserts = 0
        games = list((await self.db.scalars(select(Game).limit(200))))
        players = {p.full_name.lower(): p for p in list((await self.db.scalars(select(Player).limit(500))))}
        for event in payload:
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")
            game = next((g for g in games if g.home_team.lower() in home_team.lower() or g.away_team.lower() in away_team.lower()), None)
            if not game:
                continue
            for book in event.get("bookmakers", []):
                for market in book.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        player = players.get((outcome.get("description") or outcome.get("name") or "").lower())
                        if not player:
                            continue
                        line_row = SportsbookLine(
                            game_id=game.id,
                            player_id=player.id,
                            sportsbook=book.get("title", "Sportsbook"),
                            market=market.get("key", "hits"),
                            side=(outcome.get("name") or "over").lower(),
                            line=float(outcome.get("point") or 0.5),
                            odds_american=int(outcome.get("price") or 0),
                            implied_probability=None,
                            last_seen_at=datetime.utcnow(),
                        )
                        self.db.add(line_row)
                        upserts += 1
        await self.db.commit()
        return {"status": "ok", "lines_upserted": upserts}
