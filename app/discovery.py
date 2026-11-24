"""Find Iranian announcements in the news index and on source pages."""
import json
from urllib.parse import urlencode, urljoin, urlsplit
from bs4 import BeautifulSoup
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from .db import sources
from .extract import norm
from .fetch import canonical, request

NEWS_SEARCH = "https://api.gdeltproject.org/api/v2/doc/doc?" + urlencode({
    "query": '("military service" OR conscription OR conscripts OR "knowledge-based companies") sourcecountry:iran',
    "mode": "artlist", "format": "json", "timespan": "7d",
    "sort": "datedesc", "maxrecords": 250,
})
INDEXES = [("جست‌وجوی اخبار ایران", NEWS_SEARCH),
           ("خبرگزاری دانشجویان ایران", "https://www.isna.ir/"),
           ("خبرگزاری مهر", "https://www.mehrnews.com/"),
           ("خبرگزاری تسنیم", "https://www.tasnimnews.ir/"),
           ("خبرگزاری دانشجو", "https://snn.ir/")]

def relevant(title):
    return any(word in norm(title) for word in (
        "امریه", "کسری خدمت", "کسر خدمت", "جایگزین خدمت", "سرباز فناور",
        "سرباز نخب", "سرباز پژوهش", "سرباز معلم", "سربازمعلم"))

def search_news():
    status, _, body = request(NEWS_SEARCH)
    if status != 200:
        raise ValueError(f"News search HTTP {status}")
    links = {}
    for article in json.loads(body)["articles"]:
        if not relevant(article.get("title") or ""):
            continue
        try:
            url = canonical(article.get("url") or "")
        except ValueError:
            continue
        if len(url) <= 2048:
            links[url] = urlsplit(url).hostname
    return links

def register_sources(conn, entries):
    for name, url in entries:
        if conn.scalar(select(sources.c.id).where(sources.c.url == url)):
            continue
        try:
            with conn.begin_nested():
                conn.execute(insert(sources).values(name=name[:200], url=url))
        except IntegrityError:
            continue

def discover(html, origin):
    soup = BeautifulSoup(html,"html.parser")
    found = {}
    for link in soup.select("a[href]"):
        title = norm(link.get_text(" ",strip=True))
        if not relevant(title):
            continue
        try:
            url = canonical(urljoin(origin,link["href"]))
        except ValueError:
            continue
        host = urlsplit(url).hostname
        if url != origin and (host == urlsplit(origin).hostname or host.endswith(".ir")) and len(url)<=2048:
            found[url] = title[:200]
        if len(found)>=30:
            break
    return found


