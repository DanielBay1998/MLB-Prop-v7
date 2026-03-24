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
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="MLB Prop Predictor")

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
      <body style="font-family: Arial; padding: 40px;">
        <h1>App is working ✅</h1>
        <p><a href="/healthz">Health check</a></p>
        <p><a href="/docs">API docs</a></p>
      </body>
    </html>
    """

@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True})