from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.routes import router as api_router
from app.config import settings
from app.database import get_db, init_models
from app.models import Game, Player, PropPrediction, SportsbookLine
from app.services.model_training import ModelTrainer
from app.services.projection_engine import ProjectionEngine

app = FastAPI(title=settings.app_name)
app.include_router(api_router)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
async def startup_event() -> None:
    await init_models()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    predictions = list((await db.scalars(select(PropPrediction).options(selectinload(PropPrediction.player), selectinload(PropPrediction.game)).order_by(PropPrediction.created_at.desc()).limit(25))))
    players = list((await db.scalars(select(Player).order_by(Player.full_name.asc()).limit(150))))
    games = list((await db.scalars(select(Game).order_by(Game.game_date.desc(), Game.id.desc()).limit(75))))
    lines = list((await db.scalars(select(SportsbookLine).options(selectinload(SportsbookLine.player), selectinload(SportsbookLine.game)).order_by(SportsbookLine.last_seen_at.desc()).limit(20))))
    today = date.today()
    best_bets = []
    try:
        best_bets = await ProjectionEngine(db).best_bets(today, limit=12)
    except Exception:
        best_bets = []
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "predictions": predictions,
            "players": players,
            "games": games,
            "sportsbook_lines": lines,
            "best_bets": best_bets,
            "markets": [
                ("hits", "Hits"),
                ("total_bases", "Total Bases"),
                ("home_runs", "Home Runs"),
                ("batter_strikeouts", "Batter Strikeouts"),
                ("pitcher_strikeouts", "Pitcher Strikeouts"),
                ("hits_allowed", "Pitcher Hits Allowed"),
            ],
            "today": today.isoformat(),
            "default_end": (today + timedelta(days=2)).isoformat(),
        },
    )


@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True, "app": settings.app_name})


@app.post("/predict/form", response_class=HTMLResponse)
async def predict_form(request: Request, player_id: int = Form(...), game_id: int = Form(...), market: str = Form(...), line: float = Form(...), db: AsyncSession = Depends(get_db)):
    player = await db.get(Player, player_id)
    game = await db.get(Game, game_id)
    pred = await ProjectionEngine(db).create_prediction(player, game, market, line)
    return templates.TemplateResponse("partials/prediction_card.html", {"request": request, "prediction": pred})
