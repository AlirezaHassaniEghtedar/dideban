"""Shared persistence and versioned schema initialization."""
import os
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, ForeignKey, Integer, MetaData, String,
                        Table, Text, JSON, create_engine, text)

engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///dideban.db"), pool_pre_ping=True)
meta = MetaData()

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

sources = Table("sources", meta,
    Column("id", Integer, primary_key=True), Column("name", String(200), nullable=False),
    Column("url", String(2048), unique=True, nullable=False),
    Column("next_check", DateTime, nullable=False, default=now))
jobs = Table("jobs", meta, Column("id", Integer, primary_key=True),
    Column("source_id", ForeignKey("sources.id"), nullable=False, unique=True),
    Column("state", String, nullable=False), Column("updated", DateTime, nullable=False),
    Column("attempt", Integer, nullable=False, default=0), Column("error", String))
items = Table("opportunities", meta, Column("id", Integer, primary_key=True),
    Column("source_id", ForeignKey("sources.id"), unique=True, nullable=False),
    Column("title", Text, nullable=False), Column("category", String, index=True),
    Column("organization", String), Column("city", String), Column("model", String),
    Column("deadline", String), Column("summary", Text), Column("evidence", JSON), Column("conditions", JSON),
    Column("digest", String, nullable=False), Column("updated", DateTime, nullable=False),
    Column("checked", DateTime, nullable=False), Column("review", String, index=True))
history = Table("changes", meta, Column("id", Integer, primary_key=True),
    Column("opportunity_id", ForeignKey("opportunities.id")), Column("recorded", DateTime),
    Column("previous", JSON))
runs = Table("crawl_history", meta, Column("id", Integer, primary_key=True),
    Column("source_id", ForeignKey("sources.id")), Column("finished", DateTime),
    Column("result", String), Column("detail", String))

candidates = Table("source_candidates", meta, Column("id", Integer, primary_key=True),
    Column("url", String(2048), nullable=False, unique=True), Column("title", String(200)),
    Column("origin", String(2048)))

def migrate():
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(692439)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"))
        if conn.scalar(text("SELECT max(version) FROM schema_version")) is None:
            meta.create_all(conn)
            conn.execute(text("INSERT INTO schema_version VALUES (1)"))
        if conn.scalar(text("SELECT max(version) FROM schema_version")) < 2:
            candidates.create(conn, checkfirst=True)
            conn.execute(text("INSERT INTO schema_version VALUES (2)"))
        if conn.scalar(text("SELECT max(version) FROM schema_version")) < 3:
            from sqlalchemy import inspect
            if "conditions" not in {col["name"] for col in inspect(conn).get_columns("opportunities")}:
                conn.execute(text("ALTER TABLE opportunities ADD COLUMN conditions JSON"))
            conn.execute(text("INSERT INTO schema_version VALUES (3)"))

