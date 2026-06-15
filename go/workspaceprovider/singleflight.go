package workspaceprovider

import "sync"

// keyedMutex is a per-key mutex: callers serialize on a string key while distinct keys proceed in
// parallel. It backs Provision's per-Name singleflight so concurrent same-Name provisions within a
// tenancy serialize (closing the check-then-create TOCTOU on a real substrate) while different-Name
// provisions never contend. The zero value is usable.
//
// It is a reference-counted lock registry, NOT a sharded fixed-lock map: an entry is created on
// first lock and DELETED when its last waiter unlocks, so a Provider that provisions millions of
// distinct workspaces over its lifetime does not leak a lock per Name (the map stays the size of
// the in-flight concurrent set, not the historical total).
type keyedMutex struct {
	mu    sync.Mutex
	locks map[string]*refLock
}

// refLock is one key's lock plus the count of goroutines currently holding OR waiting on it (so the
// registry can reclaim the entry when the count returns to zero).
type refLock struct {
	mu  sync.Mutex
	ref int
}

// lock acquires the per-key lock, registering/creating the entry under the registry mutex first
// (and bumping its refcount so a concurrent unlock does not reclaim it out from under this waiter),
// then blocking on the key's own mutex. It returns the unlock func the caller defers.
func (k *keyedMutex) lock(key string) func() {
	k.mu.Lock()
	if k.locks == nil {
		k.locks = make(map[string]*refLock)
	}
	rl := k.locks[key]
	if rl == nil {
		rl = &refLock{}
		k.locks[key] = rl
	}
	rl.ref++
	k.mu.Unlock()

	rl.mu.Lock()
	return func() {
		rl.mu.Unlock()
		k.mu.Lock()
		rl.ref--
		if rl.ref == 0 {
			delete(k.locks, key)
		}
		k.mu.Unlock()
	}
}
