import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Set up before importing the application. Never touch a developer database.
tmp=tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"]="sqlite:///"+str(Path(tmp.name)/"test.db")
os.environ["ADMIN_PASSWORD"]="temporary-test-only-credential"
from app.main import app
from app.db import engine
from app.worker import tick
from app.discovery import discover, search_news
from app.extract import extract, deadline_of
from app.enrichment import grounded, Proposal
from app.fetch import canonical, request

FIXTURE="<article><h1>فراخوان جذب امریه</h1><p>شهر: کرج</p><p>مهلت ثبت نام: ۱۴۰۴/۰۱/۰۱</p></article>"
def tearDownModule():
    engine.dispose()
    tmp.cleanup()

class Pipeline(unittest.TestCase):
    def test_tls_timeout_retries_verified_connection(self):
        addresses = [(None, None, None, None, ("8.8.8.8", 443))]
        with (patch("app.fetch.socket.getaddrinfo", return_value=addresses),
              patch("app.fetch.socket.create_connection") as connect,
              patch("app.fetch.ssl.create_default_context") as context,
              patch("app.fetch.http.client.HTTPSConnection") as connection):
            wrap = context.return_value.wrap_socket
            wrap.side_effect = [TimeoutError("handshake timed out"), MagicMock()]
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.read1.side_effect = [b"ok", b""]
            self.assertEqual(request("https://example.org/")[2], b"ok")
            self.assertEqual(connect.call_count, 2)
            self.assertEqual([call.kwargs["server_hostname"] for call in wrap.call_args_list],
                             ["example.org", "example.org"])

    def test_service_reduction_without_project_prefix(self):
        self.assertEqual(extract("<h1>فراخوان جذب برای کسری خدمت</h1>").category, "پروژه کسری خدمت")

    def test_robots_local_redirect(self):
        from email.message import Message
        from app.fetch import fetch
        html = Message()
        html["Content-Type"] = "text/html"
        replies = [(301, {"Location": "/policy.txt"}, b""), (200, {}, b"User-agent: *\nAllow: /"), (200, html, b"ok")]
        with patch("app.fetch.request", side_effect=replies) as get, patch("app.fetch.time.sleep"):
            self.assertEqual(fetch("https://example.org/news"), "ok")
            self.assertEqual(get.call_args_list[1].args[0], "https://example.org/policy.txt")

    def test_discovery_across_iranian_sites(self):
        page = '<a href="https://university.ac.ir/news">فراخوان جذب امریه</a>'
        self.assertIn("https://university.ac.ir/news", discover(page, "https://news.ir/"))
        with patch("app.discovery.request", return_value=(200, {}, '{"articles":[{"url":"https://university.ac.ir/news","title":"جذب امریه"}]}'.encode())):
            self.assertIn("https://university.ac.ir/news", search_news())

    def test_dates_and_missing(self):
        item=extract(FIXTURE)
        self.assertEqual(item.deadline,date(2025,3,21))
        self.assertEqual(item.city,"کرج")
        self.assertIsNone(item.model)
        self.assertIsNone(item.organization)
        self.assertIsNone(deadline_of("مهلت ثبت نام: 1404/13/01"))
        conflict=extract(FIXTURE.replace("</article>","<p>مهلت ثبت نام: ۱۴۰۴/۰۲/۰۱</p></article>"))
        self.assertIsNone(conflict.deadline)
        self.assertIn("conflict",conflict.evidence)
        self.assertIsNone(extract("<h1>اخبار روز</h1>"))

    def test_grounding(self):
        record=extract(FIXTURE)
        proposal=Proposal.model_validate({"organization":{"value":"شرکت نمونه","evidence":"جذب در شرکت نمونه"},"city":None})
        self.assertIsNone(grounded(record,proposal,FIXTURE).organization)

    def test_public_fetch(self):
        with self.assertRaises(ValueError): canonical("http://example.org")
        with self.assertRaises(ValueError): request("https://127.0.0.1/")
        with self.assertRaises(ValueError): canonical("https://name@example.org/")

    def test_review_flow(self):
        auth=("admin",os.environ["ADMIN_PASSWORD"])
        with TestClient(app) as api:
            self.assertEqual(api.get("/api/admin/sources").status_code,401)
            source={"name":"آزمون","url":"https://example.org/test"}
            self.assertEqual(api.post("/api/admin/sources",json=source,auth=auth).status_code,201)
            self.assertEqual(api.post("/api/admin/sources",json=source,auth=auth).status_code,409)
            with patch.dict(os.environ,{"OPENAI_API_KEY":""}):
                tick(lambda _: FIXTURE)
                self.assertEqual(api.get("/api/search").json()["total"],0)
                row=api.get("/api/admin/reviews",auth=auth).json()[0]
                change={"decision":"published","digest":row["digest"]}
                self.assertEqual(api.patch("/api/admin/opportunities/1",json=change,auth=auth).status_code,200)
                self.assertEqual(api.get("/api/search",params={"city":"كرج"}).json()["total"],1)
                self.assertEqual(api.get("/api/search",params={"q":"تهران"}).json()["total"],0)
                self.assertIn("کرج",api.get("/opportunities/1").text)
                api.post("/api/admin/crawl/1",auth=auth)
                tick(lambda _:FIXTURE)
                self.assertEqual(api.get("/api/search").json()["total"],1)
                api.post("/api/admin/crawl/1",auth=auth)
                tick(lambda _: (_ for _ in ()).throw(TimeoutError("timeout")))
                self.assertEqual(api.get("/api/search").json()["total"],1)
                self.assertEqual(api.get("/api/admin/crawl-jobs",auth=auth).json()[0]["state"],"failed")

