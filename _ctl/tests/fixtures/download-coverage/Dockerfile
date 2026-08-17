# Counter-stimulus fixture for _ctl/tests/download-coverage.test.sh.
#
# Nothing builds this file and it is not an image. It exists so the readers in
# that test have a file they MUST report and a file they must leave alone: a
# check that has never fired on input in the failing shape is a check nobody
# has watched work.
#
# Every fetch shape the real tree holds is here once, and the exemption file
# beside it (exemptions.txt) answers for the ones that need an answer. The
# names are chosen so no one is a substring of another, because the assertions
# match on the name.
FROM ubuntu:24.04

ARG TOOL_VERSION=1.2.3
ARG TOOL_SHA256_AMD64=1111111111111111111111111111111111111111111111111111111111111111
ARG DOUBLE_SHA256_AMD64=2222222222222222222222222222222222222222222222222222222222222222

# The apt layer. It names curl and wget as PACKAGES, and it fetches no URL of
# its own. A reader that counts the word `curl` reports this line, and then
# every apt block in the repository looks like an unverified download.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      wget \
 && rm -rf /var/lib/apt/lists/*

# VERIFIED. The digest goes to the helper as an argument, in the same command
# as the URL. This is the shape the whole rule exists to require, and the
# reader must NOT report it.
RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/verified-tool-v${TOOL_VERSION}.tar.gz" \
      /tmp/verified-tool.tar.gz \
      "${TOOL_SHA256_AMD64}" \
      TOOL_SHA256_AMD64

# UNCLASSIFIED ON PURPOSE. A plain curl with no digest and no exemption row.
# This is the defect: 51 downloads of the real tree looked exactly like it.
RUN curl -fsSL "https://example.invalid/unclassified-tool.tar.gz" -o /tmp/unclassified.tgz

# EXEMPT. No version lives in the URL, so no digest can be pinned to it. The
# row in exemptions.txt says so, and the reader must NOT report it.
RUN curl -fsSL "https://example.invalid/exempt-installer.sh" | sh

# DOUBLE-CLASSIFIED ON PURPOSE. It passes a digest to the helper AND carries an
# exemption row. Two answers for one download means the reader of the
# exemption file cannot tell which one holds, so the detector must report it.
RUN /usr/local/lib/gophersys/fetch-verified.sh \
      "https://example.invalid/double-classified.tar.gz" \
      /tmp/double.tar.gz \
      "${DOUBLE_SHA256_AMD64}" \
      DOUBLE_SHA256_AMD64

# Its 1 exemption row names a class outside the taxonomy. The site is answered
# exactly once, so only the class detector may report it.
RUN curl -fsSL "https://example.invalid/bad-class.tar.gz" -o /tmp/bad-class.tgz

# Its 1 exemption row is missing its reason field. The site is answered exactly
# once, so only the row-grammar detector may report it.
RUN curl -fsSL "https://example.invalid/malformed-row.tar.gz" -o /tmp/malformed.tgz

# Prose, not an instruction. A reader that reads comments finds
# https://example.invalid/prose-only.tar.gz here and reports a download that no
# layer performs — and base/Dockerfile really does write URLs in prose.
