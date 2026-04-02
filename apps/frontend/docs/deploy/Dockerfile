FROM python:3.10-slim AS builder
WORKDIR /app
COPY mkdocs.yml /app/
COPY docs/ /app/docs/
RUN pip install mkdocs-material mkdocs-awesome-pages-plugin
RUN mkdocs build -d /app/site

FROM nginx:alpine
COPY --from=builder /app/site /usr/share/nginx/html
EXPOSE 80
