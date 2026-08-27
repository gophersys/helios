package agentprofile

import (
	"bytes"
	"context"
	"io/fs"
	"slices"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/errors"
)

// Config is the immutable, fully-resolved input: the profile document and the overlay selector that
// picks this repository's variant of it. It holds no path, no handle and no credential — everything
// that touches the world arrives through Deps.
type Config struct {
	// Document is the profile document as JSON bytes. REQUIRED. The caller reads it from wherever
	// it lives (a file, an object store, a ConfigMap); this library only parses it.
	Document []byte
	// Repository names the per-repository overlay to apply, and MUST be one the document declares.
	// Empty selects no overlay, which is the correct value for a caller rendering the base matrix.
	Repository string
}

// Deps is the injected hexagon: the harness renderers and the read-only view of the committed tree.
// New consumes ports; it constructs none.
type Deps struct {
	// Renderers are the harness renderers this Compiler can emit through, at least one, each
	// claiming a distinct Harness. A Target whose harness no renderer claims is a KindNotFound
	// error, never a silent empty emission.
	Renderers []Renderer
	// Tree is the read-only view of the committed working tree Drift compares a fresh render
	// against. REQUIRED even for a render-only caller: drift is half of what this library is for,
	// and a Compiler wired without a Tree is a check that cannot fail.
	Tree Tree
}

// Compiler is the concrete type New returns (return-concrete). It holds the parsed document, the
// selected overlay and the bound ports, all immutable after New, so Render and Drift hold no
// per-call state and are safe for concurrent use. The zero value is unusable; construct via New.
type Compiler struct {
	document   document
	repository string
	renderers  map[Harness]Renderer
	tree       Tree
}

// New is the constructor spine (10 §9). PURE: no I/O, no clock, no environment, no globals — it
// parses and validates the document, checks the overlay selector names a declared overlay, binds
// each injected Renderer to the harness it claims, and returns the concrete *Compiler. Binding
// calls Renderer.Harness, which the port requires to be a constant accessor, not an operation.
func New(configuration Config, dependencies Deps) (*Compiler, error) {
	if len(configuration.Document) == 0 {
		return nil, invalid("New requires Config.Document (the profile document bytes)")
	}
	if dependencies.Tree == nil {
		return nil, invalid("New requires Deps.Tree (a read-only view of the committed tree)")
	}
	renderers, err := bindRenderers(dependencies.Renderers)
	if err != nil {
		return nil, err
	}
	parsed, err := parseDocument(configuration.Document)
	if err != nil {
		return nil, err
	}
	if err := parsed.selectOverlay(configuration.Repository); err != nil {
		return nil, err
	}
	return &Compiler{
		document:   parsed,
		repository: configuration.Repository,
		renderers:  renderers,
		tree:       dependencies.Tree,
	}, nil
}

// bindRenderers indexes the injected renderers by the harness each claims. Two renderers claiming
// one harness is a wiring mistake with no defensible resolution — whichever won would be an
// accident of slice order — so it is refused rather than silently decided.
func bindRenderers(injected []Renderer) (map[Harness]Renderer, error) {
	if len(injected) == 0 {
		return nil, invalid("New requires at least one Deps.Renderers entry")
	}
	bound := make(map[Harness]Renderer, len(injected))
	for _, renderer := range injected {
		if renderer == nil {
			return nil, invalid("New rejects a nil entry in Deps.Renderers")
		}
		harness := renderer.Harness()
		if !harness.known() {
			return nil, invalid("New rejects a Deps.Renderers entry claiming unknown harness " + string(harness))
		}
		if _, duplicate := bound[harness]; duplicate {
			return nil, invalid("New rejects two Deps.Renderers entries claiming harness " + string(harness))
		}
		bound[harness] = renderer
	}
	return bound, nil
}

// Render emits the complete, deterministically ordered file set for one cell of the matrix. It
// resolves the target through the precedence chain, hands the projection to the bound renderer, and
// enforces this library's emission invariants on what comes back — so a third-party renderer cannot
// widen the contract by returning nothing, a duplicate path, or a path that escapes the tree.
func (c *Compiler) Render(ctx context.Context, target Target) (FileSet, error) {
	renderer, bound := c.renderers[target.Harness]
	if !bound {
		return nil, notFound("no Deps.Renderers entry claims harness " + string(target.Harness) +
			"; wire one, or render a target this Compiler can emit")
	}
	resolved, err := c.document.resolve(target, c.repository)
	if err != nil {
		return nil, err
	}
	files, err := renderer.Render(ctx, resolved)
	if err != nil {
		return nil, errors.Wrap(errors.KindOf(err), "agentprofile: render "+target.String(), err).
			WithField("target", target.String())
	}
	slices.SortFunc(files, func(left, right File) int { return strings.Compare(left.Path, right.Path) })
	if err := validateEmission(files, target); err != nil {
		return nil, err
	}
	return files, nil
}

// Drift renders the target afresh and reports every file whose committed bytes do not match. An
// empty result is the only clean verdict; a non-empty one is what fails a CI gate. Drift never
// writes: the Tree port has no write method, so this check cannot repair its own expectation.
func (c *Compiler) Drift(ctx context.Context, target Target) ([]Divergence, error) {
	rendered, err := c.Render(ctx, target)
	if err != nil {
		return nil, err
	}
	divergences := make([]Divergence, 0, len(rendered))
	for i := range rendered {
		file := &rendered[i]
		committed, readErr := c.tree.ReadFile(ctx, file.Path)
		switch {
		case readErr != nil && errors.Is(readErr, fs.ErrNotExist):
			divergences = append(divergences, Divergence{
				Path:   file.Path,
				Reason: DivergenceMissing,
				Diff:   "absent from the committed tree; rendered " + describeContent(file.Content) + "; re-render and commit it",
			})
		case readErr != nil:
			return nil, errors.Wrap(errors.KindOf(readErr), "agentprofile: read committed "+file.Path, readErr).
				WithField("path", file.Path)
		case !bytes.Equal(committed, file.Content):
			divergences = append(divergences, Divergence{
				Path:   file.Path,
				Reason: DivergenceContentDiffers,
				Diff: "committed " + describeContent(committed) + ", rendered " + describeContent(file.Content) +
					"; re-render and commit it",
			})
		}
	}
	return divergences, nil
}

// describeContent summarizes a blob as its content address and its length — deterministic, bounded,
// and safe to print, since a digest reveals nothing a log should not carry.
func describeContent(content []byte) string {
	return digestOf(content) + " (" + strconv.Itoa(len(content)) + " bytes)"
}

// validateEmission enforces the FileSet contract on a sorted emission: at least one file (an empty
// emission would let a drift check pass over a profile that was never written — the anti-false-green
// rule), a usable relative path per file, and no two files claiming the same path. Every failure is
// KindInternal: it is a defect in the renderer, not in the caller's input.
func validateEmission(files FileSet, target Target) error {
	if len(files) == 0 {
		return rendererFault("renderer for " + target.String() + " emitted no files; an empty emission " +
			"would make the drift check vacuous, so it is refused")
	}
	for i := range files {
		if unusablePath(files[i].Path) {
			return rendererFault("renderer for " + target.String() + " emitted the unusable path " +
				strconv.Quote(files[i].Path) + "; a path must be relative, slash-separated and free of . or .. elements")
		}
		if i > 0 && files[i].Path == files[i-1].Path {
			return rendererFault("renderer for " + target.String() + " emitted the path " +
				strconv.Quote(files[i].Path) + " twice; one path, one file")
		}
	}
	return nil
}

// unusablePath reports whether p cannot be written under a repository root. The emission is written
// to disk by the caller, so an absolute path or a ".." element is a directory escape this library
// refuses to hand out rather than trusting every consumer to re-check it.
func unusablePath(p string) bool {
	if p == "" || strings.HasPrefix(p, "/") || strings.Contains(p, `\`) {
		return true
	}
	for element := range strings.SplitSeq(p, "/") {
		if element == "" || element == "." || element == ".." {
			return true
		}
	}
	return false
}
