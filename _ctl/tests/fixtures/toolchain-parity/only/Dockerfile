# The Dockerfile of the fixture image `only`. cmd_validate asks 4 things of it:
# that it is non-empty, that it carries a FROM, that no RUN line hardcodes a
# semver, and that no RUN line reads ${USERNAME} after a switch to zsh. It
# builds nothing, and the linter that reads it here is a stub.
FROM ubuntu:24.04

RUN true
