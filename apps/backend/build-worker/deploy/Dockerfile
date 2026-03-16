FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY apps/backend/build-worker/setup.py setup.py
RUN pip install --no-cache-dir -e . && pip cache purge

# Copy shared libraries
COPY libs/protocols /libs/protocols
COPY libs/python /libs/python
ENV PYTHONPATH="/app/src:/libs:/libs/python:/libs/protocols"

# Copy app source
COPY apps/backend/build-worker/src src

# Install git for repo cloning
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client && rm -rf /var/lib/apt/lists/*

CMD ["python3", "-m", "src.main"]
