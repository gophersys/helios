package fetchall

import (
	"context"
	"errors"
	"sync"
)

// Result holds one successful operation output alongside its original position.
type Result struct {
	Index  int
	Output string
}

type entry struct {
	output string
	err    error
}

// Process runs operation concurrently on each input, limiting parallelism to
// concurrency. Results are returned in input order. Errors are aggregated
// and each individual error remains reachable via errors.Is / errors.As.
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

	entries := make([]entry, len(inputs))
	sem := make(chan struct{}, concurrency)
	var wg sync.WaitGroup

	for i, input := range inputs {
		// Acquire a semaphore slot before launching.
		select {
		case sem <- struct{}{}:
		case <-ctx.Done():
			// Parent context cancelled; mark this and all remaining inputs
			// with the context error and stop launching.
			cause := context.Cause(ctx)
			if cause == nil {
				cause = ctx.Err()
			}
			for j := i; j < len(inputs); j++ {
				entries[j].err = cause
			}
			wg.Wait()
			return collect(entries)
		}

		wg.Add(1)
		go func(idx int, input string) {
			defer wg.Done()
			defer func() { <-sem }()
			out, err := operation(ctx, input)
			if err != nil {
				entries[idx].err = err
				return
			}
			entries[idx].output = out
		}(i, input)
	}

	wg.Wait()
	return collect(entries)
}

func collect(entries []entry) ([]Result, error) {
	var results []Result
	var errs []error

	for i, e := range entries {
		if e.err != nil {
			errs = append(errs, e.err)
		} else {
			results = append(results, Result{Index: i, Output: e.output})
		}
	}

	if len(errs) > 0 {
		return results, errors.Join(errs...)
	}
	return results, nil
}
