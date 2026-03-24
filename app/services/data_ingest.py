from __future__ import annotations

from datetime import date, timedelta
import pandas as pd
from sqlalchemy.orm import Session

from pybaseball import batting_stats_range, pitching_stats_range

from app.models import Player, BattingGameLog, PitchingGameLog


class HistoricalDataIngestor:
    def __init__(self, db: Session):
        self.db = db

    def ingest_recent_summary_window(self, start_date: date, end_date: date) -> dict:
        batting = batting_stats_range(start_date.isoformat(), end_date.isoformat())
        pitching = pitching_stats_range(start_date.isoformat(), end_date.isoformat())
        batting_count = self._store_batting_summary(batting)
        pitching_count = self._store_pitching_summary(pitching)
        self.db.commit()
        return {"batters_loaded": batting_count, "pitchers_loaded": pitching_count}

    def _get_or_create_player(self, full_name: str, team: str | None = None) -> Player:
        player = self.db.query(Player).filter(Player.full_name == full_name).first()
        if player:
            if team and not player.team:
                player.team = team
            return player
        player = Player(full_name=full_name, team=team)
        self.db.add(player)
        self.db.flush()
        return player

    def _store_batting_summary(self, df: pd.DataFrame) -> int:
        count = 0
        for _, row in df.head(250).iterrows():
            player = self._get_or_create_player(row.get("Name", "Unknown"), row.get("Team"))
            self.db.add(BattingGameLog(
                player_id=player.id,
                game_date=date.today(),
                opponent="TBD",
                hits=float(row.get("H", 0) or 0),
                total_bases=float(row.get("TB", 0) or 0),
                home_runs=float(row.get("HR", 0) or 0),
                strikeouts=float(row.get("SO", 0) or 0),
                walks=float(row.get("BB", 0) or 0),
                plate_appearances=float(row.get("PA", 0) or 0),
            ))
            count += 1
        return count

    def _store_pitching_summary(self, df: pd.DataFrame) -> int:
        count = 0
        for _, row in df.head(200).iterrows():
            player = self._get_or_create_player(row.get("Name", "Unknown"), row.get("Team"))
            self.db.add(PitchingGameLog(
                player_id=player.id,
                game_date=date.today(),
                opponent="TBD",
                innings_pitched=float(row.get("IP", 0) or 0),
                strikeouts=float(row.get("SO", 0) or 0),
                hits_allowed=float(row.get("H", 0) or 0),
                walks_allowed=float(row.get("BB", 0) or 0),
                earned_runs=float(row.get("ER", 0) or 0),
                batters_faced=float(row.get("BF", 0) or 0),
            ))
            count += 1
        return count


def default_ingest_window() -> tuple[date, date]:
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    return start_date, end_date
