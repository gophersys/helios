package agentprofile

import (
	"bytes"
	"encoding/json"
	"maps"
	"slices"
	"strconv"
)

// schemaVersion is the one profile-document schema version this library parses. A document that
// names any other version is refused rather than parsed on a guess: the schema is the contract
// between the document author and every renderer, so a version this build does not know is a
// document it cannot honestly render.
const schemaVersion = 1

// document is the parsed profile document — the whole role x harness matrix and the layers it is
// composed from. It is deliberately unexported: the document's public shape is its JSON, which
// Config.Document carries, so the schema can gain a field without widening the frozen Go surface.
type document struct {
	SchemaVersion int                 `json:"schemaVersion"`
	Defaults      layer               `json:"defaults"`
	Roles         map[string]roleSpec `json:"roles"`
	Overlays      map[string]layer    `json:"overlays"`
}

// layer is one contributor to a cell's composition: the defaults, a role, or a repository overlay.
// The three are the same shape on purpose — precedence is decided by WHERE a layer sits in the
// chain, never by a layer being able to express something the others cannot.
type layer struct {
	Instruction string     `json:"instruction"`
	Rules       []Fragment `json:"rules"`
	Skills      []Fragment `json:"skills"`
}

// roleSpec is one row of the matrix: a layer, plus the harnesses that row may be rendered for.
type roleSpec struct {
	layer
	Harnesses []Harness `json:"harnesses"`
}

// parseDocument decodes and validates the profile document. Unknown fields and trailing content are
// REFUSED, not ignored: a typo in a key would otherwise silently render a profile missing the rule
// its author thought they had declared, and that is exactly the failure this library exists to make
// impossible.
func parseDocument(raw []byte) (document, error) {
	var parsed document
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&parsed); err != nil {
		return document{}, parseFault(raw, err)
	}
	if decoder.More() {
		return document{}, invalid("the profile document carries trailing content after its first JSON value")
	}
	if err := parsed.validate(); err != nil {
		return document{}, err
	}
	return parsed, nil
}

// validate checks every invariant a renderer is then allowed to assume. Roles and overlays are
// walked in sorted order so a document with two faults always reports the same one first — a
// validator whose message depended on map order would make a failing build unreproducible.
func (d *document) validate() error {
	if d.SchemaVersion != schemaVersion {
		return invalid("schemaVersion " + strconv.Itoa(d.SchemaVersion) + " is not supported; this library parses schemaVersion " + strconv.Itoa(schemaVersion))
	}
	if len(d.Roles) == 0 {
		return invalid("the profile document declares no roles")
	}
	if err := d.Defaults.validate("defaults"); err != nil {
		return err
	}
	for _, name := range slices.Sorted(maps.Keys(d.Roles)) {
		if err := d.validateRole(name); err != nil {
			return err
		}
	}
	for _, name := range slices.Sorted(maps.Keys(d.Overlays)) {
		if !validSlug(name) {
			return invalid("overlay name " + strconv.Quote(name) + " is not an HNS-1 slug (rule 11)")
		}
		overlay := d.Overlays[name]
		if err := overlay.validate("overlay " + name); err != nil {
			return err
		}
	}
	return nil
}

// validateRole checks one row of the matrix: a slug name, at least one known harness declared once,
// an instruction that resolves to something, and well-formed fragments.
func (d *document) validateRole(name string) error {
	if !validSlug(name) {
		return invalid("role name " + strconv.Quote(name) + " is not an HNS-1 slug (rule 11)")
	}
	role := d.Roles[name]
	if len(role.Harnesses) == 0 {
		return invalid("role " + name + " declares no harnesses; a row with no column renders nothing")
	}
	for i, harness := range role.Harnesses {
		if !harness.known() {
			return invalid("role " + name + " declares unknown harness " + strconv.Quote(string(harness)))
		}
		if slices.Contains(role.Harnesses[:i], harness) {
			return invalid("role " + name + " declares harness " + string(harness) + " twice")
		}
	}
	if d.Defaults.Instruction == "" && role.Instruction == "" {
		return invalid("role " + name + " resolves to an empty instruction; declare one on the role or in defaults")
	}
	return role.validate("role " + name)
}

// validate checks both fragment sets of one layer. scope names the layer in any message, so a fault
// in a 40-role document points at the role that carries it.
func (l *layer) validate(scope string) error {
	if err := validateFragments(l.Rules, scope+" rules"); err != nil {
		return err
	}
	return validateFragments(l.Skills, scope+" skills")
}

// validateFragments checks that every fragment carries a slug name unique within its set and a
// non-empty body. An empty body is refused because it renders an empty file, which reads to the
// next human as a rule that was deleted rather than one that was never written.
func validateFragments(fragments []Fragment, scope string) error {
	for i := range fragments {
		fragment := &fragments[i]
		if !validSlug(fragment.Name) {
			return invalid(scope + ": fragment name " + strconv.Quote(fragment.Name) + " is not an HNS-1 slug (rule 11)")
		}
		if fragment.Body == "" {
			return invalid(scope + ": fragment " + fragment.Name + " has an empty body")
		}
		for j := range fragments[:i] {
			if fragments[j].Name == fragment.Name {
				return invalid(scope + ": fragment " + fragment.Name + " is declared twice")
			}
		}
	}
	return nil
}

// selectOverlay checks that repository names an overlay the document declares. An unknown selector
// is a KindNotFound failure at New rather than an overlay silently resolving to nothing: a
// repository that meant to override a rule and quietly did not is the drift this library prevents.
// The empty selector is the base matrix and selects no overlay.
func (d *document) selectOverlay(repository string) error {
	if repository == "" {
		return nil
	}
	if _, declared := d.Overlays[repository]; !declared {
		return notFound("the profile document declares no overlay for repository " + strconv.Quote(repository) +
			"; declare one, or leave Config.Repository empty for the base matrix")
	}
	return nil
}

// resolve projects one cell of the matrix through the precedence chain (defaults < role < overlay)
// into the immutable Resolved a renderer consumes. The overlay lookup of an empty or absent
// selector yields the zero layer, which contributes nothing — New has already refused an unknown
// non-empty selector, so a silent miss here is not reachable.
func (d *document) resolve(target Target, repository string) (Resolved, error) {
	role, declared := d.Roles[string(target.Role)]
	if !declared {
		return Resolved{}, notFound("the profile document declares no role " + strconv.Quote(string(target.Role)))
	}
	if !slices.Contains(role.Harnesses, target.Harness) {
		return Resolved{}, notFound("role " + string(target.Role) + " declares no harness " +
			strconv.Quote(string(target.Harness)) + "; the matrix has no such cell")
	}
	overlay := d.Overlays[repository]
	return Resolved{
		SchemaVersion: d.SchemaVersion,
		Target:        target,
		Repository:    repository,
		Instruction:   lastNonEmpty(d.Defaults.Instruction, role.Instruction, overlay.Instruction),
		Rules:         composeFragments(d.Defaults.Rules, role.Rules, overlay.Rules),
		Skills:        composeFragments(d.Defaults.Skills, role.Skills, overlay.Skills),
	}, nil
}

// composeFragments applies precedence across the layer sets in ascending order — a later set
// REPLACES a same-named fragment from an earlier one — and returns the result sorted by name. The
// sort is what keeps the emission independent of map order and of the order the document happened
// to list its fragments in.
func composeFragments(sets ...[]Fragment) []Fragment {
	byName := make(map[string]Fragment)
	for _, set := range sets {
		for _, fragment := range set {
			byName[fragment.Name] = fragment
		}
	}
	composed := make([]Fragment, 0, len(byName))
	for _, name := range slices.Sorted(maps.Keys(byName)) {
		composed = append(composed, byName[name])
	}
	return composed
}

// lastNonEmpty returns the last non-empty candidate, which is the precedence rule for a scalar:
// the highest layer that declares one wins, and a layer that declares nothing overrides nothing.
func lastNonEmpty(candidates ...string) string {
	chosen := ""
	for _, candidate := range candidates {
		if candidate != "" {
			chosen = candidate
		}
	}
	return chosen
}

// validSlug reports whether s is an HNS-1 slug (rule 11): word ("-" word)*, word := [a-z][a-z0-9]*.
// Role names, overlay names and fragment names all become path components of the emission, so the
// slug rule is also what keeps a document from steering a write outside the profile root — the
// grammar admits no dot, no slash and no separator.
func validSlug(s string) bool {
	if s == "" {
		return false
	}
	wordStart := true
	for i := range len(s) {
		character := s[i]
		switch {
		case character == '-':
			if wordStart {
				return false
			}
			wordStart = true
		case character >= 'a' && character <= 'z':
			wordStart = false
		case character >= '0' && character <= '9':
			if wordStart {
				return false
			}
		default:
			return false
		}
	}
	return !wordStart
}
