# trivy --ignore-policy for the nightly scan — the ONE class rule this file holds.
#
# linux-libc-dev (the kernel HEADERS package) accrues unfixed kernel CVEs
# continuously: 5 CRITICALs in the 5 days to 2026-08-24, each marked
# `affected` with no fixed version, each turning all 6 scans red until a
# hand-written waiver landed. No kernel code from the package executes in a
# container — the host kernel is the runtime — so an UNFIXED kernel-header
# CVE carries no actionable risk here, and no bump can clear it.
#
# THE RULE IGNORES ONLY WHILE NO FIX EXISTS. The moment ubuntu publishes a
# fixed version, the FixedVersion field appears, the finding RESURFACES, and the
# next image rebuild picks the fix up through apt. So the gate keeps its
# teeth exactly where a fix is actionable.
#
# Decision: Mateo, 2026-08-24 ("Rego policy"), replacing the per-CVE waiver
# treadmill for this one package. Review with the waiver batch each quarter.
# Any OTHER package still takes a dated entry in .ci/trivyignore.yaml.
package trivy

default ignore = false

ignore {
    input.PkgName == "linux-libc-dev"
    not input.FixedVersion
}
