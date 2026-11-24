import hashlib
import re
from datetime import date
from typing import Literal

import jdatetime
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

CATEGORIES = ("امریه دولتی", "امریه شرکت دانش بنیان", "پروژه کسری خدمت", "پروژه جایگزین خدمت",
              "سرباز نخبگی", "پروژه پژوهشی", "سرباز فناور", "پروژه علمی و فناوری",
              "پژوهش تخصصی خدمت", "سایر طرح‌ها", "امریه", "سرباز معلم", "سرباز پژوهشگر")

CATEGORY_ALIASES = {"کسری خدمت": "پروژه کسری خدمت", "کسر خدمت": "پروژه کسری خدمت",
                    "جایگزین خدمت": "پروژه جایگزین خدمت", "سربازمعلم": "سرباز معلم"}
def norm(value):
    return " ".join(value.translate(str.maketrans("يك۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩‌", "یک01234567890123456789 ")).split())

class Extracted(BaseModel):
    title: str = Field(min_length=3, max_length=350)
    category: str
    organization: str | None = None
    city: str | None = None
    model: Literal["دورکاری", "حضوری", "ترکیبی"] | None = None
    deadline: date | None = None
    summary: str
    conditions: dict[str, str] = Field(default_factory=dict)
    evidence: dict[str, str]
    digest: str

def deadline_of(line):
    match = re.fullmatch(r"(?:مهلت ثبت نام|آخرین مهلت|پایان ثبت نام)\s*[:：]\s*(1[34]\d\d)[/-](\d{1,2})[/-](\d{1,2})", line)
    if match:
        try:
            return jdatetime.date(*map(int, match.groups())).togregorian()
        except ValueError:
            pass
    return None

def extract(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script,style,nav,footer,aside"):
        tag.decompose()
    root = soup.select_one("article, main") or soup
    heading = root.find("h1") or soup.title
    if not heading:
        return None
    title = norm(heading.get_text(" ", strip=True))[:350]
    category = next((v for v in CATEGORIES if norm(v) in title), None)
    if category is None:
        category = next((v for phrase, v in CATEGORY_ALIASES.items() if phrase in title), None)
    if not category or not re.search("فراخوان|پذیرش|جذب|ثبت نام|دعوت", title):
        return None
    lines = [norm(x) for x in root.get_text("\n", strip=True).splitlines() if x.strip()]
    evidence = {"title": title, "category": title}
    values = {}
    for key, label in (("city", "شهر"), ("organization", "سازمان"), ("model", "شیوه همکاری")):
        hits = {line for line in lines if line.startswith(label + ":")}
        if len(hits) == 1:
            line = hits.pop()
            value = line.partition(":")[2].strip()
            if value and len(value) <= 120 and (key != "model" or value in ("حضوری","دورکاری","ترکیبی")):
                values[key] = value
                evidence[key] = line
    deadlines = {d: line for line in lines if (d := deadline_of(line))}
    if len(deadlines) == 1:
        values["deadline"], evidence["deadline"] = next(iter(deadlines.items()))
    if len(deadlines) > 1:
        evidence["conflict"] = " | ".join(deadlines.values())
    labels = ("استان", "رشته تحصیلی", "مقطع تحصیلی", "مهارت", "نوع همکاری",
              "نوع سازمان", "مدارک لازم", "نحوه ثبت نام", "شرایط پذیرش", "مدت پروژه",
              "میزان کسری خدمت", "شرایط غیبت", "تاریخ اعزام", "ساعت همکاری", "تاریخ انتشار")
    conditions = {}
    for label in labels:
        prefix = label + ":"
        matches = {line for line in lines if line.startswith(prefix)}
        if len(matches) == 1:
            line = matches.pop()
            value = line[len(prefix):].strip()
            if value and len(value) <= 400:
                conditions[label] = value
                evidence[label] = line
    summary = next((x[:200] for x in lines if x != title and len(x)>25), title)
    return Extracted(title=title, category=category, summary=summary, evidence=evidence, conditions=conditions,
                     digest=hashlib.sha256("\n".join(lines).encode()).hexdigest(), **values)

