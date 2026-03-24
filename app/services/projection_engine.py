from __future__ import annotations

import math
from typing import Any

import joblib
import pandas as pd
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Game, ModelArtifact, Player, PropPrediction, SportsbookLine
from app.services.feature_builder import build_features


class ProjectionEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _active_model(self, market: str) -> ModelArtifact | None:
        return await self.db.scalar(
            select(ModelArtifact).where(ModelArtifact.market == market, ModelArtifact.is_active.is_(True)).order_by(desc(ModelArtifact.trained_at)).limit(1)
        )

    async def create_prediction(self, player: Player, game: Game, market: str, line: float) -> PropPrediction:
        artifact = await self._active_model(market)
        if artifact is None:
            raise ValueError(f"No trained model available for market '{market}'. Run /api/models/train first.")

        model_payload = joblib.load(artifact.artifact_path)
        feature_bundle = await build_features(self.db, player, game, market)
        expected_features = model_payload.get("features") or list(feature_bundle.values.keys())
        feature_frame = pd.DataFrame([{name: feature_bundle.values.get(name, 0.0) for name in expected_features}])
        projected_value = float(model_payload["pipeline"].predict(feature_frame)[0])
        edge_pct = ((projected_value - line) / max(abs(line), 0.5)) * 100.0
        volatility_proxy = max(abs(projected_value) * 0.18, 0.35)
        z_score = (projected_value - line) / volatility_proxy
        cover_probability = 0.5 * (1.0 + math.erf(z_score / math.sqrt(2)))
        confidence = min(99.0, max(5.0, 40 + abs(edge_pct) * 2.2 + (15 if feature_bundle.values.get("lineup_confirmed") else 0)))
        rationale = "; ".join(feature_bundle.rationale_bits)

        prediction = PropPrediction(
            player_id=player.id,
            game_id=game.id,
            market=market,
            line=line,
            projected_value=round(projected_value, 3),
            edge_pct=round(edge_pct, 2),
            confidence=round(confidence, 2),
            cover_probability=round(cover_probability, 4),
            rationale=rationale,
            feature_snapshot=feature_bundle.values,
            model_version=artifact.version,
        )
        self.db.add(prediction)
        await self.db.commit()
        await self.db.refresh(prediction)
        return prediction

    async def best_bets(self, game_date=None, limit: int = 10) -> list[dict[str, Any]]:
        stmt = (
            select(SportsbookLine)
            .options(selectinload(SportsbookLine.player), selectinload(SportsbookLine.game))
            .order_by(SportsbookLine.last_seen_at.desc())
            .limit(200)
        )
        lines = list((await self.db.scalars(stmt)))
        ranked: list[dict[str, Any]] = []
        for line in lines:
            if game_date and line.game and line.game.game_date != game_date:
                continue
            try:
                pred = await self.create_prediction(line.player, line.game, line.market, line.line)
            except Exception:
                continue
            recommended_side = "over" if pred.projected_value >= line.line else "under"
            ranked.append({
                "sportsbook": line.sportsbook,
                "player": line.player,
                "game": line.game,
                "market": line.market,
                "line": line.line,
                "recommended_side": recommended_side,
                "projected_value": pred.projected_value,
                "edge_pct": pred.edge_pct,
                "edge_abs": abs(pred.edge_pct),
                "cover_probability": pred.cover_probability,
                "confidence": pred.confidence,
                "confidence_tier": "A" if pred.confidence >= 80 else "B" if pred.confidence >= 65 else "C",
                "rationale": pred.rationale,
                "feature_snapshot": pred.feature_snapshot,
            })
        ranked.sort(key=lambda x: (x["edge_abs"], x["confidence"], x["cover_probability"]), reverse=True)
        return ranked[:limit]
