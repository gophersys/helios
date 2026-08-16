# Devcontainer = the CI image + interactive comforts. FROM the CI image so the
# two can never drift: a failure in CI reproduces here byte for byte.
FROM ghcr.io/gophersys/research-ui-ci:latest

RUN apt-get update -q && apt-get install -y -q --no-install-recommends \
      zsh less jq gh ripgrep \
    && rm -rf /var/lib/apt/lists/* || \
    (apt-get update -q && apt-get install -y -q zsh less jq ripgrep && rm -rf /var/lib/apt/lists/*)
