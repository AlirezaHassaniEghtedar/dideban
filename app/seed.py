"""Register published source URLs for crawling, without publishing opportunity records."""
from sqlalchemy import select
from .db import migrate, engine, sources
from .fetch import canonical

SEEDS = [
    ("خبرگزاری تسنیم", "https://www.tasnimnews.ir/fa/news/1404/06/04/3385202/آغاز-ششمین-مرحله-جذب-امریه-سربازی-وزارت-ارتباطات-در-دولت-چهاردهم/amp"),
    ("خبرنامه دانشجویان ایران", "https://iusnews.ir/fa/news-details/449479/وزارت-ارتباطات-و-فناوری-اطلاعات:جذب-امریه-سربازی-در-وزارت-ارتباطات/"),
]
if __name__=="__main__":
    migrate()
    with engine.begin() as conn:
        for name,url in SEEDS:
            url=canonical(url)
            if not conn.scalar(select(sources.c.id).where(sources.c.url==url)):
                conn.execute(sources.insert().values(name=name,url=url))

