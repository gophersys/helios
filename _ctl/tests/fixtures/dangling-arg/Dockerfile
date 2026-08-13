# Counter-stimulus fixture for _ctl/tests/dockerfile-args.test.sh.
#
# Nothing builds this file and it is not an image. It exists so the detector in
# that test has a file it MUST report: a check that has never fired on input in
# the failing shape is a check nobody has watched work.
#
# The defect it carries is the one a rename produces. Renaming an ARG leaves the
# RUN line asking for the name it had before; the reference then expands to the
# empty string, the URL is wrong, and the build fails at `curl` with a 404 —
# LONG after the pull request that caused it was merged.
FROM ubuntu:24.04

ARG TOOL_VERSION=1.2.3

# DANGLING ON PURPOSE. No ARG declares TOOL_RELEASE_VERSION, so this expands to
# .../tool-v.tar.gz and fetches something that does not exist.
RUN curl -fsSL "https://example.invalid/tool-v${TOOL_RELEASE_VERSION}.tar.gz" -o /tmp/tool.tgz

# Declared and referenced correctly. The detector must NOT report this one — if
# it did, it would report every version reference in the repository.
RUN echo "tool ${TOOL_VERSION}"

# Prose, not an instruction. A detector that reads comments reports the
# ${NEVER_DECLARED_VERSION} written in this sentence, and zephyr/Dockerfile
# really does explain a zsh expansion in prose the same way.
