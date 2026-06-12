// good.go holds the compliant counterparts; none of these may be flagged.
package sample

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"sync"
	"time"
)

// Clock is a port; systemClock is the defaulting adapter.
type Clock interface{ Now() time.Time }

type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() } // adapter, not constructor: allowed

// GoodDependencies is the injected record.
type GoodDependencies struct{ Clock Clock }

// GoodWidget is the concrete result type.
type GoodWidget struct {
	clock Clock
}

// NewGoodWidget is pure: defaulting to an adapter is the documented exception.
func NewGoodWidget(deps GoodDependencies) (*GoodWidget, error) {
	if deps.Clock == nil {
		deps.Clock = systemClock{}
	}
	return &GoodWidget{clock: deps.Clock}, nil
}

// goodWrap wraps with %w.
func goodWrap(err error) error {
	return fmt.Errorf("loading widget: %w", err)
}

// goodClassify uses the Go 1.26 generic form.
func goodClassify(err error) (time.Duration, bool) {
	pe, ok := errors.AsType[*pathError](err)
	if !ok {
		return 0, false
	}
	_ = pe
	return time.Second, true
}

// goodRun takes ctx first.
func goodRun(ctx context.Context, name string) error {
	_ = name
	<-ctx.Done()
	return nil
}

// goodFan uses the stdlib multi-handler.
func goodFan(a, b slog.Handler) *slog.Logger {
	return slog.New(slog.NewMultiHandler(a, b))
}

// goodSpawn uses WaitGroup.Go.
func goodSpawn(inputs []string) {
	var wg sync.WaitGroup
	for range inputs {
		wg.Go(func() {})
	}
	wg.Wait()
}

// Small interfaces compose.
type Getter interface{ Get(key string) (string, bool) }
type Putter interface{ Put(key, value string) }
