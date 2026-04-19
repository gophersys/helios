# syntax=docker/dockerfile:1.7
#
# images/python — Python 3.12 via uv, on top of images/base.
#
# uv is the package manager + Python installer. We install uv first and
# let it manage the Python interpreter, which keeps the image slim (no
# apt python3 that drifts with Ubuntu's release cadence) and gives us a
# reproducible interpreter pin.
ARG BASE_TAG=latest
FROM ghcr.io/gophersys/base:${BASE_TAG}

LABEL org.opencontainers.image.source="https://github.com/gophersys/.devcontainer"
LABEL org.opencontainers.image.description="Python 3.12 via uv"

USER root

ARG UV_VERSION=0.5.11
ARG PYTHON_VERSION=3.12

ENV UV_INSTALL_DIR=/usr/local/bin \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_CACHE_DIR=/var/cache/uv \
    PATH=/opt/uv-python/bin:/usr/local/bin:${PATH}

# Official uv installer. Pin the version so the base is reproducible.
RUN curl -fsSL https://astral.sh/uv/${UV_VERSION}/install.sh \
      | env UV_INSTALL_DIR=/usr/local/bin sh \
 && uv --version

# Let uv install a pinned Python into a shared path. Symlinks expose the
# standard `python` and `python3` names on PATH.
RUN mkdir -p "${UV_PYTHON_INSTALL_DIR}" "${UV_CACHE_DIR}" \
 && uv python install "${PYTHON_VERSION}" \
 && PY_BIN="$(uv python find ${PYTHON_VERSION})" \
 && ln -sf "${PY_BIN}" /usr/local/bin/python \
 && ln -sf "${PY_BIN}" /usr/local/bin/python3 \
 && chmod -R a+rx "${UV_PYTHON_INSTALL_DIR}" \
 && chmod -R a+rwx "${UV_CACHE_DIR}" \
 && python --version

USER dev
WORKDIR /home/dev
