package fetchall

import (
	"context"
	"errors"
	"sort"
	"sync"
)

// Result holds the output of a single operation, along with the index of its
// input in the original slice.
type Result struct {
	Index  int
	Output string
}

// Process runs operation on each input with at most concurrency operations in
// flight. Results are returned ordered by Index. When some operations fail,
// the remaining inputs are still processed and the aggregate error wraps every
// individual failure so that errors.Is / errors.As can reach them.
func Process(
	ctx context.Context,
	inputs []string,
	concurrency int,
	operation func(ctx context.Context, input string) (string, error),
) ([]Result, error) {
	if concurrency < 1 {
		return nil, errors.New("fetchall: concurrency must be >= 1")
	}
	if len(inputs) == 0 {
		return nil, nil
	}

	// Semaphore implemented as a buffered channel.  A goroutine sends a token
	// before running and receives it back when done, so at most concurrency
	// tokens (and thus goroutines) are in flight.
	sem := make(chan struct{}, concurrency)

	var (
		mu      sync.Mutex
		results []Result
		errs    []error
		wg      sync.WaitGroup
	)

	for i, input := range inputs {
		i, input := i, input
		wg.Go(func() {
			// Acquire the semaphore slot, or bail if ctx is cancelled first.
			select {
			case sem <- struct{}{}:
			case <-ctx.Done():
				return
			}
			defer func() { <-sem }()

			output, err := operation(ctx, input)

			mu.Lock()
			if err != nil {
				errs = append(errs, err)
			} else {
				results = append(results, Result{Index: i, Output: output})
			}
			mu.Unlock()
		})
	}

	wg.Wait()

	sort.Slice(results, func(i, j int) bool {
		return results[i].Index < results[j].Index
	})

	if len(errs) > 0 {
		return results, errors.Join(errs...)
	}
	return results, nil
}