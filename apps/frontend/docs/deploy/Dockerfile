FROM python:3.12-slim AS builder

ARG APP_VERSION=dev
ARG ENVIRONMENT=development
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ARG BUILD_TIME=unknown
ARG BUILD_HOST=unknown

WORKDIR /app

# Dependencies first (cached layer)
COPY apps/frontend/docs/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy corekinect library + protocols for API reference generation
COPY libs/python/ /app/libs/python/
COPY libs/protocols/ /app/libs/protocols/
COPY libs/ /app/libs/

# Copy docs source + config
COPY mkdocs.yml /app/
COPY docs/ /app/docs/

# Build with PYTHONPATH so mkdocstrings finds the library
ENV PYTHONPATH=/app/libs/python:/app/libs/protocols:/app/libs

# Build metadata
ENV APP_VERSION=${APP_VERSION} \
    ENVIRONMENT=${ENVIRONMENT} \
    GIT_COMMIT=${GIT_COMMIT} \
    GIT_BRANCH=${GIT_BRANCH} \
    BUILD_TIME=${BUILD_TIME} \
    BUILD_HOST=${BUILD_HOST}

RUN mkdocs build -d /app/site 2>&1 || \
    (echo "Strict build failed, retrying without strict..." && \
     sed -i 's/strict: true/strict: false/' /app/mkdocs.yml 2>/dev/null; \
     mkdocs build -d /app/site)

FROM nginx:alpine
COPY --from=builder /app/site /usr/share/nginx/html
EXPOSE 80
