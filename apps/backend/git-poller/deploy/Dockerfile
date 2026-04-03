FROM python:3.12-slim

ARG APP_VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_TIME=unknown
ENV APP_VERSION=${APP_VERSION}
ENV GIT_COMMIT=${GIT_COMMIT}
ENV BUILD_TIME=${BUILD_TIME}

RUN apt-get update && \
    apt-get install -y --no-install-recommends git openssh-client && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY apps/backend/git-poller/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/backend/git-poller/src/ src/

EXPOSE 9003
CMD ["python3", "-u", "-m", "src.main"]
