#!/bin/sh
# 16-envsubst-eden-nginx.sh — render the Eden frontend nginx config from its template at container
# start, substituting ONLY ${NGINX_LOCAL_RESOLVERS} (the pod's cluster DNS, exported by the base
# image's 15-local-resolvers.envsh, which the nginx entrypoint sources BEFORE this numbered step).
#
# The stock 20-envsubst-on-templates.sh only processes /etc/nginx/templates/*.template into
# /etc/nginx/conf.d/ (server-block fragments); the Eden config is a FULL nginx.conf (its own http{}
# with the /tmp temp paths + the lazy-resolver proxy), so it is rendered here into /etc/nginx/nginx.conf.
# envsubst is scoped to the single var so nginx's own $variables (proxy_pass captures) survive verbatim.
set -e

# Fall back to docker's embedded DNS (127.0.0.11) when the base image's resolver detection yields an
# empty value (unset OR set-but-empty) — an empty `resolver` directive is a fatal nginx config error.
if [ -z "${NGINX_LOCAL_RESOLVERS:-}" ]; then
    # Derive the pod's real resolver: /etc/resolv.conf works on BOTH substrates (k8s
    # cluster DNS / docker embedded DNS). The old hardcoded 127.0.0.11 default was
    # docker-only and broke the /gateway + /platform proxies on the home cluster.
    NGINX_LOCAL_RESOLVERS="$(awk '/^nameserver/{print $2; exit}' /etc/resolv.conf 2>/dev/null)"
    [ -n "$NGINX_LOCAL_RESOLVERS" ] || NGINX_LOCAL_RESOLVERS="127.0.0.11"
    export NGINX_LOCAL_RESOLVERS
fi

# The single quotes are REQUIRED: envsubst (not the shell) must receive the literal var list, so it
# substitutes ONLY this var and leaves nginx's own $variables intact.
# shellcheck disable=SC2016
envsubst '${NGINX_LOCAL_RESOLVERS}' \
    < /etc/nginx/nginx.conf.template \
    > /etc/nginx/nginx.conf

echo "16-envsubst-eden-nginx.sh: rendered nginx.conf (resolver=${NGINX_LOCAL_RESOLVERS})"
