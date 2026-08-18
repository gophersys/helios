# _ctl/tests/fixtures/zsh-username/post-switch.Dockerfile — the trap, staged.
#
# The counter-stimulus of zsh-username.test.sh, and it is the shape of a defect
# this repository has already shipped: mobile/Dockerfile chowned /opt/flutter
# and /opt/android-sdk through ${USERNAME} from zsh-as-root layers, both images
# shipped root-owned, and `flutter --version` as `dev` exited 128 with "detected
# dubious ownership". No build failed. The first smoke run that ever executed
# the tool found it.
#
# This file is never built. It is read by zsh_username_run_references in ctl.sh,
# and it carries BOTH directions on purpose — a detector that reports every
# ${USERNAME} is as useless as one that reports none:
#
#   REPORTED      a RUN line after the SHELL switch, on 1 line and on a
#                 continuation line. Docker hands the string to zsh, and zsh has
#                 already overwritten USERNAME with the EFFECTIVE user.
#   NOT REPORTED  the same reference BEFORE the switch, an ENV, a USER, and a
#                 Dockerfile comment inside a RUN continuation. The parser
#                 expands ENV and USER out of the build args and strips the
#                 comment, so no shell is involved in any of the 3.
#
FROM ubuntu:24.04

ARG USERNAME=dev

# BEFORE the switch. The default /bin/sh does not touch USERNAME, so this reads
# the ARG and it is not a hit.
RUN mkdir -p "/home/${USERNAME}/before-the-switch"

SHELL ["/usr/bin/zsh", "-o", "pipefail", "-c"]

# THE DEFECT, on 1 line. In a root layer this means `chown root`.
RUN chown -R "${USERNAME}:${USERNAME}" /opt/tool

# THE SAME DEFECT on a CONTINUATION line, spelled bare rather than braced, which
# is where a real one hides: the first line of the RUN is innocent.
RUN mkdir -p /opt/second \
 && chown -R "$USERNAME" /opt/second \
    # a Dockerfile comment inside a RUN continuation may name ${USERNAME}, and
    # the parser strips the whole line before any shell reads it
 && chmod 0755 /opt/second

# The Dockerfile PARSER expands both of these out of the build args. zsh never
# sees either one, so neither is a hit.
ENV HOME_DIRECTORY=/home/${USERNAME}
USER ${USERNAME}
