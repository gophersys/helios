package fetchall

import (
	"context"
	"errors"
	"sync"
)

// Result holds a single successful operation output paired with its input index.
type Result struct {
	Index  int
	Output string
}

// Process runs operation concurrently for each input, limiting concurrency
// to at most concurrency in-flight operations at any moment.
//
// Results are ordered by Index ascending and contain an entry for every input
// that succeeded. When one or more operations fail, Process returns the
// successful results together with a single aggregated error; every individual
// failure remains reachable via errors.Is / errors.As.
//
// concurrency must be >= 1. Empty inputs returns (nil, nil).
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

	type slot struct {
		result *Result
		err    error
	}

	slots := make([]slot, len(inputs))

	var (
		wg  sync.WaitGroup
		sem = make(chan struct{}, concurrency)
	)

	for i, input := range inputs {
		// Acquire semaphore slot (blocking).
		sem <- struct{}{}
		i, input := i, input

		wg.Go(func() {
			defer func() { <-sem }() // release slot

			out, err := operation(ctx, input)
			if err != nil {
				slots[i] = slot{err: err}
			} else {
				slots[i] = slot{result: &Result{Index: i, Output: out}}
			}
		})
	}

	wg.Wait()

	// Build ordered results and collect errors.
	var (
		results []Result
		errs    []error
	)
	for _, s := range slots {
		if s.result != nil {
			results = append(results, *s.result)
		}
		if s.err != nil {
			errs = append(errs, s.err)
		}
	}

	if len(errs) > 0 {
		return results, errors.Join(errs...)
	}
	return results, nil
}