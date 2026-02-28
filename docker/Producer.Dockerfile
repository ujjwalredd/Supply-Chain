FROM python:3.11-slim

WORKDIR /app

COPY requirements-ingestion.txt .
RUN pip install --no-cache-dir -r requirements-ingestion.txt

COPY ingestion/ ingestion/

ENV PYTHONPATH=/app
