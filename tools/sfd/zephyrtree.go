package main

// Pure queries over a Zephyr source tree. Every function takes the tree
// root explicitly and returns data; nothing here writes, prompts, or reads
// global state. This is the Eden seam.

import (
	"bufio"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"gopkg.in/yaml.v3"
)

// ZephyrSHA returns the tree's HEAD commit. The tree must be its OWN git
// checkout: a plain directory inside some other repository would silently
// yield the enclosing repository's SHA — wrong provenance, which is worse
// than none.
func ZephyrSHA(root string) (string, error) {
	abs, err := filepath.Abs(root)
	if err != nil {
		return "", err
	}
	top, err := exec.Command("git", "-C", root, "rev-parse", "--show-toplevel").Output()
	if err != nil {
		return "", fmt.Errorf("cannot resolve git toplevel of %s: %w (provenance is mandatory)", root, err)
	}
	topAbs, err := filepath.EvalSymlinks(strings.TrimSpace(string(top)))
	if err != nil {
		return "", err
	}
	absReal, err := filepath.EvalSymlinks(abs)
	if err != nil {
		return "", err
	}
	if topAbs != absReal {
		return "", fmt.Errorf("%s is not its own git checkout (toplevel is %s) — refusing to cite a foreign SHA", root, topAbs)
	}
	out, err := exec.Command("git", "-C", root, "rev-parse", "HEAD").Output()
	if err != nil {
		return "", fmt.Errorf("cannot resolve HEAD of %s: %w (provenance is mandatory)", root, err)
	}
	return strings.TrimSpace(string(out)), nil
}

// bindingDoc is the subset of a devicetree binding YAML we read. Include
// is `any`: bindings write it as a string, a list of strings, or a list of
// maps with a name key.
type bindingDoc struct {
	Compatible string `yaml:"compatible"`
	OnBus      string `yaml:"on-bus"`
	Include    any    `yaml:"include"`
}

// includeNames flattens a binding's include field into file names.
func (b bindingDoc) includeNames() []string {
	var out []string
	switch v := b.Include.(type) {
	case string:
		out = append(out, v)
	case []any:
		for _, item := range v {
			switch it := item.(type) {
			case string:
				out = append(out, it)
			case map[string]any:
				if n, _ := it["name"].(string); n != "" {
					out = append(out, n)
				}
			}
		}
	}
	return out
}

// resolveOnBus returns the binding's bus, following includes recursively
// when the file itself carries no `on-bus:`. Most device bindings get
// their bus this way (include: [i2c-device.yaml]); without resolution the
// extracted bus list reports empty and the record lies. Include names are
// unique across dts/bindings, so resolution is by basename index.
func resolveOnBus(doc bindingDoc, byName map[string]string, depth int) string {
	if doc.OnBus != "" || depth > 4 {
		return doc.OnBus
	}
	for _, name := range doc.includeNames() {
		path, ok := byName[name]
		if !ok {
			continue
		}
		raw, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		var inc bindingDoc
		if yaml.Unmarshal(raw, &inc) != nil {
			continue
		}
		if bus := resolveOnBus(inc, byName, depth+1); bus != "" {
			return bus
		}
	}
	return ""
}

// FindBindings walks dts/bindings and returns every binding whose
// `compatible:` equals the given compatible string.
func FindBindings(root, compatible string) ([]BindingRef, error) {
	base := filepath.Join(root, "dts", "bindings")
	if _, err := os.Stat(base); err != nil {
		return nil, fmt.Errorf("no dts/bindings under %s: %w", root, err)
	}
	// One walk builds both the match list and the name index that include
	// resolution needs (include names are unique basenames by convention).
	byName := map[string]string{}
	type match struct {
		doc  bindingDoc
		path string
	}
	var matches []match
	err := filepath.WalkDir(base, func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() || !strings.HasSuffix(path, ".yaml") {
			return err
		}
		byName[filepath.Base(path)] = path
		raw, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		var doc bindingDoc
		if yaml.Unmarshal(raw, &doc) != nil {
			return nil // not every yaml under bindings is a binding; skip unparseable
		}
		if doc.Compatible == compatible {
			matches = append(matches, match{doc, path})
		}
		return nil
	})
	var refs []BindingRef
	for _, m := range matches {
		rel, _ := filepath.Rel(root, m.path)
		class := "unknown"
		if parts := strings.Split(rel, string(filepath.Separator)); len(parts) > 3 {
			class = parts[2] // dts/bindings/<class>/...
		}
		refs = append(refs, BindingRef{Path: rel, OnBus: resolveOnBus(m.doc, byName, 0), Class: class})
	}
	sort.Slice(refs, func(i, j int) bool { return refs[i].Path < refs[j].Path })
	return refs, err
}

// FindDrivers returns the driver directories that declare
// DT_DRV_COMPAT <compatible-with-separators-as-underscores>.
func FindDrivers(root, compatible string) ([]string, error) {
	ident := strings.NewReplacer(",", "_", "-", "_", ".", "_").Replace(compatible)
	needle := regexp.MustCompile(`DT_DRV_COMPAT\s+` + regexp.QuoteMeta(ident) + `\b`)
	base := filepath.Join(root, "drivers")
	dirs := map[string]bool{}
	err := filepath.WalkDir(base, func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return err
		}
		switch filepath.Ext(path) {
		case ".c", ".h":
		default:
			return nil
		}
		raw, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		if needle.Match(raw) {
			rel, _ := filepath.Rel(root, filepath.Dir(path))
			dirs[rel] = true
		}
		return nil
	})
	var out []string
	for d := range dirs {
		out = append(out, d)
	}
	sort.Strings(out)
	return out, err
}

// FindExercisers returns files under samples/, tests/ and boards/ that
// reference the compatible in devicetree sources. Capped: the point is
// evidence that it is exercised, not an exhaustive census.
func FindExercisers(root, compatible string, cap int) ([]string, error) {
	var out []string
	for _, top := range []string{"samples", "tests", "boards"} {
		base := filepath.Join(root, top)
		err := filepath.WalkDir(base, func(path string, d fs.DirEntry, err error) error {
			if err != nil || d.IsDir() || len(out) >= cap {
				return err
			}
			switch filepath.Ext(path) {
			case ".dts", ".dtsi", ".overlay":
			default:
				return nil
			}
			raw, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			if strings.Contains(string(raw), compatible) {
				rel, _ := filepath.Rel(root, path)
				out = append(out, rel)
			}
			return nil
		})
		if err != nil && !os.IsNotExist(err) {
			return nil, err
		}
	}
	sort.Strings(out)
	return out, nil
}

// SocDecl is one SoC found in a soc.yml.
type SocDecl struct {
	Name   string
	Family string
	Series string
	SocYML string // path relative to root
}

// FindSoc walks soc/**/soc.yml (hardware model v2) for a SoC by name.
func FindSoc(root, name string) (*SocDecl, error) {
	base := filepath.Join(root, "soc")
	var found *SocDecl
	err := filepath.WalkDir(base, func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() || d.Name() != "soc.yml" || found != nil {
			return err
		}
		raw, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		var doc map[string]any
		if yaml.Unmarshal(raw, &doc) != nil {
			return nil
		}
		rel, _ := filepath.Rel(root, path)
		if decl := searchSocDoc(doc, name, rel); decl != nil {
			found = decl
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	if found == nil {
		return nil, fmt.Errorf("soc %q not declared in any soc/**/soc.yml under %s", name, root)
	}
	return found, nil
}

// searchSocDoc recursively walks a parsed soc.yml for socs entries,
// tracking the enclosing family/series names.
func searchSocDoc(node any, name, socYML string) *SocDecl {
	var walk func(node any, family, series string) *SocDecl
	walk = func(node any, family, series string) *SocDecl {
		m, ok := node.(map[string]any)
		if !ok {
			return nil
		}
		if n, _ := m["name"].(string); n != "" {
			if _, hasSocs := m["socs"]; hasSocs && family == "" {
				family = n
			} else if _, hasSocs := m["socs"]; hasSocs {
				series = n
			}
		}
		if socs, ok := m["socs"].([]any); ok {
			for _, s := range socs {
				sm, ok := s.(map[string]any)
				if !ok {
					continue
				}
				if sn, _ := sm["name"].(string); sn == name {
					return &SocDecl{Name: name, Family: family, Series: series, SocYML: socYML}
				}
			}
		}
		for _, key := range []string{"family", "series", "runners"} {
			if list, ok := m[key].([]any); ok {
				nextFamily, nextSeries := family, series
				if key == "series" {
					if n, _ := m["name"].(string); n != "" {
						nextFamily = n
					}
				}
				for _, item := range list {
					if hit := walk(item, nextFamily, nextSeries); hit != nil {
						return hit
					}
				}
			}
		}
		return nil
	}
	return walk(node, "", "")
}

// boardYML is the subset of a board.yml we read.
type boardYML struct {
	Board struct {
		Name string `yaml:"name"`
		Socs []struct {
			Name string `yaml:"name"`
		} `yaml:"socs"`
	} `yaml:"board"`
	Boards []struct {
		Name string `yaml:"name"`
		Socs []struct {
			Name string `yaml:"name"`
		} `yaml:"socs"`
	} `yaml:"boards"`
}

// FindBoardsForSoc returns the board directories (relative) whose board.yml
// declares the SoC.
func FindBoardsForSoc(root, socName string) ([]string, error) {
	base := filepath.Join(root, "boards")
	var out []string
	err := filepath.WalkDir(base, func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() || d.Name() != "board.yml" {
			return err
		}
		raw, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		var doc boardYML
		if yaml.Unmarshal(raw, &doc) != nil {
			return nil
		}
		match := false
		for _, s := range doc.Board.Socs {
			if s.Name == socName {
				match = true
			}
		}
		for _, b := range doc.Boards {
			for _, s := range b.Socs {
				if s.Name == socName {
					match = true
				}
			}
		}
		if match {
			rel, _ := filepath.Rel(root, filepath.Dir(path))
			out = append(out, rel)
		}
		return nil
	})
	sort.Strings(out)
	return out, err
}

// FindSocDtsi locates the dtsi files for a SoC. Two strategies, in order:
//  1. basename under dts/ contains the SoC name;
//  2. dtsi files included by the .dts of boards that declare the SoC.
//
// No hit is an ERROR that lists what was tried — never a silent empty.
func FindSocDtsi(root, socName string, boards []string) ([]string, error) {
	hits := map[string]bool{}

	// Strategy 1: name match under dts/.
	dtsBase := filepath.Join(root, "dts")
	_ = filepath.WalkDir(dtsBase, func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() || !strings.HasSuffix(path, ".dtsi") {
			return err
		}
		if strings.Contains(filepath.Base(path), socName) {
			rel, _ := filepath.Rel(root, path)
			hits[rel] = true
		}
		return nil
	})

	// Strategy 2: includes from the boards' .dts files.
	inc := regexp.MustCompile(`#include\s+[<"]([^">]+\.dtsi)[">]`)
	for _, b := range boards {
		entries, err := os.ReadDir(filepath.Join(root, b))
		if err != nil {
			continue
		}
		for _, e := range entries {
			if e.IsDir() || filepath.Ext(e.Name()) != ".dts" {
				continue
			}
			raw, err := os.ReadFile(filepath.Join(root, b, e.Name()))
			if err != nil {
				continue
			}
			for _, m := range inc.FindAllStringSubmatch(string(raw), -1) {
				// Resolve against the dts/ include roots.
				matches, _ := filepath.Glob(filepath.Join(dtsBase, "*", m[1]))
				more, _ := filepath.Glob(filepath.Join(dtsBase, "*", "*", m[1]))
				for _, hit := range append(matches, more...) {
					rel, _ := filepath.Rel(root, hit)
					hits[rel] = true
				}
			}
		}
	}

	if len(hits) == 0 {
		return nil, fmt.Errorf(
			"no dtsi found for soc %q: tried basename match under dts/ and includes of %d board(s) %v — pass --dtsi explicitly",
			socName, len(boards), boards)
	}
	var out []string
	for h := range hits {
		out = append(out, h)
	}
	sort.Strings(out)
	return out, nil
}

// expandIncludes resolves the dtsi include closure of the seed files.
// A SoC dtsi is often a thin wrapper whose peripherals live in an included
// family dtsi (nxp_rt1050.dtsi → nxp_rt10xx.dtsi: 1 vs 137 compatibles) —
// without the closure the extracted record silently lies. Resolution
// mirrors Zephyr's dts include roots: the including file's directory, then
// dts/<inc>, dts/*/<inc>, dts/*/*/<inc>. Cycle-safe via the seen set.
func expandIncludes(root string, seed []string) []string {
	inc := regexp.MustCompile(`#include\s+[<"]([^">]+\.dtsi)[">]`)
	dtsBase := filepath.Join(root, "dts")
	seen := map[string]bool{}
	var order []string
	var visit func(rel string)
	visit = func(rel string) {
		if seen[rel] {
			return
		}
		seen[rel] = true
		order = append(order, rel)
		raw, err := os.ReadFile(filepath.Join(root, rel))
		if err != nil {
			return
		}
		for _, m := range inc.FindAllStringSubmatch(string(raw), -1) {
			var candidates []string
			local := filepath.Join(filepath.Dir(rel), m[1])
			if _, err := os.Stat(filepath.Join(root, local)); err == nil {
				candidates = append(candidates, filepath.Join(root, local))
			}
			for _, pat := range []string{
				filepath.Join(dtsBase, m[1]),
				filepath.Join(dtsBase, "*", m[1]),
				filepath.Join(dtsBase, "*", "*", m[1]),
			} {
				hits, _ := filepath.Glob(pat)
				candidates = append(candidates, hits...)
			}
			for _, c := range candidates {
				if crel, err := filepath.Rel(root, c); err == nil {
					visit(crel)
				}
			}
		}
	}
	for _, s := range seed {
		visit(s)
	}
	return order
}

// DtsiInventory extracts the declared compatibles and power states from
// dtsi files AND their include closure. Text-level extraction,
// declared-not-supported: everything it returns is depth D1 by definition.
func DtsiInventory(root string, dtsiFiles []string) (compatibles []string, states []PowerState, err error) {
	dtsiFiles = expandIncludes(root, dtsiFiles)
	compatRe := regexp.MustCompile(`compatible\s*=\s*(.+);`)
	quoted := regexp.MustCompile(`"([^"]+)"`)
	nameRe := regexp.MustCompile(`power-state-name\s*=\s*"([^"]+)"`)
	resRe := regexp.MustCompile(`min-residency-us\s*=\s*<\s*(\d+)\s*>`)
	exitRe := regexp.MustCompile(`exit-latency-us\s*=\s*<\s*(\d+)\s*>`)

	seen := map[string]bool{}
	for _, f := range dtsiFiles {
		file, err := os.Open(filepath.Join(root, f))
		if err != nil {
			return nil, nil, err
		}
		var inPowerState bool
		var current PowerState
		flush := func() {
			if inPowerState && current.Name != "" {
				states = append(states, current)
			}
			inPowerState, current = false, PowerState{}
		}
		sc := bufio.NewScanner(file)
		for sc.Scan() {
			line := sc.Text()
			if m := compatRe.FindStringSubmatch(line); m != nil {
				for _, q := range quoted.FindAllStringSubmatch(m[1], -1) {
					if !seen[q[1]] {
						seen[q[1]] = true
						compatibles = append(compatibles, q[1])
					}
				}
				if strings.Contains(m[1], `"zephyr,power-state"`) {
					flush()
					inPowerState = true
				}
			}
			if inPowerState {
				if m := nameRe.FindStringSubmatch(line); m != nil {
					current.Name = m[1]
				}
				if m := resRe.FindStringSubmatch(line); m != nil {
					current.MinResidencyUS, _ = strconv.Atoi(m[1])
				}
				if m := exitRe.FindStringSubmatch(line); m != nil {
					current.ExitLatencyUS, _ = strconv.Atoi(m[1])
				}
				if strings.Contains(line, "};") {
					flush()
				}
			}
		}
		flush()
		file.Close()
		if err := sc.Err(); err != nil {
			return nil, nil, err
		}
	}
	sort.Strings(compatibles)
	return compatibles, states, nil
}
