package main

import (
	"encoding/json"
	"fmt"
	"io"

	"github.com/gophersys/eden/tools/documentvalidator/internal/corpus"
	"github.com/gophersys/eden/tools/documentvalidator/internal/projection"
)

// edge is the wire form of one link edge for the `links` command.
type edge struct {
	File string `json:"file"`
	From string `json:"from"`
	Type string `json:"type"`
	To   string `json:"to"`
}

// runLinks executes `documentvalidator links <dir> [--json]`, emitting the typed
// link-edge list (the derived corpus graph) without enforcing any rule.
func runLinks(args []string, stdout, stderr io.Writer) int {
	opts, err := parseArgs(args)
	if err != nil {
		fmt.Fprintf(stderr, "documentvalidator: %v\n", err)
		usage(stderr)
		return exitUsage
	}

	paths, err := walkDocuments(opts.dir)
	if err != nil {
		fmt.Fprintf(stderr, "documentvalidator: %v\n", err)
		return exitUsage
	}

	var docs []*projection.Document
	for _, path := range paths {
		doc, perr := projection.Project(path)
		if perr != nil {
			fmt.Fprintf(stderr, "documentvalidator: %v\n", perr)
			return exitUsage
		}
		docs = append(docs, doc)
	}

	c := corpus.Build(docs)
	edges := c.EdgeList()

	if opts.json {
		out := make([]edge, 0, len(edges))
		for _, e := range edges {
			out = append(out, edge{File: relPath(opts.dir, e.FromPath), From: e.From, Type: e.Type, To: e.To})
		}
		enc := json.NewEncoder(stdout)
		enc.SetIndent("", "  ")
		_ = enc.Encode(out)
		return exitClean
	}

	for _, e := range edges {
		fmt.Fprintf(stdout, "%s: %s --%s--> %s\n", relPath(opts.dir, e.FromPath), e.From, e.Type, e.To)
	}
	return exitClean
}
