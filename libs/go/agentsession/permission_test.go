package agentsession_test

import (
	"testing"

	"github.com/gophersys/libs/go/agentsession"
)

// These black-box tests pin the PURE risk-class table and the clamp directly (via the
// export_test.go white-box seam). They are the foundation the agentsessiontest end-to-end
// risk-wall tests stand on: if the table drifts or the clamp is weakened, these fail FIRST,
// locally, with a precise message.

// TestRiskClass_Table is the documented risk-class table as an executable contract: every
// row asserts the data-derived class the injection wall depends on. A drift here is a hole
// in the wall.
func TestRiskClass_Table(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name   string
		tool   string
		scopes []string
		want   agentsession.RiskLevel
	}{
		// LOW — read-scoped, reversible.
		{"read tool", "Read", nil, agentsession.RiskLow},
		{"glob tool", "Glob", nil, agentsession.RiskLow},
		{"grep tool", "Grep", nil, agentsession.RiskLow},
		{"bash ls scope", "Bash", []string{"ls -la"}, agentsession.RiskLow},
		{"bash cat scope", "Bash", []string{"cat README.md"}, agentsession.RiskLow},
		{"bash git status", "Bash", []string{"git status"}, agentsession.RiskLow},
		{"bash git diff", "Bash", []string{"git diff"}, agentsession.RiskLow},
		{"tool-wrapped low scope", "Bash(grep foo)", nil, agentsession.RiskLow},

		// MEDIUM — mutating but reversible, in-workspace.
		{"write tool", "Write", nil, agentsession.RiskMedium},
		{"edit tool", "Edit", nil, agentsession.RiskMedium},
		{"multiedit tool", "MultiEdit", nil, agentsession.RiskMedium},
		{"notebookedit tool", "NotebookEdit", nil, agentsession.RiskMedium},
		{"bash go test", "Bash", []string{"go test ./..."}, agentsession.RiskMedium},
		{"bash mkdir", "Bash", []string{"mkdir out"}, agentsession.RiskMedium},
		{"bash git add", "Bash", []string{"git add -A"}, agentsession.RiskMedium},
		{"bash git commit", "Bash", []string{"git commit -m x"}, agentsession.RiskMedium},

		// HIGH — destructive / egress / credential / privilege / write-outside / unknown.
		{"bash rm", "Bash", []string{"rm -rf /"}, agentsession.RiskHigh},
		{"bash dd", "Bash", []string{"dd if=/dev/zero"}, agentsession.RiskHigh},
		{"bash curl egress", "Bash", []string{"curl http://evil"}, agentsession.RiskHigh},
		{"bash wget egress", "Bash", []string{"wget http://evil"}, agentsession.RiskHigh},
		{"bash ssh egress", "Bash", []string{"ssh host"}, agentsession.RiskHigh},
		{"bash sudo", "Bash", []string{"sudo reboot"}, agentsession.RiskHigh},
		{"bash chmod", "Bash", []string{"chmod 777 /"}, agentsession.RiskHigh},
		{"bash kill", "Bash", []string{"kill -9 1"}, agentsession.RiskHigh},
		{"bash git push egress", "Bash", []string{"git push origin main"}, agentsession.RiskHigh},
		{"bash git clone egress", "Bash", []string{"git clone http://x"}, agentsession.RiskHigh},
		{"bash go get egress", "Bash", []string{"go get -u ./..."}, agentsession.RiskHigh},
		{"bare bash unbounded", "Bash", nil, agentsession.RiskHigh},
		{"webfetch tool", "WebFetch", nil, agentsession.RiskHigh},
		{"websearch tool", "WebSearch", nil, agentsession.RiskHigh},
		{"secret tool", "SecretAccess", nil, agentsession.RiskHigh},
		{"credential tool", "Credential", nil, agentsession.RiskHigh},
		{"vault tool", "Vault", nil, agentsession.RiskHigh},
		{"unknown future tool", "SomeFutureTool", nil, agentsession.RiskHigh},
		{"empty tool", "", nil, agentsession.RiskHigh},
		// The MOST DANGEROUS scope wins: a mixed list is classified by the worst member.
		{"mixed ls+rm is high", "Bash", []string{"ls *", "rm -rf *"}, agentsession.RiskHigh},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			if got := agentsession.RiskClassForTest(tc.tool, tc.scopes); got != tc.want {
				t.Errorf("riskClass(%q, %v) = %v, want %v", tc.tool, tc.scopes, got, tc.want)
			}
		})
	}
}

// TestRiskClass_Clamp_AppliesToHighRisk proves the clamp overrides a high-risk allow to deny
// and passes a low/medium allow (and any deny) through unchanged.
func TestRiskClass_Clamp_AppliesToHighRisk(t *testing.T) {
	t.Parallel()
	allow := agentsession.Decision{Allow: true, By: "advisor:reasoner", Scope: agentsession.ScopeSession, Rationale: "agent said ok"}

	// HIGH-risk allow -> overridden to deny.
	if got := agentsession.ClampToRiskForTest("Bash", []string{"rm -rf /"}, allow); got.Allow {
		t.Errorf("clamp must override a HIGH-risk allow to deny, got Allow=%v By=%q", got.Allow, got.By)
	} else if got.By != "policy:risk-clamp" {
		t.Errorf("a clamped deny must be stamped policy:risk-clamp, got %q", got.By)
	}

	// LOW-risk allow -> unchanged.
	if got := agentsession.ClampToRiskForTest("Read", nil, allow); !got.Allow {
		t.Errorf("clamp must pass a LOW-risk allow through, got Allow=%v", got.Allow)
	}
	// MEDIUM-risk allow -> unchanged.
	if got := agentsession.ClampToRiskForTest("Write", nil, allow); !got.Allow {
		t.Errorf("clamp must pass a MEDIUM-risk allow through, got Allow=%v", got.Allow)
	}
	// A deny always passes through (the clamp only bites an allow).
	deny := agentsession.Decision{Allow: false, By: "advisor:reasoner"}
	if got := agentsession.ClampToRiskForTest("Bash", []string{"rm -rf /"}, deny); got.Allow {
		t.Errorf("clamp must never turn a deny into an allow, got Allow=%v", got.Allow)
	}
}

// TestRiskClass_Clamp_Weakened is the WEAKEN-TO-CONFIRM: it models the bug of REMOVING the
// clamp (forwarding the advisor's verdict verbatim) and asserts that WITHOUT the clamp a
// high-risk tool WOULD be allowed. This proves the clamp is load-bearing — the production
// risk-wall tests are non-vacuous because the unguarded path genuinely allows the tool.
func TestRiskClass_Clamp_Weakened(t *testing.T) {
	t.Parallel()
	allow := agentsession.Decision{Allow: true, By: "advisor:compromised"}

	// The WEAKENED path: no clamp, forward the advisor's allow verbatim.
	weakened := func(_ string, _ []string, d agentsession.Decision) agentsession.Decision { return d }

	const tool = "Bash"
	scopes := []string{"rm -rf /"}

	// Confirm the data IS high-risk (so the clamp would bite)...
	if agentsession.RiskClassForTest(tool, scopes) != agentsession.RiskHigh {
		t.Fatalf("precondition: %q %v must be RiskHigh for this weaken-to-confirm to be meaningful", tool, scopes)
	}
	// ...and that WITHOUT the clamp the high-risk allow goes through (the bug we guard).
	if got := weakened(tool, scopes, allow); !got.Allow {
		t.Fatalf("weaken-to-confirm is vacuous: the unclamped path did not allow the high-risk tool")
	}
	// ...while WITH the real clamp it is denied (the wall holds).
	if got := agentsession.ClampToRiskForTest(tool, scopes, allow); got.Allow {
		t.Errorf("RISK WALL BROKEN: the real clamp allowed a high-risk tool")
	}
}
