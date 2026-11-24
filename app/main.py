import os
import secrets
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal
import jdatetime
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, insert, update, or_
from sqlalchemy.exc import IntegrityError
from .db import engine, items, sources, jobs, runs, migrate, now
from .extract import CATEGORIES, norm
from .db import candidates
from .fetch import canonical

@asynccontextmanager
async def lifespan(app):
    migrate()
    yield

app = FastAPI(title="دیده‌بان خدمت", lifespan=lifespan)
root = Path(__file__).parent
templates = Jinja2Templates(directory=root / "templates")
app.mount("/static", StaticFiles(directory=root/"static"), name="static")
basic = HTTPBasic(auto_error=False)

@app.middleware("http")
async def protect_admin(request: Request, call_next):
    if request.url.path.startswith("/api/admin/") and request.method not in ("GET","HEAD","OPTIONS"):
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (origin and urlsplit(origin).netloc != request.url.netloc):
            return JSONResponse({"detail":"Cross-origin management request"},status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" if not request.url.path in ("/docs","/redoc") else "frame-ancestors 'none'"
    if "/admin" in request.url.path:
        response.headers["Cache-Control"] = "no-store"
    return response

def admin(credentials: HTTPBasicCredentials | None = Depends(basic)):
    key = os.getenv("ADMIN_PASSWORD", "")
    if len(key)<16 or not credentials or not secrets.compare_digest(credentials.password.encode(),key.encode()) or credentials.username != "admin":
        raise HTTPException(401, headers={"WWW-Authenticate":'Basic realm="Didban"'})

def jalali(value):
    if not value:
        return "نامشخص"
    if isinstance(value,str):
        value=date.fromisoformat(value[:10])
    return jdatetime.date.fromgregorian(date=value).strftime("%Y/%m/%d").translate(str.maketrans("0123456789","۰۱۲۳۴۵۶۷۸۹"))
templates.env.filters["jalali"] = jalali

def all_rows(query):
    with engine.connect() as conn:
        return [dict(x) for x in conn.execute(query).mappings()]

def search(q:str=Query("",max_length=200), category:str="", city:str="", model:str="", province:str="", major:str="", education:str="", skill:str="", commitment:str="", org_type:str="", deadline_before:date|None=None, status:Literal["","expired","unknown"]="", sort:Literal["updated","deadline","title"]="updated", page:int=Query(1,ge=1,le=100000)):
    canonical_ids = select(func.min(items.c.id)).where(items.c.review=="published").group_by(items.c.digest)
    query=select(items, sources.c.name.label("source_name"), sources.c.url).join(sources).where(items.c.id.in_(canonical_ids))
    if q.strip():
        term=norm(q)
        query=query.where(or_(*(col.contains(term,autoescape=True) for col in (items.c.title,items.c.organization,items.c.summary))))
    for key,value in (("category",category),("city",city),("model",model)):
        if value:
            query=query.where(items.c[key]==norm(value))
    for key, value in (("استان",province),("رشته تحصیلی",major),("مقطع تحصیلی",education),("مهارت",skill),("نوع همکاری",commitment),("نوع سازمان",org_type)):
        if value:
            query = query.where(items.c.conditions[key].as_string().contains(norm(value), autoescape=True))
    if deadline_before:
        query = query.where(items.c.deadline <= deadline_before.isoformat())
    today = date.today().isoformat()
    if status == "expired":
        query = query.where(items.c.deadline < today)
    elif status == "unknown":
        query = query.where(or_(items.c.deadline == None, items.c.deadline >= today))
    order={"updated":items.c.updated.desc(),"deadline":items.c.deadline.asc().nulls_last(),"title":items.c.title}[sort]
    with engine.connect() as conn:
        total=conn.scalar(select(func.count()).select_from(query.subquery()))
        rows=conn.execute(query.order_by(order,items.c.id).limit(12).offset((page-1)*12)).mappings().all()
    return {"results":[dict(r) for r in rows],"total":total,"page":page}

app.get("/api/opportunities")(search)
app.get("/api/search")(search)

@app.get("/api/categories")
def categories():
    return CATEGORIES

@app.get("/api/opportunities/{identifier}")
def detail(identifier:int):
    rows=all_rows(select(items,sources.c.url,sources.c.name.label("source_name")).join(sources).where(items.c.id==identifier,items.c.review=="published"))
    if not rows:
        raise HTTPException(404)
    row = rows[0]
    row["references"] = all_rows(select(sources.c.name, sources.c.url).join(items).where(
        items.c.digest == row["digest"], items.c.review == "published").order_by(sources.c.id))
    return row

@app.get("/")
@app.get("/opportunities")
def listing(request:Request, data=Depends(search)):
    with engine.connect() as conn:
        denied = conn.scalar(select(func.count()).select_from(jobs).where(
            jobs.c.state == "failed", jobs.c.error.like("PermissionError:%")))
    return templates.TemplateResponse(request,"index.html",dict(data,home=request.url.path=="/",categories=CATEGORIES,denied=denied))

@app.get("/opportunities/{identifier}")
def page_detail(identifier:int,request:Request):
    return templates.TemplateResponse(request,"detail.html",{"item":detail(identifier)})

class Source(BaseModel):
    name:str=Field(min_length=2,max_length=200)
    url:str=Field(max_length=2048)
    @field_validator("url")
    @classmethod
    def normalize(cls,url):
        return canonical(url)

@app.post("/api/admin/sources",dependencies=[Depends(admin)],status_code=201)
def add(source:Source):
    try:
        with engine.begin() as conn:
            result=conn.execute(insert(sources).values(**source.model_dump(),next_check=now()))
            return {"id":result.inserted_primary_key[0]}
    except IntegrityError as exc:
        raise HTTPException(409,"منبع قبلاً ثبت شده است") from exc

@app.get("/api/admin/sources",dependencies=[Depends(admin)])
def source_list():
    return all_rows(select(sources).order_by(sources.c.id.desc()))

@app.get("/api/admin/crawl-jobs",dependencies=[Depends(admin)])
def job_list():
    return all_rows(select(jobs,sources.c.name).join(sources).order_by(jobs.c.updated.desc()).limit(100))

@app.post("/api/admin/crawl/{identifier}",dependencies=[Depends(admin)])
def queue(identifier:int):
    with engine.begin() as conn:
        result=conn.execute(update(sources).where(sources.c.id==identifier).values(next_check=now()))
        if not result.rowcount:
            raise HTTPException(404)
    return {"queued":True}

@app.get("/api/admin/reviews",dependencies=[Depends(admin)])
def reviews():
    return all_rows(select(items,sources.c.url).join(sources).where(items.c.review=="pending").order_by(items.c.updated).limit(100))

class Review(BaseModel):
    decision:Literal["published","rejected"]
    digest:str

@app.patch("/api/admin/opportunities/{identifier}",dependencies=[Depends(admin)])
def decide(identifier:int,review:Review):
    with engine.begin() as conn:
        result=conn.execute(update(items).where(items.c.id==identifier,items.c.digest==review.digest,items.c.review=="pending").values(review=review.decision))
        if not result.rowcount:
            raise HTTPException(409,"نسخهٔ رکورد تغییر کرده است")
    return {"review":review.decision}

@app.get("/admin",dependencies=[Depends(admin)])
def dashboard(request:Request):
    pending = all_rows(select(candidates).where(~candidates.c.url.in_(select(sources.c.url))).limit(100))
    return templates.TemplateResponse(request,"admin.html",{"sources":source_list(),"jobs":job_list(),"reviews":reviews(),"candidates":pending})

