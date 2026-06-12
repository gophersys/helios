package fetchall

import (
	"context"
	"errors"
	"sort"
	"sync"
)

// Result holds the successful output of a single operation, paired with the
// index of its input.
type Result struct {
	Index  int
	Output string
}

// Process calls operation once for each input. At most concurrency operations
// are in flight at any moment. Results are returned ordered by Index ascending.
// When any operation fails, Process waits for all inflight work and then returns
// the successful results together with a single aggregated error that wraps
// every individual failure (reachable via errors.Is / errors.As).
func Process(
	ctx context.Context,
	inputs []string,
	concurrency int,
	operation func(ctx context.Context, input string) (string, error),
) ([]Result, error) {
	if concurrency < 1 {
		return nil, errors.New("fetchall: concurrency must be at least 1")
	}
	if len(inputs) == 0 {
		return nil, nil
	}

	// Semaphore: at most concurrency slots.
	sem := make(chan struct{}, concurrency)

	var mu sync.Mutex
	var wg sync.WaitGroup

	results := make([]Result, 0, len(inputs))
	var errs []error

	for i, input := range inputs {
		// Acquire a semaphore slot, respecting parent ctx cancellation.
		select {
		case sem <- struct{}{}:
		case <-ctx.Done():
			// Context cancelled while waiting for a slot; wait for in-flight
			// goroutines, then return whatever we have.
			wg.Wait()
			mu.Lock()
			if len(errs) > 0 {
				errs = append(errs, context.Cause(ctx))
			}
			mu.Unlock()
			// Fall through to finalize below.
			goto finalize
		}

		wg.Add(1)
		go func(idx int, inp string) {
			defer func() { <-sem }()
			defer wg.Done()

			out, err := operation(ctx, inp)
			if err != nil {
				mu.Lock()
				errs = append(errs, err)
				mu.Unlock()
				return
			}
			mu.Lock()
			results = append(results, Result{Index: idx, Output: out})
			mu.Unlock()
		}(i, input)
	}

	wg.Wait()

finalize:
	sort.Slice(results, func(a, b int) bool {
		return results[a].Index < results[b].Index
	})

	if len(errs) > 0 {
		return results, errors.Join(errs...)
	}
	return results, nil
}