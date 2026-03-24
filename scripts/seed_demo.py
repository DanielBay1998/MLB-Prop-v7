from __future__ import annotations

import asyncio
import random
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, init_models
from app.models import BattingGameLog, Game, PitchingGameLog, Player
from app.services.context_enrichment import ContextEnrichmentService
from app.services.model_training import ModelTrainer

TEAMS = ["LAD", "NYY", "ATL", "CHC", "COL", "HOU"]
PLAYERS = [
    ("Shohei Ohtani", "LAD", "L", "R", "DH"),
    ("Mookie Betts", "LAD", "R", "R", "OF"),
    ("Aaron Judge", "NYY", "R", "R", "OF"),
    ("Juan Soto", "NYY", "L", "L", "OF"),
    ("Ronald Acuna Jr.", "ATL", "R", "R", "OF"),
    ("Cody Bellinger", "CHC", "L", "L", "OF"),
    ("Kyle Tucker", "HOU", "L", "R", "OF"),
    ("Blake Snell", "LAD", "L", "L", "P"),
    ("Gerrit Cole", "NYY", "R", "R", "P"),
    ("Spencer Strider", "ATL", "R", "R", "P"),
    ("Justin Steele", "CHC", "L", "L", "P"),
    ("Framber Valdez", "HOU", "L", "L", "P"),
]


async def seed_demo_data(db: AsyncSession) -> dict:
    existing_players = await db.scalar(select(func.count(Player.id)))
    existing_games = await db.scalar(select(func.count(Game.id)))
    if (existing_players or 0) > 0 and (existing_games or 0) > 0:
        return {"seeded": False, "reason": "data already exists"}

    created_players: list[Player] = []
    for name, team, bats, throws, pos in PLAYERS:
        p = Player(full_name=name, team=team, bats=bats, throws=throws, position=pos)
        db.add(p)
        created_players.append(p)
    await db.commit()
    for p in created_players:
        await db.refresh(p)

    today = date.today()
    for offset, (home, away) in enumerate(zip(TEAMS[::2], TEAMS[1::2]), start=0):
        db.add(
            Game(
                game_date=today + timedelta(days=offset),
                home_team=home,
                away_team=away,
                probable_home_pitcher=f"{home} SP",
                probable_away_pitcher=f"{away} SP",
                venue_name=f"{home} Park",
                ballpark_key=f"{home.lower()}-park",
            )
        )
    await db.commit()

    for p in created_players:
        for i in range(90):
            game_day = today - timedelta(days=i + 1)
            if p.position == "P":
                db.add(
                    PitchingGameLog(
                        player_id=p.id,
                        game_date=game_day,
                        opponent=random.choice(TEAMS),
                        innings_pitched=round(random.uniform(4.8, 7.2), 1),
                        strikeouts=round(random.uniform(4, 11), 1),
                        hits_allowed=round(random.uniform(3, 9), 1),
                        walks_allowed=round(random.uniform(0, 4), 1),
                        earned_runs=round(random.uniform(0, 5), 1),
                        batters_faced=round(random.uniform(18, 30), 1),
                        pitches=round(random.uniform(75, 108), 1),
                    )
                )
            else:
                db.add(
                    BattingGameLog(
                        player_id=p.id,
                        game_date=game_day,
                        opponent=random.choice(TEAMS),
                        home_or_away=random.choice(["H", "A"]),
                        hits=round(random.uniform(0, 3), 1),
                        total_bases=round(random.uniform(0, 6), 1),
                        home_runs=round(random.choice([0, 0, 0, 1, 1, 2]), 1),
                        strikeouts=round(random.uniform(0, 3), 1),
                        walks=round(random.uniform(0, 2), 1),
                        plate_appearances=round(random.uniform(3, 6), 1),
                        stolen_bases=round(random.choice([0, 0, 1]), 1),
                        lineup_spot=random.randint(1, 9),
                        handedness_split=random.choice(["vsL", "vsR"]),
                    )
                )
    await db.commit()
    return {"seeded": True, "players": len(created_players)}


async def main() -> None:
    await init_models()
    async with AsyncSessionLocal() as db:
        seed_state = await seed_demo_data(db)
        context = ContextEnrichmentService(db)
        await context.upsert_default_park_factors()
        await context.refresh_weather()
        await context.confirm_lineups()
        await ModelTrainer(db).train_all()
        print({"message": "Demo data ready", **seed_state})


if __name__ == "__main__":
    asyncio.run(main())
