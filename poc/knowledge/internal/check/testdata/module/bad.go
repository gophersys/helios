// Package sample exercises every rule's BAD shape exactly once.
package sample

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"sync"
	"time"
)

type widget struct{ created time.Time }

// NewWidget violates go/constructor-purity (direct time.Now).
func NewWidget() (*widget, error) {
	return &widget{created: time.Now()}, nil
}

// NewLaundered hides the impurity one call deep: clean under v1 (direct-call)
// analysis, a violation under v2 (-transitive) analysis.
func NewLaundered() (*widget, error) {
	return &widget{created: stamp()}, nil
}

func stamp() time.Time { return time.Now() }

// loadPort violates go/environment-confinement (env read in a library).
func loadPort() string {
	return os.Getenv("SAMPLE_PORT")
}

// wrap violates go/error-wrapping (%v on an error).
func wrap(err error) error {
	return fmt.Errorf("loading widget: %v", err)
}

// concat violates go/error-wrapping (err.Error() concatenation).
func concat(err error) error {
	return errors.New("loading widget: " + err.Error())
}

// Store violates go/interface-size (5 methods > 4).
type Store interface {
	Get(key string) (string, bool)
	Put(key, value string)
	Delete(key string)
	List() []string
	Compact() error
}

// Cacher is consumed by NewCacher below.
type Cacher interface {
	Get(key string) (string, bool)
	Put(key, value string)
}

// NewCacher violates go/return-concrete (returns project-defined interface)
// — and is itself pure, so it must NOT trip constructor-purity.
func NewCacher() (Cacher, error) {
	return nil, nil
}

// run violates go/context-first (ctx is the second parameter).
func run(name string, ctx context.Context) error {
	_ = name
	<-ctx.Done()
	return nil
}

// typed error for the errors.As demonstration.
type pathError struct{ path string }

func (e *pathError) Error() string { return e.path }

// classify violates go/errors-astype (pre-1.26 errors.As).
func classify(err error) bool {
	var pe *pathError
	return errors.As(err, &pe)
}

// fanout violates go/slog-multihandler (hand-rolled fan-out handler).
type fanout struct{ handlers []slog.Handler }

func (f *fanout) Enabled(ctx context.Context, level slog.Level) bool { return true }
func (f *fanout) Handle(ctx context.Context, record slog.Record) error {
	for _, h := range f.handlers {
		_ = h.Handle(ctx, record)
	}
	return nil
}
func (f *fanout) WithAttrs(attrs []slog.Attr) slog.Handler { return f }
func (f *fanout) WithGroup(name string) slog.Handler       { return f }

// spawn violates go/waitgroup-go (inline Add/go/Done triple).
func spawn(inputs []string) {
	var wg sync.WaitGroup
	for range inputs {
		wg.Add(1)
		go func() {
			defer wg.Done()
		}()
	}
	wg.Wait()
}
