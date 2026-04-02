FROM python:3.10-slim AS builder
WORKDIR /app

# Install doc tooling
RUN pip install --no-cache-dir \
    mkdocs-material \
    mkdocs-awesome-pages-plugin \
    'mkdocstrings[python]'

# Copy corekinect library + protocols for API reference generation
COPY libs/python/ /app/libs/python/
COPY libs/protocols/ /app/libs/protocols/

# Install corekinect deps so mkdocstrings can introspect
RUN pip install --no-cache-dir \
    grpcio protobuf requests minio pyyaml python-dotenv \
    termcolor sqlalchemy sshtunnel 'paramiko<4' pytest

# Copy docs source + config
COPY mkdocs.yml /app/
COPY docs/ /app/docs/

# Build with PYTHONPATH so mkdocstrings finds the library
ENV PYTHONPATH=/app/libs/python:/app/libs/protocols:/app/libs
RUN mkdocs build -d /app/site

FROM nginx:alpine
COPY --from=builder /app/site /usr/share/nginx/html
EXPOSE 80
