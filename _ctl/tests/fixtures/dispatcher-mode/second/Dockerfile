# The Dockerfile of the fixture image `second`. cmd_validate asks 4 things of it:
# that it is non-empty, that it carries a FROM, that no RUN line hardcodes a
# semver, and that no RUN line reads ${USERNAME} after a switch to zsh. It
# builds nothing and no test ever hands it to docker.
FROM ghcr.io/gophersys/first:latest

RUN true
