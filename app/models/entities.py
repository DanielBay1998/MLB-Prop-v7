from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mlb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    team: Mapped[Optional[str]] = mapped_column(String(10), index=True)
    bats: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    throws: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    batting_logs: Mapped[list["BattingGameLog"]] = relationship(back_populates="player", cascade="all, delete-orphan")
    pitching_logs: Mapped[list["PitchingGameLog"]] = relationship(back_populates="player", cascade="all, delete-orphan")
    lineup_slots: Mapped[list["LineupSnapshot"]] = relationship(back_populates="player")
    predictions: Mapped[list["PropPrediction"]] = relationship(back_populates="player")
    sportsbook_lines: Mapped[list["SportsbookLine"]] = relationship(back_populates="player")


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (UniqueConstraint("game_date", "home_team", "away_team", name="uq_game_date_matchup"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_game_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, unique=True)
    game_date: Mapped[date] = mapped_column(Date, index=True)
    start_time_utc: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    home_team: Mapped[str] = mapped_column(String(10), index=True)
    away_team: Mapped[str] = mapped_column(String(10), index=True)
    probable_home_pitcher: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    probable_away_pitcher: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    venue_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    venue_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ballpark_key: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    weather_summary: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    lineup_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    lineup_snapshots: Mapped[list["LineupSnapshot"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    weather_snapshots: Mapped[list["WeatherSnapshot"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    predictions: Mapped[list["PropPrediction"]] = relationship(back_populates="game")
    sportsbook_lines: Mapped[list["SportsbookLine"]] = relationship(back_populates="game")


class BattingGameLog(Base):
    __tablename__ = "batting_game_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    game_date: Mapped[date] = mapped_column(Date, index=True)
    opponent: Mapped[str] = mapped_column(String(10))
    home_or_away: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    hits: Mapped[float] = mapped_column(Float, default=0)
    total_bases: Mapped[float] = mapped_column(Float, default=0)
    home_runs: Mapped[float] = mapped_column(Float, default=0)
    strikeouts: Mapped[float] = mapped_column(Float, default=0)
    walks: Mapped[float] = mapped_column(Float, default=0)
    plate_appearances: Mapped[float] = mapped_column(Float, default=0)
    stolen_bases: Mapped[float] = mapped_column(Float, default=0)
    lineup_spot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    handedness_split: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)

    player: Mapped[Player] = relationship(back_populates="batting_logs")


class PitchingGameLog(Base):
    __tablename__ = "pitching_game_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    game_date: Mapped[date] = mapped_column(Date, index=True)
    opponent: Mapped[str] = mapped_column(String(10))
    innings_pitched: Mapped[float] = mapped_column(Float, default=0)
    strikeouts: Mapped[float] = mapped_column(Float, default=0)
    hits_allowed: Mapped[float] = mapped_column(Float, default=0)
    walks_allowed: Mapped[float] = mapped_column(Float, default=0)
    earned_runs: Mapped[float] = mapped_column(Float, default=0)
    batters_faced: Mapped[float] = mapped_column(Float, default=0)
    pitches: Mapped[float] = mapped_column(Float, default=0)

    player: Mapped[Player] = relationship(back_populates="pitching_logs")


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"
    __table_args__ = (UniqueConstraint("game_id", "observed_at", name="uq_game_weather_observed"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    temperature_f: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_mph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    humidity_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precipitation_prob: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roof_open: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    game: Mapped[Game] = relationship(back_populates="weather_snapshots")


class TeamParkFactor(Base):
    __tablename__ = "team_park_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ballpark_key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    team: Mapped[str] = mapped_column(String(10), index=True)
    venue_name: Mapped[str] = mapped_column(String(120))
    run_factor: Mapped[float] = mapped_column(Float, default=1.0)
    hr_factor: Mapped[float] = mapped_column(Float, default=1.0)
    hit_factor: Mapped[float] = mapped_column(Float, default=1.0)
    strikeout_factor: Mapped[float] = mapped_column(Float, default=1.0)
    handedness_notes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LineupSnapshot(Base):
    __tablename__ = "lineup_snapshots"
    __table_args__ = (UniqueConstraint("game_id", "team", "lineup_spot", name="uq_game_team_lineup_spot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    team: Mapped[str] = mapped_column(String(10), index=True)
    lineup_spot: Mapped[int] = mapped_column(Integer)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    game: Mapped[Game] = relationship(back_populates="lineup_snapshots")
    player: Mapped[Player] = relationship(back_populates="lineup_slots")


class SportsbookLine(Base):
    __tablename__ = "sportsbook_lines"
    __table_args__ = (
        UniqueConstraint("game_id", "player_id", "sportsbook", "market", "side", "line", name="uq_sportsbook_line"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    sportsbook: Mapped[str] = mapped_column(String(80), index=True)
    market: Mapped[str] = mapped_column(String(80), index=True)
    side: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    line: Mapped[float] = mapped_column(Float)
    odds_american: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    implied_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    game: Mapped[Game] = relationship(back_populates="sportsbook_lines")
    player: Mapped[Player] = relationship(back_populates="sportsbook_lines")


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"
    __table_args__ = (UniqueConstraint("market", "version", name="uq_market_model_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(60), index=True)
    version: Mapped[str] = mapped_column(String(40), index=True)
    artifact_path: Mapped[str] = mapped_column(String(255))
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PropPrediction(Base):
    __tablename__ = "prop_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    market: Mapped[str] = mapped_column(String(50), index=True)
    line: Mapped[float] = mapped_column(Float)
    projected_value: Mapped[float] = mapped_column(Float)
    edge_pct: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    cover_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rationale: Mapped[str] = mapped_column(String(1000))
    feature_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    player: Mapped[Player] = relationship(back_populates="predictions")
    game: Mapped[Game] = relationship(back_populates="predictions")
