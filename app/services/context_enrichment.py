from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game, LineupSnapshot, Player, TeamParkFactor, WeatherSnapshot

DEFAULT_PARK_FACTORS = {
    "dodger-stadium": {"run_factor": 0.98, "hr_factor": 1.01, "hit_factor": 0.99, "strikeout_factor": 1.02},
    "coors-field": {"run_factor": 1.24, "hr_factor": 1.16, "hit_factor": 1.18, "strikeout_factor": 0.93},
    "yankee-stadium": {"run_factor": 1.04, "hr_factor": 1.11, "hit_factor": 1.01, "strikeout_factor": 0.98},
}


class ContextEnrichmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_default_park_factors(self) -> int:
        count = 0
        games = list((await self.db.scalars(select(Game).limit(200))))
        for game in games:
            key = game.ballpark_key or f"{game.home_team.lower()}-park"
            factors = DEFAULT_PARK_FACTORS.get(key, {"run_factor": 1.0, "hr_factor": 1.0, "hit_factor": 1.0, "strikeout_factor": 1.0})
            existing = await self.db.scalar(select(TeamParkFactor).where(TeamParkFactor.ballpark_key == key))
            row = existing or TeamParkFactor(ballpark_key=key, team=game.home_team, venue_name=game.venue_name or key)
            row.team = game.home_team
            row.venue_name = game.venue_name or key
            row.run_factor = factors["run_factor"]
            row.hr_factor = factors["hr_factor"]
            row.hit_factor = factors["hit_factor"]
            row.strikeout_factor = factors["strikeout_factor"]
            if not existing:
                self.db.add(row)
            count += 1
        await self.db.commit()
        return count

    async def refresh_weather(self) -> int:
        games = list((await self.db.scalars(select(Game).limit(200))))
        count = 0
        for game in games:
            snapshot = WeatherSnapshot(
                game_id=game.id,
                temperature_f=72.0 if game.home_team not in {"COL", "CHC"} else 61.0,
                wind_mph=7.0 if game.home_team != "CHC" else 13.0,
                wind_direction="out" if game.home_team in {"CHC", "COL"} else "cross",
                humidity_pct=38.0,
                precipitation_prob=0.08,
                roof_open=None,
                summary="simulated pregame weather",
                observed_at=datetime.utcnow(),
            )
            game.weather_summary = snapshot.summary
            self.db.add(snapshot)
            count += 1
        await self.db.commit()
        return count

    async def confirm_lineups(self) -> int:
        games = list((await self.db.scalars(select(Game).limit(50))))
        players = list((await self.db.scalars(select(Player).where(Player.position != "P").limit(300))))
        created = 0
        for game in games:
            await self.db.execute(delete(LineupSnapshot).where(LineupSnapshot.game_id == game.id))
            team_players = [p for p in players if p.team in {game.home_team, game.away_team}]
            for idx, player in enumerate(team_players[:18], start=1):
                lineup = LineupSnapshot(
                    game_id=game.id,
                    player_id=player.id,
                    team=player.team or game.home_team,
                    lineup_spot=((idx - 1) % 9) + 1,
                    confirmed=True,
                    source="demo-confirmation",
                    confirmed_at=datetime.utcnow(),
                )
                self.db.add(lineup)
                created += 1
            game.lineup_confirmed = True
        await self.db.commit()
        return created
