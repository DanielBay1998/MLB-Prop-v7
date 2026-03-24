from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="MLB Prop Predictor")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "predictions": [],
            "players": [],
            "games": [],
            "sportsbook_lines": [],
            "best_bets": [],
            "markets": [
                ("hits", "Hits"),
                ("total_bases", "Total Bases"),
                ("home_runs", "Home Runs"),
                ("batter_strikeouts", "Batter Strikeouts"),
                ("pitcher_strikeouts", "Pitcher Strikeouts"),
                ("hits_allowed", "Pitcher Hits Allowed"),
            ],
            "today": "",
            "default_end": "",
        },
    )

@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True})