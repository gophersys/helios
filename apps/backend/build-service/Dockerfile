FROM python:3.12-slim

# Orchestrator dependencies: git, SSH, Docker CLI (for spawning builder containers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git openssh-client ca-certificates curl gnupg && \
    # Install Docker CLI from official Docker repo
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sdk/ /app/sdk/
COPY src/ src/

ENV PYTHONPATH=/app/src
EXPOSE 9002

CMD ["python3", "-u", "-m", "src.main"]
