from datetime import date, datetime
from pydantic import BaseModel


class PropPredictionOut(BaseModel):
    id: int
    player_name: str
    team: str | None
    game_date: date
    matchup: str
    market: str
    line: float
    projected_value: float
    edge_pct: float
    confidence: float
    rationale: str
    created_at: datetime

    model_config = {"from_attributes": True}
