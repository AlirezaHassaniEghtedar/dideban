# دیده‌بان خدمت

فهرست فارسی فراخوان‌های خدمت با بازبینی انسانی، ثبت شواهد و نمایش تاریخ شمسی.

## اجرای محلی
Python 3.13. In PowerShell run these from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:ADMIN_PASSWORD = Read-Host 'Enter a unique local admin password (16+ characters)'
python -m app.seed
Start-Process -WindowStyle Hidden -FilePath (Get-Command python).Source -ArgumentList '-m','app.worker'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 for the directory and /admin for management. User name is admin. /docs exposes the API schema. Start only one worker when using SQLite. An empty initial directory is expected. Seed registers two historical public articles. It never creates listings. Add public HTTPS announcement URLs in the admin page, wait for a crawl, review the source and publish. The original announcement link is always displayed. A reviewed listing makes no promise that applications are open.

## PostgreSQL and deployment
Copy .env.example to .env. Set a long random URL-safe POSTGRES_PASSWORD and a distinct ADMIN_PASSWORD of at least 16 characters. Run `docker compose up --build -d` then `docker compose exec web python -m app.seed`. Both services run the versioned migration at startup. The database volume survives restarts. Keep the published port bound to loopback and terminate TLS at the reverse proxy before exposing Basic authentication. Restrict admin access and rate-limit at that proxy. Back up the database before upgrades.

## Extraction and tests
Deterministic extraction runs first. Optional OPENAI_API_KEY enables sending up to 6,000 characters of public source text to OpenAI for organization and city proposals. Configure EXTRACTION_MODEL to select a compatible structured-output model. Missing fields remain unknown. Review every proposal before publishing.
Run `python -m unittest discover -s tests -v`. Test documents live only in temporary databases. See docs for architecture, design, skill assessment and release status.

