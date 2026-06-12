package corpus

import (
	"sort"
	"strings"

	"github.com/gophersys/eden/tools/documentvalidator/internal/projection"
)

// ingest registers one projected document's identifiers, link edges, and (for a
// specification) its mandatory citations into the corpus.
func (c *Corpus) ingest(d *projection.Document) {
	meta, _ := d.Projection["meta"].(map[string]any)
	docType, _ := stringField(meta, "type")
	docID, _ := stringField(meta, "id")

	// Register the document id itself so links may resolve to it (e.g. an ADR or
	// spec cited by another document, or a supersedes target).
	if docID != "" {
		c.define(&Item{
			ID:         docID,
			DefinedIn:  d.Path,
			IsDocument: true,
			Rank:       c.docTypeRank[docType],
			Tier:       documentTypeRank[docType].tier,
		})
	}

	// Document-level link edges live under meta.links.
	c.ingestLinks(docID, d.Path, meta["links"])

	// Walk the data block for body item ids and their per-item links.
	if data, ok := d.Projection["data"].(map[string]any); ok {
		c.ingestData(docType, d.Path, data)
	}
}

// ingestData registers the item ids a document body defines (personas,
// requirements, workflows, entities, invariants, components, contracts, work
// packages) and their per-item link edges, and captures a specification's
// work_package / contract citations.
func (c *Corpus) ingestData(docType, path string, data map[string]any) {
	// Specification: a single object with work_package + contract cites (T4).
	if docType == "specification" {
		c.Specs = append(c.Specs, SpecCite{
			DocID:       documentIDForPath(c, path),
			Path:        path,
			WorkPackage: stringOrEmpty(data["work_package"]),
			Contract:    stringOrEmpty(data["contract"]),
		})
	}

	// product-charter defines personas under data.personas.
	c.ingestItemArray(path, data["personas"])
	// registry catalogues use data.items (requirements, user-workflows).
	c.ingestItemArray(path, data["items"])
	// domain-model uses data.entities and data.invariants.
	c.ingestItemArray(path, data["entities"])
	c.ingestItemArray(path, data["invariants"])
	// system-design uses data.components.
	c.ingestItemArray(path, data["components"])
	// service-contracts uses data.contracts.
	c.ingestItemArray(path, data["contracts"])
	// implementation-plan uses data.packages.
	c.ingestItemArray(path, data["packages"])
}

// ingestItemArray registers each element of an item array that carries an `id`
// of the item-id grammar, along with its per-item `links`.
func (c *Corpus) ingestItemArray(path string, raw any) {
	arr, ok := raw.([]any)
	if !ok {
		return
	}
	for _, elem := range arr {
		obj, ok := elem.(map[string]any)
		if !ok {
			continue
		}
		id := stringOrEmpty(obj["id"])
		prefix := prefixOf(id)
		if prefix == "" {
			continue
		}
		kind := prefixKind[prefix]
		item := &Item{
			ID:        id,
			Prefix:    prefix,
			DefinedIn: path,
			Rank:      kind.rank,
			Tier:      kind.tier,
		}
		if prefix == "REQ" {
			item.Priority = stringOrEmpty(obj["priority"])
		}
		c.define(item)
		c.ingestLinks(id, path, obj["links"])
	}
}

// ingestLinks appends one Edge per typed reference found in a links object.
// Edges are recorded in a stable order (link types sorted, then references in
// declaration order) so diagnostics are deterministic.
func (c *Corpus) ingestLinks(from, path string, raw any) {
	links, ok := raw.(map[string]any)
	if !ok {
		return
	}
	types := make([]string, 0, len(links))
	for t := range links {
		types = append(types, t)
	}
	sort.Strings(types)
	for _, t := range types {
		switch v := links[t].(type) {
		case []any:
			for _, ref := range v {
				if s := stringOrEmpty(ref); s != "" {
					c.Edges = append(c.Edges, Edge{From: from, FromPath: path, Type: t, To: s})
				}
			}
		case string:
			// supersedes is a scalar document id.
			c.Edges = append(c.Edges, Edge{From: from, FromPath: path, Type: t, To: v})
		}
	}
}

// define records an item, tracking duplicate ids for T5. The first definition of
// an id wins; later definitions are recorded as duplicates.
func (c *Corpus) define(item *Item) {
	if existing, ok := c.Items[item.ID]; ok {
		// A document id and a same-named item should not collide in practice;
		// either way the second definition is the duplicate. Keep the first.
		_ = existing
		c.Duplicates = append(c.Duplicates, duplicate{id: item.ID, path: item.DefinedIn})
		return
	}
	c.Items[item.ID] = item
}

// prefixOf returns the uppercase item-id prefix (the run of letters before the
// first hyphen) when the id matches the item-id grammar PREFIX-NNNN, or "".
func prefixOf(id string) string {
	dash := strings.IndexByte(id, '-')
	if dash <= 0 {
		return ""
	}
	prefix := id[:dash]
	for _, r := range prefix {
		if r < 'A' || r > 'Z' {
			return ""
		}
	}
	if _, ok := prefixKind[prefix]; !ok {
		return ""
	}
	// The remainder must be exactly four digits.
	rest := id[dash+1:]
	if len(rest) != 4 {
		return ""
	}
	for _, r := range rest {
		if r < '0' || r > '9' {
			return ""
		}
	}
	return prefix
}

// documentIDForPath finds the document id already registered for a path, used to
// attribute a spec citation to its document id for diagnostics.
func documentIDForPath(c *Corpus, path string) string {
	for id, item := range c.Items {
		if item.IsDocument && item.DefinedIn == path {
			return id
		}
	}
	return ""
}

func stringField(m map[string]any, key string) (string, bool) {
	if m == nil {
		return "", false
	}
	s, ok := m[key].(string)
	return s, ok
}

func stringOrEmpty(v any) string {
	s, _ := v.(string)
	return s
}
