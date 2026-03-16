#!/bin/sh
# Render nginx config template with environment variables.
# The official nginx:alpine image runs scripts in /docker-entrypoint.d/ on startup.
# envsubst is already available in nginx:alpine.
envsubst '${API_HOST} ${API_PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf
