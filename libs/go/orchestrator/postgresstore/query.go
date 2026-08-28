package postgresstore

import (
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/orchestrator"
)

// buildWhere renders the SQL WHERE clause + positional args for a Filter. It mirrors the
// in-memory store's matchesFilter EXACTLY (tenant, template name/version, OnlyActive, statuses)
// so the two bindings are behaviorally identical — the closure the conformance suite demands.
// Each filtered key is a promoted column, so the predicate is an index-assisted SQL test rather
// than an in-memory scan.
//
//nolint:nonamedreturns // the named results document the (whereClause, positionalArgs) pair the caller splices into the query.
func buildWhere(filter *orchestrator.Filter) (whereClause string, positionalArgs []any) {
	var (
		clauses []string
		args    []any
	)
	add := func(columnExpression string, value any) {
		args = append(args, value)
		clauses = append(clauses, columnExpression+"=$"+strconv.Itoa(len(args)))
	}
	if !filter.Tenant.IsZero() {
		add("org_id", filter.Tenant.OrganizationID)
		add("project_id", filter.Tenant.ProjectID)
	}
	if filter.Template.Name != "" {
		add("template_name", filter.Template.Name)
	}
	if filter.Template.Version != "" {
		add("template_version", filter.Template.Version)
	}
	if filter.OnlyActive {
		clauses = append(clauses, "terminal = false")
	}
	if len(filter.Statuses) > 0 {
		codes := make([]int16, len(filter.Statuses))
		for i, status := range filter.Statuses {
			codes[i] = int16(status)
		}
		args = append(args, codes)
		clauses = append(clauses, "status = ANY($"+strconv.Itoa(len(args))+")")
	}
	if len(clauses) == 0 {
		return "", nil
	}
	return " WHERE " + strings.Join(clauses, " AND "), args
}

// paginate slices the matched set by the filter's Cursor/Limit and returns the page plus the
// next cursor. It is a byte-for-byte copy of the in-memory store's offset-cursor semantics (one
// behavior, asserted by the SAME conformance cases) so the Postgres binding is substitutable:
// the Cursor is the id of the last item of the previous page; Limit<=0 means "the rest".
func paginate(matched []orchestrator.Agent, filter *orchestrator.Filter) orchestrator.Page {
	start := 0
	if filter.Cursor != "" {
		for i := range matched {
			if string(matched[i].ID) == filter.Cursor {
				start = i + 1
				break
			}
		}
	}
	if start > len(matched) {
		start = len(matched)
	}
	limit := filter.Limit
	if limit <= 0 || start+limit > len(matched) {
		limit = len(matched) - start
	}
	page := orchestrator.Page{Agents: append([]orchestrator.Agent(nil), matched[start:start+limit]...)}
	if start+limit < len(matched) && limit > 0 {
		page.Next = string(matched[start+limit-1].ID)
	}
	return page
}
