# Counter-stimulus fixture for _ctl/tests/dockerfile-args.test.sh.
#
# Nothing builds this file and it is not an image. It exists so the ORPHAN
# detector in that test has a file it MUST report: a check that has never fired
# on input in the failing shape is a check nobody has watched work.
#
# The defect it carries is the mirror of the dangling one. Deleting a
# RUN-install line but leaving its `ARG *_VERSION` at the top of the file, or
# renaming an ARG and dropping the reference that used it, leaves a version ARG
# that no RUN line threads. The build still succeeds, so nothing fails — but the
# ARG is now a stale pin for a tool the image no longer installs, which is the
# tell that image content changed under a pull request.
FROM ubuntu:24.04

# Declared AND referenced. The detector must NOT report this one — if it did, it
# would report every version ARG in the repository. Named so it is neither a
# substring nor a superstring of the orphan below, so a substring-matching
# assertion cannot confuse the two.
ARG KEPT_TOOL_VERSION=1.2.3
RUN echo "tool ${KEPT_TOOL_VERSION}"

# ORPHAN ON PURPOSE. This ARG is declared but no RUN line references it, exactly
# as a deleted install leaves behind. The detector MUST report this name.
ARG ABANDONED_TOOL_VERSION=4.5.6

# Declared AND referenced, the digest half. The detector must NOT report this
# one — if it did, it would report every digest pin in the repository.
ARG KEPT_TOOL_SHA256_AMD64=2222222222222222222222222222222222222222222222222222222222222222
RUN echo "digest ${KEPT_TOOL_SHA256_AMD64}"

# ORPHAN ON PURPOSE, the digest half. A download that moved to another image,
# or a tool that was removed, leaves its digest ARG at the top. The build still
# succeeds, and the stale pin then reads as evidence that the image still
# verifies a tool it no longer installs. The detector MUST report this name.
ARG ABANDONED_TOOL_SHA256_AMD64=3333333333333333333333333333333333333333333333333333333333333333

# Prose, not a declaration. A commented `# ARG` line is not an ARG, so the
# detector must NOT treat COMMENTED_OUT_VERSION as declared-and-orphaned.
# ARG COMMENTED_OUT_VERSION=7.8.9
