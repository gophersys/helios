package configuration

import "strconv"

// Path is a resolved-tree location: dotted keys with [i] indices
// (e.g. "engine.models[0].auth"). It is the join key between a typed library
// view and a source Position. Empty Path is the root.
type Path string

// Child appends ".key" to the path. On the root (empty) Path there is no
// leading dot, so Path("").Child("engine") == "engine".
func (p Path) Child(key string) Path {
	if p == "" {
		return Path(key)
	}
	return p + "." + Path(key)
}

// Index appends "[i]" to the path.
func (p Path) Index(i int) Path {
	return p + Path("["+strconv.Itoa(i)+"]")
}
