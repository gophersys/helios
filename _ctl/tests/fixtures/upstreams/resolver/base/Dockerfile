# Fixture world for _ctl/tests/resolve-upstream.test.sh — the GOVERNED file of
# a miniature repository: the 5 downloads whose bytes a digest answers for.
#
# Nothing builds this file and it is not an image. It is here because the
# download URL of a pin lives in the file that FETCHES it and nowhere else. The
# resolver reads the URL out of this file, substitutes the version it just
# resolved, and digests the bytes that URL then serves — so the digest it writes
# is the digest of the bytes the BUILD will fetch. A second copy of the URL in
# _build/upstreams.txt would let the resolver compute a correct digest of the
# wrong asset.
#
# The `case "${TARGETPLATFORM}"` arm is here for the same reason: `${ARCH}` is
# not a pin and not a table field, it is a shell variable the RUN block sets
# from the 1 sanctioned platform. A resolver that fetched the URL with `${ARCH}`
# left in it would ask the far end for a file whose name carries a dollar sign.
FROM ubuntu:24.04

ARG TARGETPLATFORM
ARG STUBGITHUB_VERSION
ARG STUBGITHUB_SHA256_AMD64
ARG STUBGO_VERSION
ARG STUBGO_SHA256_AMD64
ARG STUBK8S_VERSION
ARG STUBK8S_SHA256_AMD64
ARG STUBTAILSCALE_VERSION
ARG STUBTAILSCALE_SHA256_AMD64
ARG STUBFLUTTER_VERSION
ARG STUBFLUTTER_SHA256_AMD64

RUN case "${TARGETPLATFORM}" in \
      linux/amd64) ARCH=amd64 ;; \
      *) echo "unsupported platform: ${TARGETPLATFORM}"; exit 1 ;; \
    esac \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://github.com/stubowner/stubgithub/releases/download/v${STUBGITHUB_VERSION}/stubgithub-${STUBGITHUB_VERSION}.tar.gz" \
      /tmp/stubgithub.tar.gz "${STUBGITHUB_SHA256_AMD64}" STUBGITHUB_SHA256_AMD64 \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://go.dev/dl/go${STUBGO_VERSION}.linux-${ARCH}.tar.gz" \
      /tmp/stubgo.tar.gz "${STUBGO_SHA256_AMD64}" STUBGO_SHA256_AMD64 \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://dl.k8s.io/release/v${STUBK8S_VERSION}/bin/linux/${ARCH}/stubk8s" \
      /usr/local/bin/stubk8s "${STUBK8S_SHA256_AMD64}" STUBK8S_SHA256_AMD64 \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://pkgs.tailscale.com/stable/tailscale_${STUBTAILSCALE_VERSION}_${ARCH}.tgz" \
      /tmp/stubtailscale.tgz "${STUBTAILSCALE_SHA256_AMD64}" STUBTAILSCALE_SHA256_AMD64 \
 && /usr/local/lib/gophersys/fetch-verified.sh \
      "https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_${STUBFLUTTER_VERSION}-stable.tar.xz" \
      /tmp/stubflutter.tar.xz "${STUBFLUTTER_SHA256_AMD64}" STUBFLUTTER_SHA256_AMD64
