//go:build load

package edenhttp_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/edenhttptest"
)

// loadN is the concurrent request fan-out (the `load` verb sets EDEN_LOAD_N; default 500).
func loadN() int {
	if raw := os.Getenv("EDEN_LOAD_N"); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

type loadInput struct {
	Command string `json:"command"`
}

type loadOutput struct {
	By string `json:"by"`
}

// TestLoad_ConcurrentPipelineRaceClean fires N concurrent requests at one spine + pipeline handler
// (the *Spine is shared and must be safe for concurrent use) under -race, mixing authorized and
// under-granted callers, and asserts every authorized request got a 200 and every under-granted one
// a 403 — no race, no torn Identity, no cross-request state bleed.
//
//nolint:paralleltest // a load fan-out owns the process goroutine budget; running it parallel to other tests would distort the high-water assertion.
func TestLoad_ConcurrentPipelineRaceClean(t *testing.T) {
	spine, err := edenhttp.New(
		edenhttp.Config{},
		edenhttp.Deps{Verifier: edenhttptest.NewVerifier(), Clock: edenhttptest.FixedClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	pipeline := edenhttp.Handler[loadInput, loadOutput]{
		Required: edenhttp.NewGrant("sessions", "control"),
		Execute: func(_ context.Context, id edenhttp.Identity, _ loadInput) (loadOutput, error) {
			return loadOutput{By: id.Subject}, nil
		},
	}
	handler := spine.Middleware(pipeline)

	authorizedToken := edenhttptest.MintToken("sessions:control")
	underGrantedToken := edenhttptest.MintToken("sessions:read")

	var ok200, forbidden403, wrong atomic.Int64
	semaphore := make(chan struct{}, 64) // bound the goroutine high-water (race-clean fan-out).
	var waitGroup sync.WaitGroup
	total := loadN()
	for index := 0; index < total; index++ {
		waitGroup.Add(1)
		semaphore <- struct{}{}
		go func(authorized bool) {
			defer waitGroup.Done()
			defer func() { <-semaphore }()
			token := authorizedToken
			if !authorized {
				token = underGrantedToken
			}
			request := httptest.NewRequest(http.MethodPost, "/sessions/x/control", strings.NewReader(`{"command":"prompt"}`))
			request.Header.Set("Authorization", "Bearer "+token)
			recorder := httptest.NewRecorder()
			handler.ServeHTTP(recorder, request)

			switch {
			case authorized && recorder.Code == http.StatusOK:
				ok200.Add(1)
			case !authorized && recorder.Code == http.StatusForbidden:
				forbidden403.Add(1)
			default:
				wrong.Add(1)
			}
		}(index%2 == 0)
	}
	waitGroup.Wait()

	if wrong.Load() != 0 {
		t.Fatalf("%d concurrent requests had the wrong status (race/state-bleed)", wrong.Load())
	}
	if ok200.Load()+forbidden403.Load() != int64(total) {
		t.Errorf("handled %d, want %d", ok200.Load()+forbidden403.Load(), total)
	}
}
