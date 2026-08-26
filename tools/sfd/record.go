// Package main implements sfd, the software-first-design catalog tool.
//
// The core is a library of pure transforms: a Zephyr tree in, typed records
// out. The CLI in main.go is a thin shell. Eden imports the library or
// shells the CLI; the YAML records are the API.
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"
)

// Provenance pins a record to the exact tree it was extracted from.
type Provenance struct {
	ZephyrSHA string `yaml:"zephyr_sha"`
	Extracted string `yaml:"extracted"` // date, YYYY-MM-DD
	Tool      string `yaml:"tool"`
}

// BindingRef is one devicetree binding that matched a compatible.
type BindingRef struct {
	Path  string `yaml:"path"`             // relative to the zephyr root
	OnBus string `yaml:"on_bus,omitempty"` // i2c, spi, ... empty = bus-less
	Class string `yaml:"class"`            // subdir under dts/bindings
}

// ComponentRecord is the catalog entry for one external component,
// identified by its Zephyr compatible string. Part numbers are a LATE
// binding: the field exists, stays empty until P4, and is never written by
// extraction.
type ComponentRecord struct {
	Schema      string       `yaml:"schema"` // sfd.component/v0
	Compatible  string       `yaml:"compatible"`
	Class       string       `yaml:"class"`
	Buses       []string     `yaml:"buses"`
	Bindings    []BindingRef `yaml:"bindings"`
	Drivers     []string     `yaml:"drivers"`      // dirs under drivers/
	ExercisedBy []string     `yaml:"exercised_by"` // samples/tests/boards refs
	Depth       string       `yaml:"depth"`        // D1 sourced, D2 has driver
	PartNumbers []string     `yaml:"part_numbers"` // empty until P4, per product
	Provenance  Provenance   `yaml:"provenance"`
}

// PowerState is one zephyr,power-state node extracted from a SoC dtsi.
type PowerState struct {
	Name           string `yaml:"name"`
	MinResidencyUS int    `yaml:"min_residency_us,omitempty"`
	ExitLatencyUS  int    `yaml:"exit_latency_us,omitempty"`
}

// SocRecord is the catalog entry for one SoC, identified by its Zephyr SoC
// name (soc.yml), never by an orderable part number.
type SocRecord struct {
	Schema      string       `yaml:"schema"` // sfd.soc/v0
	Name        string       `yaml:"name"`
	Family      string       `yaml:"family"`
	Series      string       `yaml:"series,omitempty"`
	SocYML      string       `yaml:"soc_yml"` // path that declared it
	DtsiFiles   []string     `yaml:"dtsi_files"`
	Compatibles []string     `yaml:"compatibles"` // declared peripheral inventory
	PowerStates []PowerState `yaml:"power_states"`
	Boards      []string     `yaml:"boards"` // in-tree boards declaring this SoC
	Depth       string       `yaml:"depth"`  // D1: declared inventory only
	PartNumbers []string     `yaml:"part_numbers"` // empty until P4
	Provenance  Provenance   `yaml:"provenance"`
}

// componentPath returns the catalog file for a compatible.
func componentPath(catalogDir, compatible string) string {
	return filepath.Join(catalogDir, "components", safeName(compatible)+".yaml")
}

// socPath returns the catalog file for a SoC name.
func socPath(catalogDir, name string) string {
	return filepath.Join(catalogDir, "socs", safeName(name)+".yaml")
}

// safeName maps an identifier to a filesystem-safe file stem.
func safeName(id string) string {
	return strings.NewReplacer("/", "_").Replace(id)
}

// writeRecord marshals a record to path, refusing to overwrite unless force.
func writeRecord(path string, rec any, force bool) error {
	if !force {
		if _, err := os.Stat(path); err == nil {
			return fmt.Errorf("%s exists; pass --force to overwrite", path)
		}
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	out, err := yaml.Marshal(rec)
	if err != nil {
		return err
	}
	return os.WriteFile(path, out, 0o644)
}
