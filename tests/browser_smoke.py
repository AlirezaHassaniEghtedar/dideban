"""Run with Python Playwright and installed Edge. Uses an isolated temp database."""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

def smoke():
    with TemporaryDirectory() as folder, socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port = sock.getsockname()[1]
        sock.close()
        url = f"http://127.0.0.1:{port}"
        password = secrets.token_urlsafe(24)
        env = dict(os.environ, DATABASE_URL="sqlite:///"+str(Path(folder)/"browser.db"), ADMIN_PASSWORD=password)
        server = subprocess.Popen([sys.executable,"-m","uvicorn","app.main:app","--port",str(port)],env=env)
        try:
            for _ in range(100):
                try:
                    with urlopen(url,timeout=1):
                        break
                except OSError:
                    time.sleep(.1)
            with sync_playwright() as p:
                browser=p.chromium.launch(channel=os.getenv("BROWSER_CHANNEL","msedge"))
                page=browser.new_page(http_credentials={"username":"admin","password":password})
                for width in (360,430,768,1440):
                    page.set_viewport_size({"width":width,"height":850})
                    page.goto(url)
                    assert page.locator("html").get_attribute("dir")=="rtl"
                    page.locator("summary").click()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    page.get_by_label("شهر",exact=True).fill("تهران")
                    page.get_by_role("button",name="جست‌وجو").click()
                    assert page.get_by_text("فرصتی با این مشخصات پیدا نشد").is_visible()
                    page.screenshot(path=str(Path(folder)/f"results-{width}.png"))
                page.goto(url+"/admin")
                page.get_by_label("نام منبع").fill("منبع آزمون")
                page.get_by_label("نشانی اطلاعیه عمومی").fill("https://example.org/notice")
                page.get_by_role("button",name="ثبت منبع").click()
                page.get_by_role("link",name="منبع آزمون").wait_for()
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)

if __name__=="__main__":
    smoke()

