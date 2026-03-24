from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import BattingGameLog, ModelArtifact, PitchingGameLog, Player

MARKET_TARGETS = {
    "hits": ("batting", "hits"),
    "total_bases": ("batting", "total_bases"),
    "home_runs": ("batting", "home_runs"),
    "batter_strikeouts": ("batting", "strikeouts"),
    "pitcher_strikeouts": ("pitching", "strikeouts"),
    "hits_allowed": ("pitching", "hits_allowed"),
}

NUMERIC_FEATURES = [
    "recent_hits_5",
    "recent_hits_10",
    "recent_total_bases_5",
    "recent_plate_appearances_10",
    "recent_batter_ks_10",
    "recent_k_5",
    "recent_k_10",
    "recent_hits_allowed_5",
    "recent_batters_faced_10",
    "park_hit_factor",
    "park_hr_factor",
    "park_k_factor",
    "temperature_f",
    "wind_mph",
    "precipitation_prob",
    "lineup_spot",
    "lineup_confirmed",
    "is_home",
    "player_bats_L",
    "player_throws_R",
    "is_pitcher_market",
]


def _avg(values: list[float]) -> float:
    return round(float(mean(values)), 4) if values else 0.0


class ModelTrainer:
    def __init__(self, db: AsyncSession):
        self.db = db
        Path(settings.model_dir).mkdir(parents=True, exist_ok=True)

    async def _players_map(self) -> dict[int, Player]:
        players = list((await self.db.scalars(select(Player))))
        return {p.id: p for p in players}

    async def _load_training_frame(self, market: str) -> pd.DataFrame:
        kind, target = MARKET_TARGETS[market]
        players = await self._players_map()
        raw: list[dict] = []

        if kind == "batting":
            rows = list((await self.db.scalars(select(BattingGameLog).order_by(BattingGameLog.player_id.asc(), BattingGameLog.game_date.asc()))))
            history: dict[int, list[BattingGameLog]] = defaultdict(list)
            for r in rows:
                player = players.get(r.player_id)
                prev = history[r.player_id]
                feature_row = {
                    "target": getattr(r, target),
                    "recent_hits_5": _avg([x.hits for x in prev[-5:]]),
                    "recent_hits_10": _avg([x.hits for x in prev[-10:]]),
                    "recent_total_bases_5": _avg([x.total_bases for x in prev[-5:]]),
                    "recent_plate_appearances_10": _avg([x.plate_appearances for x in prev[-10:]]),
                    "recent_batter_ks_10": _avg([x.strikeouts for x in prev[-10:]]),
                    "recent_k_5": 0.0,
                    "recent_k_10": 0.0,
                    "recent_hits_allowed_5": 0.0,
                    "recent_batters_faced_10": 0.0,
                    "park_hit_factor": 1.0,
                    "park_hr_factor": 1.0,
                    "park_k_factor": 1.0,
                    "temperature_f": 72.0,
                    "wind_mph": 6.0,
                    "precipitation_prob": 0.05,
                    "lineup_spot": float(r.lineup_spot or 6),
                    "lineup_confirmed": 1.0,
                    "is_home": 1.0 if (r.home_or_away or "H") == "H" else 0.0,
                    "player_bats_L": 1.0 if player and player.bats == "L" else 0.0,
                    "player_throws_R": 1.0 if player and player.throws == "R" else 0.0,
                    "is_pitcher_market": 0.0,
                }
                raw.append(feature_row)
                prev.append(r)
        else:
            rows = list((await self.db.scalars(select(PitchingGameLog).order_by(PitchingGameLog.player_id.asc(), PitchingGameLog.game_date.asc()))))
            history: dict[int, list[PitchingGameLog]] = defaultdict(list)
            for r in rows:
                player = players.get(r.player_id)
                prev = history[r.player_id]
                feature_row = {
                    "target": getattr(r, target),
                    "recent_hits_5": 0.0,
                    "recent_hits_10": 0.0,
                    "recent_total_bases_5": 0.0,
                    "recent_plate_appearances_10": 0.0,
                    "recent_batter_ks_10": 0.0,
                    "recent_k_5": _avg([x.strikeouts for x in prev[-5:]]),
                    "recent_k_10": _avg([x.strikeouts for x in prev[-10:]]),
                    "recent_hits_allowed_5": _avg([x.hits_allowed for x in prev[-5:]]),
                    "recent_batters_faced_10": _avg([x.batters_faced for x in prev[-10:]]),
                    "park_hit_factor": 1.0,
                    "park_hr_factor": 1.0,
                    "park_k_factor": 1.0,
                    "temperature_f": 72.0,
                    "wind_mph": 6.0,
                    "precipitation_prob": 0.05,
                    "lineup_spot": 0.0,
                    "lineup_confirmed": 0.0,
                    "is_home": 1.0,
                    "player_bats_L": 0.0,
                    "player_throws_R": 1.0 if player and player.throws == "R" else 0.0,
                    "is_pitcher_market": 1.0,
                }
                raw.append(feature_row)
                prev.append(r)

        return pd.DataFrame(raw)

    async def train_market(self, market: str) -> dict:
        frame = await self._load_training_frame(market)
        if frame.empty:
            raise ValueError(f"No training data available for market {market}")

        y = frame.pop("target")
        X = frame[NUMERIC_FEATURES].copy()
        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", HistGradientBoostingRegressor(max_depth=5, learning_rate=0.05, max_iter=250, random_state=42)),
        ])
        pipeline.fit(X, y)
        preds = pipeline.predict(X)
        metrics = {
            "mae": float(mean_absolute_error(y, preds)),
            "rmse": float(root_mean_squared_error(y, preds)),
            "rows": int(len(X)),
            "features": NUMERIC_FEATURES,
        }
        version = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        artifact_path = str(Path(settings.model_dir) / f"{market}-{version}.joblib")
        joblib.dump({"pipeline": pipeline, "market": market, "version": version, "features": NUMERIC_FEATURES}, artifact_path)

        await self.db.execute(update(ModelArtifact).where(ModelArtifact.market == market).values(is_active=False))
        artifact = ModelArtifact(market=market, version=version, artifact_path=artifact_path, metrics=metrics, is_active=True)
        self.db.add(artifact)
        await self.db.commit()
        return {"market": market, "version": version, "artifact_path": artifact_path, "metrics": metrics}

    async def train_all(self) -> list[dict]:
        results = []
        for market in MARKET_TARGETS:
            results.append(await self.train_market(market))
        return results
