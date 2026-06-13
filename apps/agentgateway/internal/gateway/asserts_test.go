package gateway_test

import (
	"encoding/json"
	"strconv"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
)

// decodeData decodes an SSE data line into a generic map.
func decodeData(t *testing.T, data string) map[string]any {
	t.Helper()
	out := map[string]any{}
	if err := json.Unmarshal([]byte(data), &out); err != nil {
		t.Fatalf("decode sse data %q: %v", data, err)
	}
	return out
}

// assertMonotonicIDs proves the SSE ids (seqs) are strictly increasing with no gap and no
// duplicate, starting at 1 (Seq == transcript offset). This is the REQ-0023 monotonic
// sequence guarantee, observed on the wire.
func assertMonotonicIDs(t *testing.T, idTokens []string) {
	t.Helper()
	var prev uint64
	for i, token := range idTokens {
		seq, err := strconv.ParseUint(token, 10, 64)
		if err != nil {
			t.Fatalf("frame %d id %q is not a uint seq: %v", i, token, err)
		}
		if i == 0 {
			if seq != 1 {
				t.Fatalf("first id = %d, want 1 (Seq == transcript offset)", seq)
			}
		} else if seq != prev+1 {
			t.Fatalf("ids not contiguous: frame %d seq %d follows %d (gap or dup)", i, seq, prev)
		}
		prev = seq
	}
}

// assertReceivedCommand proves the scripted adapter received a control command of the given
// kind (the SUT actually forwarded prompt/steer/abort to the harness).
func assertReceivedCommand(t *testing.T, adapter *agentsessiontest.Adapter, kind agentsession.CommandKind) {
	t.Helper()
	for _, command := range adapter.Received() {
		if command.Kind == kind {
			return
		}
	}
	t.Fatalf("scripted adapter never received command kind %v; received %v", kind, adapter.Received())
}
