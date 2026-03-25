FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends git openssh-client && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir requests urllib3

WORKDIR /app

COPY apps/backend/git-poller/src/ src/

CMD ["python3", "-m", "src.main"]
