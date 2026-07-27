FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/jobs.sqlite3

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt
COPY app ./app

RUN mkdir -p /data && chown app:app /data
USER app

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
