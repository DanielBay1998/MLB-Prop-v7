from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Game, LineupSnapshot, Player, PropPrediction, SportsbookLine, WeatherSnapshot
from app.services.cache import get_json, set_json
from app.services.context_enrichment import ContextEnrichmentService
from app.services.model_training import ModelTrainer
from app.services.odds_ingest import OddsIngestService
from app.services.projection_engine import ProjectionEngine
from app.services.schedule_sync import ScheduleSyncService
from jobs.tasks import ingest_odds, refresh_context, train_models, sync_schedule

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/players")
async def list_players(q: str | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Player).order_by(Player.full_name.asc()).limit(100)
    if q:
        stmt = select(Player).where(Player.full_name.ilike(f"%{q}%")).order_by(Player.full_name.asc()).limit(50)
    players = list((await db.scalars(stmt)))
    return [{"id": p.id, "name": p.full_name, "team": p.team, "position": p.position} for p in players]


@router.get("/games")
async def list_games(game_date: date | None = None, db: AsyncSession = Depends(get_db)):
    games = list((await db.scalars(select(Game).order_by(Game.game_date.desc()).limit(200))))
    out = []
    for g in games:
        if game_date and g.game_date != game_date:
            continue
        out.append({
            "id": g.id,
            "game_date": g.game_date.isoformat(),
            "away_team": g.away_team,
            "home_team": g.home_team,
            "probable_away_pitcher": g.probable_away_pitcher,
            "probable_home_pitcher": g.probable_home_pitcher,
            "venue_name": g.venue_name,
            "weather_summary": g.weather_summary,
            "lineup_confirmed": g.lineup_confirmed,
        })
    return out


@router.post("/schedule/sync")
async def sync_schedule_endpoint(start_date: date | None = Query(default=None), end_date: date | None = Query(default=None), db: AsyncSession = Depends(get_db)):
    start = start_date or date.today()
    end = end_date or (start + timedelta(days=2))
    return await ScheduleSyncService(db).sync_range(start, end)


@router.post("/jobs/schedule-sync")
async def queue_schedule_sync(start_date: date | None = Query(default=None), end_date: date | None = Query(default=None)):
    start = (start_date or date.today()).isoformat()
    end = (end_date or (date.today() + timedelta(days=2))).isoformat()
    task = sync_schedule.delay(start, end)
    return {"queued": True, "task_id": task.id, "note": "Schedule sync queued"}


@router.post("/context/refresh")
async def refresh_context_now(db: AsyncSession = Depends(get_db)):
    service = ContextEnrichmentService(db)
    return {
        "parks_updated": await service.upsert_default_park_factors(),
        "weather_snapshots": await service.refresh_weather(),
        "lineup_slots": await service.confirm_lineups(),
    }


@router.post("/sportsbook-lines/ingest")
async def ingest_sportsbook_lines(db: AsyncSession = Depends(get_db)):
    return await OddsIngestService(db).ingest_current_player_props()


@router.post("/jobs/odds-ingest")
async def queue_odds_ingest():
    task = ingest_odds.delay()
    return {"queued": True, "task_id": task.id}


@router.get("/sportsbook-lines")
async def list_sportsbook_lines(game_date: date | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(SportsbookLine).options(selectinload(SportsbookLine.game), selectinload(SportsbookLine.player)).order_by(SportsbookLine.last_seen_at.desc()).limit(200)
    rows = list((await db.scalars(stmt)))
    out = []
    for row in rows:
        if game_date and row.game.game_date != game_date:
            continue
        out.append({
            "id": row.id,
            "sportsbook": row.sportsbook,
            "player": row.player.full_name,
            "market": row.market,
            "side": row.side,
            "line": row.line,
            "odds_american": row.odds_american,
            "game_date": row.game.game_date.isoformat(),
            "matchup": f"{row.game.away_team} @ {row.game.home_team}",
            "last_seen_at": row.last_seen_at.isoformat(),
        })
    return out


@router.post("/models/train")
async def train_models_now(db: AsyncSession = Depends(get_db)):
    return await ModelTrainer(db).train_all()


@router.post("/jobs/models/train")
async def queue_model_training():
    task = train_models.delay()
    return {"queued": True, "task_id": task.id}


@router.get("/predictions")
async def list_predictions(game_date: date | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(PropPrediction).options(selectinload(PropPrediction.game), selectinload(PropPrediction.player)).order_by(PropPrediction.created_at.desc()).limit(100)
    preds = list((await db.scalars(stmt)))
    out = []
    for pred in preds:
        if game_date and pred.game.game_date != game_date:
            continue
        out.append({
            "id": pred.id,
            "player": pred.player.full_name,
            "team": pred.player.team,
            "matchup": f"{pred.game.away_team} @ {pred.game.home_team}",
            "game_date": pred.game.game_date.isoformat(),
            "market": pred.market,
            "line": pred.line,
            "projected_value": pred.projected_value,
            "edge_pct": pred.edge_pct,
            "confidence": pred.confidence,
            "cover_probability": pred.cover_probability,
            "rationale": pred.rationale,
            "feature_snapshot": pred.feature_snapshot or {},
            "model_version": pred.model_version,
        })
    return out


@router.get("/best-bets")
async def list_best_bets(game_date: date | None = None, limit: int = Query(default=10, ge=1, le=50), db: AsyncSession = Depends(get_db)):
    cache_key = f"best-bets:{game_date or 'all'}:{limit}"
    cached = await get_json(cache_key)
    if cached:
        return cached
    rows = await ProjectionEngine(db).best_bets(game_date=game_date, limit=limit)
    payload = [{
        "sportsbook": row["sportsbook"],
        "player": row["player"].full_name,
        "team": row["player"].team,
        "matchup": f"{row['game'].away_team} @ {row['game'].home_team}",
        "game_date": row["game"].game_date.isoformat(),
        "market": row["market"],
        "recommended_side": row["recommended_side"],
        "line": row["line"],
        "projected_value": row["projected_value"],
        "edge_pct": row["edge_pct"],
        "edge_abs": row["edge_abs"],
        "cover_probability": row["cover_probability"],
        "confidence": row["confidence"],
        "confidence_tier": row["confidence_tier"],
        "rationale": row["rationale"],
        "feature_snapshot": row["feature_snapshot"],
    } for row in rows]
    await set_json(cache_key, payload)
    return payload


@router.get("/lineups/{game_id}")
async def list_lineups(game_id: int, db: AsyncSession = Depends(get_db)):
    rows = list((await db.scalars(
        select(LineupSnapshot).options(selectinload(LineupSnapshot.player)).where(LineupSnapshot.game_id == game_id).order_by(LineupSnapshot.team.asc(), LineupSnapshot.lineup_spot.asc())
    )))
    return [{"team": r.team, "spot": r.lineup_spot, "player": r.player.full_name, "confirmed": r.confirmed} for r in rows]


@router.get("/weather/{game_id}")
async def latest_weather(game_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.scalar(select(WeatherSnapshot).where(WeatherSnapshot.game_id == game_id).order_by(WeatherSnapshot.observed_at.desc()).limit(1))
    if not row:
        raise HTTPException(status_code=404, detail="No weather snapshot found")
    return {
        "temperature_f": row.temperature_f,
        "wind_mph": row.wind_mph,
        "wind_direction": row.wind_direction,
        "precipitation_prob": row.precipitation_prob,
        "summary": row.summary,
        "observed_at": row.observed_at.isoformat(),
    }


@router.post("/predict")
async def create_prediction(player_id: int = Query(...), game_id: int = Query(...), market: str = Query(...), line: float = Query(...), db: AsyncSession = Depends(get_db)):
    player = await db.get(Player, player_id)
    game = await db.get(Game, game_id)
    if not player or not game:
        raise HTTPException(status_code=404, detail="Player or game not found")
    pred = await ProjectionEngine(db).create_prediction(player, game, market, line)
    return {
        "id": pred.id,
        "player": player.full_name,
        "market": pred.market,
        "line": pred.line,
        "projected_value": pred.projected_value,
        "edge_pct": pred.edge_pct,
        "confidence": pred.confidence,
        "cover_probability": pred.cover_probability,
        "rationale": pred.rationale,
        "feature_snapshot": pred.feature_snapshot or {},
        "model_version": pred.model_version,
    }
