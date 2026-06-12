package fetchall

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"sync"
)

// Result holds one successful output from Process, indexed by its position
// in the input slice.
type Result struct {
	Index  int
	Output string
}

// Process runs operation concurrently on every input, with at most concurrency
// operations in flight at any moment.
//
// concurrency must be >= 1. Empty inputs returns (nil, nil).
// When one or more operations fail, every individual failure remains reachable
// in the returned aggregated error via errors.Is / errors.AsType / errors.As.
// Results are returned ordered by Index ascending.
func Process(
	ctx context.Context,
	inputs []string,
	concurrency int,
	operation func(ctx context.Context, input string) (string, error),
) ([]Result, error) {
	if concurrency < 1 {
		return nil, fmt.Errorf("fetchall: concurrency must be at least 1, got %d", concurrency)
	}
	if len(inputs) == 0 {
		return nil, nil
	}

	// Buffered channel acts as a counting semaphore: send to acquire, receive
	// to release, so at most concurrency goroutines are in-flight.
	sem := make(chan struct{}, concurrency)

	var (
		mu      sync.Mutex
		results []Result
		errs    []error
	)
	var wg sync.WaitGroup

	for i, input := range inputs {
		// Wait for a semaphore slot, but abort launching new work if the
		// parent context is cancelled.
		select {
		case sem <- struct{}{}:
		case <-ctx.Done():
			goto wait
		}

		idx, inp := i, input
		wg.Add(1) //nolint:staticcheck // WaitGroup.Go not used because semaphore lifecycle straddles goroutine boundaries
		go func() {
			defer func() {
				<-sem // release the semaphore slot
				wg.Done()
			}()
			out, err := operation(ctx, inp)
			mu.Lock()
			if err != nil {
				errs = append(errs, fmt.Errorf("input %d: %w", idx, err))
			} else {
				results = append(results, Result{Index: idx, Output: out})
			}
			mu.Unlock()
		}()
	}
wait:
	wg.Wait()

	// Sort results by Index to match input order.
	sort.Slice(results, func(a, b int) bool {
		return results[a].Index < results[b].Index
	})

	if len(errs) > 0 {
		return results, errors.Join(errs...)
	}
	return results, nil
}
