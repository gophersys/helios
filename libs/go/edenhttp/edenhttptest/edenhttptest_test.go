package edenhttptest_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/edenhttp/edenhttptest"
)

// canaryNeedle is a token planted into a LOG FIELD (not the message). A redaction canary scans the
// recorded lines for it; if the recorder dropped fields, this needle would vanish silently and the
// canary property would be vacuous. This meta-test pins the recorder's field-retention contract.
const canaryNeedle = "SEEDED-CANARY-edenhttptest-field-do-not-leak"

// TestRecordingLogger_RetainsInfoFields proves an Info FIELD VALUE is retained in the recorded line —
// the property that makes the edenhttp canary scan non-vacuous. WEAKEN-TO-CONFIRM: revert
// RecordingLogger.Info to store only `message` (dropping the variadic fields) and this fails, because
// the needle planted in a field would no longer reach Infos() — proving the assertion has teeth.
func TestRecordingLogger_RetainsInfoFields(t *testing.T) {
	t.Parallel()
	logger := &edenhttptest.RecordingLogger{}
	logger.Info("token verified", "token", canaryNeedle)

	lines := logger.Infos()
	if len(lines) != 1 {
		t.Fatalf("Infos() = %d lines, want 1: %v", len(lines), lines)
	}
	if !strings.Contains(lines[0], canaryNeedle) {
		t.Fatalf("the field value was dropped: Infos()[0]=%q does not contain the planted needle %q",
			lines[0], canaryNeedle)
	}
	if !strings.Contains(lines[0], "token verified") {
		t.Fatalf("the message was dropped: Infos()[0]=%q", lines[0])
	}
}

// TestRecordingLogger_RetainsErrorFields proves an Error FIELD VALUE is retained too (the error path
// is the more likely leak site). WEAKEN-TO-CONFIRM: drop the fields in RecordingLogger.Error and this
// fails — the needle planted in an error field no longer reaches Errors().
func TestRecordingLogger_RetainsErrorFields(t *testing.T) {
	t.Parallel()
	logger := &edenhttptest.RecordingLogger{}
	logger.Error("verify failed", "offending-token", canaryNeedle)

	lines := logger.Errors()
	if len(lines) != 1 {
		t.Fatalf("Errors() = %d lines, want 1: %v", len(lines), lines)
	}
	if !strings.Contains(lines[0], canaryNeedle) {
		t.Fatalf("the field value was dropped: Errors()[0]=%q does not contain the planted needle %q",
			lines[0], canaryNeedle)
	}
}

// TestRecordingLogger_MessageOnlyStillWorks proves a fields-less call still records just the message
// (the renderLine fast path), so existing message-only assertions are unaffected by the field-retain
// change.
func TestRecordingLogger_MessageOnlyStillWorks(t *testing.T) {
	t.Parallel()
	logger := &edenhttptest.RecordingLogger{}
	logger.Info("plain message")

	lines := logger.Infos()
	if len(lines) != 1 || lines[0] != "plain message" {
		t.Fatalf("Infos() = %v, want [\"plain message\"]", lines)
	}
}
