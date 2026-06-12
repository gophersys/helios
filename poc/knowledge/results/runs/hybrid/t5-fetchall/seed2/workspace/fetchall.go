package fetchall

import (
	"context"
	"errors"
	"sync"
)

// Result holds the output of a single operation paired with the index of its
// input in the original inputs slice.
type Result struct {
	Index  int
	Output string
}

// Process runs operation on each input with bounded concurrency, collecting
// successful results ordered by their original index. When at least one
// operation fails, all operations still run and the returned error aggregates
// every individual failure so that each remains reachable via errors.Is /
// errors.As.
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

	sem := make(chan struct{}, concurrency)
	results := make([]*Result, len(inputs))
	var (
		mu   sync.Mutex
		errs []error
		wg   sync.WaitGroup
	)

	for i, input := range inputs {
		// Acquire semaphore slot before spawning the goroutine.
		sem <- struct{}{}

		i, input := i, input
		wg.Go(func() {
			defer func() { <-sem }()
			out, err := operation(ctx, input)
			mu.Lock()
			if err != nil {
				errs = append(errs, err)
			} else {
				results[i] = &Result{Index: i, Output: out}
			}
			mu.Unlock()
		})
	}

	wg.Wait()

	// Collect only the successful results, which are already in order.
	out := make([]Result, 0, len(inputs))
	for _, r := range results {
		if r != nil {
			out = append(out, *r)
		}
	}

	if len(errs) > 0 {
		return out, errors.Join(errs...)
	}
	return out, nil
}