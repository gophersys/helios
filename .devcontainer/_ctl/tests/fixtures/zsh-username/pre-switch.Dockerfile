# _ctl/tests/fixtures/zsh-username/pre-switch.Dockerfile — the correct file.
#
# The quiet half of the counter-stimulus pair. It carries every shape the trap
# reader could over-report on, and zsh_username_run_references must print
# NOTHING for it. A detector that reports a correct file is as useless as one
# that reports nothing, and it is worse in one way: it teaches a reader that the
# gate is noise.
#
# It is the pattern base/Dockerfile and cloud/Dockerfile use today. Both still
# DECLARE `ARG USERNAME=dev`, because ENV, USER and the pre-switch RUN lines
# still read it; what left both files is the ${USERNAME} that a zsh RUN layer
# would have answered itself.
#
# This file is never built.
#
FROM ubuntu:24.04

ARG USERNAME=dev
ARG USER_UID=1000

# Every reference to the ARG is BEFORE the switch, under the default /bin/sh and
# then under an explicit bash. Neither shell touches USERNAME, so both read the
# build arg and mean `dev`.
RUN groupadd --gid "${USER_UID}" "${USERNAME}" \
 && useradd --uid "${USER_UID}" --gid "${USER_UID}" --create-home --shell /usr/bin/zsh "${USERNAME}"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN touch "/home/${USERNAME}/.bashrc"

SHELL ["/usr/bin/zsh", "-o", "pipefail", "-c"]

# AFTER the switch every RUN spells the user out. `dev` is a literal, so it
# means `dev` in a root layer and in the user's own layer alike.
RUN mkdir -p /opt/tool \
 && chown -R dev:dev /opt/tool

USER ${USERNAME}
RUN touch "/home/dev/.zshrc"
