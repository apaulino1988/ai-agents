# Production image (spec: aws-deploy AC-001).
# No secrets, no database file — those live on the host (see deploy/).
FROM python:3.12-slim

RUN useradd --create-home --shell /usr/sbin/nologin app
WORKDIR /srv

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY app/ app/
COPY static/ static/
COPY data/business.json data/business.json

USER app
EXPOSE 8000

# SECRETARY_DB_PATH must point at a mounted volume (compose sets /data/secretary.db)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
