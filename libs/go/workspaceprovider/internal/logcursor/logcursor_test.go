package logcursor_test

import (
	"bytes"
	"math"
	"testing"

	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/internal/logcursor"
)

func TestReplay(t *testing.T) {
	t.Parallel()
	buf := []byte("0123456789")
	cases := []struct {
		name string
		from workspaceprovider.LogCursor
		want string
	}{
		{"from-start", 0, "0123456789"},
		{"mid", 4, "456789"},
		{"at-end", 10, ""},
		{"past-end-clamps", 50, ""},
		{"overflow-clamps", workspaceprovider.LogCursor(math.MaxUint64), ""},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			if got := logcursor.Replay(buf, tc.from); !bytes.Equal(got, []byte(tc.want)) {
				t.Errorf("Replay(%d) = %q, want %q", tc.from, got, tc.want)
			}
		})
	}
}
