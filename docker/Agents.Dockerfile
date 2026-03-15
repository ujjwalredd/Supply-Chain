FROM python:3.11-slim

WORKDIR /app

# Install Docker CLI so agents can restart sibling containers (self-healing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-agents.txt .
RUN pip install --no-cache-dir -r requirements-agents.txt

# Copy only agent source — env vars come from docker-compose, NOT from .env file
COPY agents/ ./agents/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health: verify we can reach postgres and agent tables exist
HEALTHCHECK --interval=30s --timeout=15s --start-period=90s --retries=5 \
    CMD python -c "import os,psycopg2; conn=psycopg2.connect(os.environ['DATABASE_URL']); cur=conn.cursor(); cur.execute('SELECT 1'); conn.close(); print('ok')" || exit 1

CMD ["python", "-m", "agents.run_all"]
