package persistence

import (
	"context"
	"embed"
	"sort"
	"strings"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"
)

// migrationsFS embeds the numbered goose-style migrations so the binary carries its own schema — no
// external migration tool at runtime. The startup migrate path (Migrate) and the integration lane run
// the SAME embedded files, so what ships is what is tested.
//
//go:embed migrations/*.sql
var migrationsFS embed.FS

// Migrate applies every embedded migration's +goose Up section to the database in filename order. It
// is the IOTEA-style startup step: the migrations are idempotent (CREATE ... IF NOT EXISTS), so it
// runs safely on every boot, and the composition root calls it before serving. It does NOT seed data
// — the composition root seeds the default user through Users().EnsureDefault after Migrate succeeds,
// so the schema step and the data step stay separable.
func (p *Persistence) Migrate(ctx context.Context) error {
	if p == nil || p.pool == nil {
		return errors.New(errors.KindInvalid, "persistence: Migrate on a closed store")
	}
	names, err := migrationNames()
	if err != nil {
		return err
	}
	for _, name := range names {
		raw, readErr := migrationsFS.ReadFile("migrations/" + name)
		if readErr != nil {
			return errors.Wrap(errors.KindInternal, "persistence: read migration "+name, readErr)
		}
		up := gooseUp(string(raw))
		if up == "" {
			return errors.New(errors.KindInternal, "persistence: migration "+name+" has no +goose Up section")
		}
		if _, execErr := p.pool.Exec(ctx, up); execErr != nil {
			return errors.Wrap(errors.KindUnavailable, "persistence: apply migration "+name, execErr)
		}
	}
	p.observability.Log(ctx, observability.SeverityInfo, "persistence: migrations applied",
		observability.String("migrations", strings.Join(names, ",")))
	return nil
}

// migrationNames lists the embedded *.sql migrations in lexicographic (== numbered) order, so the
// numbered prefix is the apply order.
func migrationNames() ([]string, error) {
	entries, err := migrationsFS.ReadDir("migrations")
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "persistence: read embedded migrations", err)
	}
	names := make([]string, 0, len(entries))
	for _, entry := range entries {
		if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".sql") {
			names = append(names, entry.Name())
		}
	}
	sort.Strings(names)
	return names, nil
}

// gooseUp extracts the SQL between "-- +goose Up" and "-- +goose Down" — the apply section. It is the
// minimal goose-directive reader the embedded migrations need (plain DDL, no StatementBegin/End
// blocks); the migration is authored to keep its Up section self-contained.
func gooseUp(raw string) string {
	const upMarker, downMarker = "-- +goose Up", "-- +goose Down"
	start := strings.Index(raw, upMarker)
	if start < 0 {
		return ""
	}
	body := raw[start+len(upMarker):]
	if end := strings.Index(body, downMarker); end >= 0 {
		body = body[:end]
	}
	return strings.TrimSpace(body)
}
