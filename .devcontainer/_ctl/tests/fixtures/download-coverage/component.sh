#!/usr/bin/env bash
#
# Counter-stimulus fixture for _ctl/tests/download-coverage.test.sh.
#
# Nothing runs this file and no image COPYs it. It exists so the reader is
# watched on the OTHER kind of governed file: _delta/components/*.sh install a
# tool group with the same curl-into-a-tarball shape a Dockerfile RUN uses, and
# a reader that only ever met a Dockerfile covers 7 real downloads with nothing.
#
# The 1 fetch below is unclassified on purpose, so the detector must report it.
set -Eeuo pipefail

curl -fsSL "https://example.invalid/component-tool.tar.gz" -o /tmp/component-tool.tgz
tar -xzf /tmp/component-tool.tgz -C /usr/local/bin
rm -f /tmp/component-tool.tgz
