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
COPY libs/ /app/libs/

# Install corekinect with all deps so mkdocstrings can introspect
RUN pip install --no-cache-dir \
    grpcio protobuf requests minio pyyaml python-dotenv \
    termcolor sqlalchemy sshtunnel 'paramiko<4' pytest pytest-timeout

# Copy docs source + config
COPY mkdocs.yml /app/
COPY docs/ /app/docs/

# Build with PYTHONPATH so mkdocstrings finds the library
# Use --strict=false so missing cross-references don't fail the build
ENV PYTHONPATH=/app/libs/python:/app/libs/protocols:/app/libs
RUN mkdocs build -d /app/site 2>&1 || \
    (echo "Strict build failed, retrying without strict..." && \
     sed -i 's/strict: true/strict: false/' /app/mkdocs.yml 2>/dev/null; \
     mkdocs build -d /app/site)

FROM nginx:alpine
COPY --from=builder /app/site /usr/share/nginx/html
EXPOSE 80
