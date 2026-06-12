package fetchall

import (
	"context"
	"errors"
	"sort"
	"sync"
)

// Result holds a single successful output from Process.
type Result struct {
	Index  int    // position of the input that produced this output
	Output string
}

// Process runs operation on every input with at most concurrency operations
// in flight. Results are returned ordered by Index ascending, containing only
// successful outputs. When at least one operation fails, all errors are joined
// so every individual failure remains reachable via errors.Is / errors.As.
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

	// Semaphore pattern: buffered channel of size concurrency limits how many
	// goroutines hold a slot at once.
	sem := make(chan struct{}, concurrency)

	var (
		mu      sync.Mutex
		results []Result
		errs    []error
	)
	var wg sync.WaitGroup

	for i, input := range inputs {
		wg.Add(1)
		i, input := i, input
		go func() {
			defer wg.Done()

			// Acquire a semaphore slot, but also respect context cancellation.
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
		}()
	}

	wg.Wait()

	if len(results) > 0 {
		sort.Slice(results, func(a, b int) bool {
			return results[a].Index < results[b].Index
		})
	}

	if len(errs) > 0 {
		return results, errors.Join(errs...)
	}
	return results, nil
}
