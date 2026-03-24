from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BattingGameLog, Game, LineupSnapshot, PitchingGameLog, Player, TeamParkFactor, WeatherSnapshot


@dataclass
class FeatureBundle:
    values: dict
    rationale_bits: list[str]


def _rolling_average(values: Iterable[float]) -> float:
    items = [float(v) for v in values]
    return round(mean(items), 4) if items else 0.0


async def build_features(db: AsyncSession, player: Player, game: Game, market: str) -> FeatureBundle:
    rationale: list[str] = []
    is_pitcher_market = market in {"pitcher_strikeouts", "hits_allowed"}

    if is_pitcher_market:
        rows = list((await db.scalars(
            select(PitchingGameLog)
            .where(PitchingGameLog.player_id == player.id)
            .order_by(PitchingGameLog.game_date.desc())
            .limit(30)
        )))
        last_5_k = _rolling_average(r.strikeouts for r in rows[:5])
        last_10_k = _rolling_average(r.strikeouts for r in rows[:10])
        last_5_hits_allowed = _rolling_average(r.hits_allowed for r in rows[:5])
        workload = _rolling_average(r.batters_faced for r in rows[:10])
        rationale.append(f"Pitcher recent K form {last_5_k:.2f}/{last_10_k:.2f} over last 5/10 starts")
        base = {
            "recent_k_5": last_5_k,
            "recent_k_10": last_10_k,
            "recent_hits_allowed_5": last_5_hits_allowed,
            "recent_batters_faced_10": workload,
            "is_pitcher_market": 1.0,
        }
    else:
        rows = list((await db.scalars(
            select(BattingGameLog)
            .where(BattingGameLog.player_id == player.id)
            .order_by(BattingGameLog.game_date.desc())
            .limit(30)
        )))
        last_5_hits = _rolling_average(r.hits for r in rows[:5])
        last_10_hits = _rolling_average(r.hits for r in rows[:10])
        last_5_tb = _rolling_average(r.total_bases for r in rows[:5])
        recent_pa = _rolling_average(r.plate_appearances for r in rows[:10])
        recent_ks = _rolling_average(r.strikeouts for r in rows[:10])
        rationale.append(f"Batter recent hits form {last_5_hits:.2f}/{last_10_hits:.2f} and {recent_pa:.2f} PA")
        base = {
            "recent_hits_5": last_5_hits,
            "recent_hits_10": last_10_hits,
            "recent_total_bases_5": last_5_tb,
            "recent_plate_appearances_10": recent_pa,
            "recent_batter_ks_10": recent_ks,
            "is_pitcher_market": 0.0,
        }

    park = await db.scalar(select(TeamParkFactor).where(TeamParkFactor.ballpark_key == game.ballpark_key))
    weather = await db.scalar(
        select(WeatherSnapshot)
        .where(WeatherSnapshot.game_id == game.id)
        .order_by(WeatherSnapshot.observed_at.desc())
        .limit(1)
    )
    lineup = await db.scalar(
        select(LineupSnapshot)
        .where(LineupSnapshot.game_id == game.id, LineupSnapshot.player_id == player.id)
        .limit(1)
    )

    ballpark_factor = park.hit_factor if park else 1.0
    hr_factor = park.hr_factor if park else 1.0
    k_factor = park.strikeout_factor if park else 1.0
    weather_temp = weather.temperature_f if weather and weather.temperature_f is not None else 72.0
    wind_mph = weather.wind_mph if weather and weather.wind_mph is not None else 6.0
    precip = weather.precipitation_prob if weather and weather.precipitation_prob is not None else 0.0
    lineup_spot = float(lineup.lineup_spot) if lineup else 6.0
    lineup_confirmed = 1.0 if lineup and lineup.confirmed else 0.0

    if park:
        rationale.append(f"Park factors H {park.hit_factor:.2f}, HR {park.hr_factor:.2f}, K {park.strikeout_factor:.2f}")
    if weather:
        rationale.append(f"Weather {weather.summary or 'snapshot'} temp {weather_temp:.0f}F wind {wind_mph:.0f} mph")
    if lineup:
        rationale.append(f"Lineup spot {lineup.lineup_spot} ({'confirmed' if lineup.confirmed else 'projected'})")

    base.update({
        "park_hit_factor": ballpark_factor,
        "park_hr_factor": hr_factor,
        "park_k_factor": k_factor,
        "temperature_f": weather_temp,
        "wind_mph": wind_mph,
        "precipitation_prob": precip,
        "lineup_spot": lineup_spot,
        "lineup_confirmed": lineup_confirmed,
        "is_home": 1.0 if player.team == game.home_team else 0.0,
        "player_bats_L": 1.0 if player.bats == "L" else 0.0,
        "player_throws_R": 1.0 if player.throws == "R" else 0.0,
    })
    return FeatureBundle(values=base, rationale_bits=rationale)
