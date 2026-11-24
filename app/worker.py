import logging
import time
from datetime import timedelta
from sqlalchemy import select, insert, update, or_
from .db import engine, sources, jobs, items, runs, history, migrate, now
from .fetch import fetch
from .extract import extract
from .enrichment import enrich
from .discovery import INDEXES, NEWS_SEARCH, discover, register_sources, search_news
from urllib.parse import urlsplit

INTERVAL = timedelta(minutes=30)

def persist(conn, source_id, record):
    old = conn.execute(select(items).where(items.c.source_id == source_id)).mappings().first()
    if record is None:
        if old:
            conn.execute(update(items).where(items.c.id==old["id"]).values(review="pending", checked=now()))
        return "irrelevant"
    if old and old["digest"] == record.digest:
        conn.execute(update(items).where(items.c.id==old["id"]).values(checked=now()))
        return "unchanged"
    values = dict(record.model_dump(mode="json"), updated=now(), checked=now(), review="pending")
    if old:
        previous = {k: old[k] for k in record.model_fields_set}
        conn.execute(insert(history).values(opportunity_id=old["id"], recorded=now(), previous=previous))
        conn.execute(update(items).where(items.c.id==old["id"]).values(**values))
        return "changed"
    conn.execute(insert(items).values(source_id=source_id, **values))
    return "created"

def tick(get_html=fetch):
    with engine.begin() as conn:
        query = select(sources).where(sources.c.next_check <= now()).order_by(sources.c.next_check).limit(1)
        src = conn.execute(query.with_for_update(skip_locked=True)).mappings().first()
        if not src:
            return False
        lease = now()
        conn.execute(update(sources).where(sources.c.id==src["id"]).values(next_check=lease+timedelta(minutes=15)))
        row = conn.execute(select(jobs).where(jobs.c.source_id==src["id"])).mappings().first()
        attempt = 1 if not row or row["state"]!="failed" else row["attempt"]+1
        statement = update(jobs).where(jobs.c.source_id==src["id"]) if row else insert(jobs).values(source_id=src["id"])
        conn.execute(statement.values(state="running", updated=lease, error=None, attempt=attempt))
    try:
        if src["url"] == NEWS_SEARCH:
            links = search_news()
            record = None
        else:
            html = get_html(src["url"])
            record = enrich(extract(html), html)
            links = discover(html, src["url"])
        error = None
    except Exception as exc:
        error = type(exc).__name__ + ": " + str(exc)[:180]
    with engine.begin() as conn:
        job = conn.execute(select(jobs).where(jobs.c.source_id==src["id"]).with_for_update()).mappings().one()
        if job["updated"] != lease:
            return True
        if error:
            result = "failed"
        else:
            result = "searched" if src["url"] == NEWS_SEARCH else persist(conn, src["id"], record)
            register_sources(conn, ((urlsplit(url).hostname, url) for url in links))
        conn.execute(insert(runs).values(source_id=src["id"], finished=now(), result=result, detail=error))
        conn.execute(update(jobs).where(jobs.c.id==job["id"]).values(state=result, updated=now(), error=error))
        delay = timedelta(minutes=min(30, 5 * 2**min(attempt-1,3))) if error else INTERVAL
        conn.execute(update(sources).where(sources.c.id==src["id"]).values(next_check=lease+delay))
    return True

if __name__ == "__main__":
    migrate()
    with engine.begin() as conn:
        register_sources(conn, INDEXES)
        conn.execute(update(sources).where(sources.c.next_check > now()+INTERVAL).values(next_check=now()))
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            time.sleep(2 if tick() else 15)
        except Exception:
            logging.exception("Worker transaction failed")
            time.sleep(15)

