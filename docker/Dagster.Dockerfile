FROM python:3.11-slim

WORKDIR /opt/dagster/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-dagster.txt .
RUN pip install --no-cache-dir -r requirements-dagster.txt

COPY pipeline/ pipeline/
COPY ingestion/ ingestion/
COPY transforms/ transforms/
COPY quality/ quality/

ENV DAGSTER_HOME=/opt/dagster/home
RUN mkdir -p $DAGSTER_HOME

COPY docker/dagster.yaml ${DAGSTER_HOME}/dagster.yaml
COPY docker/workspace.yaml /opt/dagster/app/workspace.yaml

ENV PYTHONPATH=/opt/dagster/app

CMD ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000", "-w", "/opt/dagster/app/workspace.yaml"]
