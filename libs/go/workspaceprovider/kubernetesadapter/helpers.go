package kubernetesadapter

import (
	"context"
	"strconv"
	"strings"
	"time"

	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/util/intstr"
)

// httpsPort is the default egress port when an EgressRule declares none (443 only — the
// model-provider HTTPS endpoint is the common case).
const httpsPort = 443

// dnsPort / dnsUDP express the always-on DNS allow so an egress-restricted workload can still
// resolve its allowed hosts.
const dnsPort = 53

// maxPort is the 16-bit TCP/UDP port ceiling; port32 bounds a consumer-supplied port against it
// before the int32 conversion (a real bounds check on the NetworkPolicy build load path).
const maxPort = 65535

// volumeName derives a deterministic, RFC-1123-valid volume name from a mount target + index.
// The index disambiguates two mounts that sanitize to the same label (e.g. "/a/b" and "/a-b").
func volumeName(target string, index int) string {
	base := SanitizeName("vol-" + strings.TrimPrefix(target, "/"))
	suffix := "-" + strconv.Itoa(index)
	if len(base)+len(suffix) > maxDNSLabel {
		base = base[:maxDNSLabel-len(suffix)]
	}
	return strings.Trim(base, "-") + suffix
}

// port32 renders a port number as the intstr.IntOrString a NetworkPolicyPort carries. A port
// arrives from the consumer-supplied EgressRule.Ports (a load path), so the conversion is guarded
// by a real bounds check: an out-of-range value (negative or > the 16-bit TCP/UDP port ceiling)
// is clamped to 0 rather than silently wrapping into a bogus int32 port.
func port32(p int) intstr.IntOrString {
	if p < 0 || p > maxPort {
		p = 0
	}
	return intstr.FromInt32(int32(p)) // #nosec G115 -- guarded: p is clamped to 0..maxPort (65535) above, well within int32; gosec cannot follow the clamp.
}

// portInt32 is the GUARDED int->int32 conversion for the editor Service/Ingress/container ports
// (the SAME bounds-check discipline as port32, in one home): an out-of-range port is clamped to 0
// rather than wrapping into a bogus int32. editorPort already clamps to 1..maxPort, so this is a
// belt-and-braces guard the SAST tool can follow.
func portInt32(p int) int32 {
	if p < 0 || p > maxPort {
		p = 0
	}
	return int32(p) // #nosec G115 -- guarded: p is clamped to 0..maxPort (65535) above, well within int32.
}

// dnsEgressRule is the always-on DNS allow (TCP+UDP 53) every egress NetworkPolicy carries so a
// restricted workload can still resolve its allowed hosts.
func dnsEgressRule() networkingv1.NetworkPolicyEgressRule {
	tcp := corev1.ProtocolTCP
	udp := corev1.ProtocolUDP
	port := port32(dnsPort)
	return networkingv1.NetworkPolicyEgressRule{
		Ports: []networkingv1.NetworkPolicyPort{
			{Protocol: &tcp, Port: &port},
			{Protocol: &udp, Port: &port},
		},
	}
}

// asCIDR reports the CIDR form of host if it already is one (contains "/"), else "". A FQDN
// cannot be expressed in vanilla IP-based NetworkPolicy, so a non-CIDR host yields a port-only
// allow (the honest limit the manifest's CapEgressPolicy declaration acknowledges).
func asCIDR(host string) string {
	if strings.Contains(host, "/") {
		return host
	}
	return ""
}

// sleepCtx sleeps for d or returns the context error if ctx fires first (a ctx-aware pause for
// the Ready poll loop).
func sleepCtx(ctx context.Context, d time.Duration) error {
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err() //nolint:wrapcheck // the raw ctx error is inspected by the caller, which maps it to a DeadlineError.
	case <-timer.C:
		return nil
	}
}

// isNotFound reports whether err is a kubernetes apiserver 404 (so Dial/Destroy treat an absent
// object as gone, not an error).
func isNotFound(err error) bool {
	return apierrors.IsNotFound(err)
}

// podIsTerminating reports whether a pod is being deleted (a non-nil DeletionTimestamp), so
// Probe treats it as Gone rather than Ready.
func podIsTerminating(pod *corev1.Pod) bool {
	return pod.DeletionTimestamp != nil
}
