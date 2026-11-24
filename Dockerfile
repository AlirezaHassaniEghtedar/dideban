FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -m didban
USER didban
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
