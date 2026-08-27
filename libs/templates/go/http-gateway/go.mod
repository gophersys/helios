// Module github.com/gophersys/libs/templates/go/http-gateway — the http-gateway
// application TEMPLATE (ADR-0023): an OpenAPI-first, sqlc/pgx HTTP service that assembles the
// shared Eden Go libraries. The unpublished v0.0.0 sibling libraries resolve through the
// monorepo go.work (NO module-level replace here — the workspace owns resolution).
module github.com/gophersys/libs/templates/go/http-gateway

go 1.26

require (
	github.com/google/uuid v1.6.0
	github.com/gophersys/libs/go/configuration v0.0.0
	github.com/gophersys/libs/go/edenhttp v0.0.0
	github.com/gophersys/libs/go/errors v0.0.0
	github.com/gophersys/libs/go/observability v0.0.0
	github.com/gophersys/libs/go/orchestrator v0.0.0
	github.com/gophersys/libs/go/secrets v0.0.0
	github.com/jackc/pgx/v5 v5.7.6
)

require (
	github.com/cenkalti/backoff/v4 v4.3.0 // indirect
	github.com/go-jose/go-jose/v4 v4.1.4 // indirect
	github.com/gophersys/libs/go/agentsession v0.0.0 // indirect
	github.com/gophersys/libs/go/dependencies v0.0.0 // indirect
	github.com/gophersys/libs/go/workspaceprovider v0.0.0 // indirect
	github.com/hashicorp/errwrap v1.1.0 // indirect
	github.com/hashicorp/go-cleanhttp v0.5.2 // indirect
	github.com/hashicorp/go-multierror v1.1.1 // indirect
	github.com/hashicorp/go-retryablehttp v0.7.8 // indirect
	github.com/hashicorp/go-rootcerts v1.0.2 // indirect
	github.com/hashicorp/go-secure-stdlib/parseutil v0.2.0 // indirect
	github.com/hashicorp/go-secure-stdlib/strutil v0.1.2 // indirect
	github.com/hashicorp/go-sockaddr v1.0.7 // indirect
	github.com/hashicorp/hcl v1.0.1-vault-7 // indirect
	github.com/hashicorp/vault/api v1.23.0 // indirect
	github.com/jackc/pgpassfile v1.0.0 // indirect
	github.com/jackc/pgservicefile v0.0.0-20240606120523-5a60cdf6a761 // indirect
	github.com/jackc/puddle/v2 v2.2.2 // indirect
	github.com/mitchellh/go-homedir v1.1.0 // indirect
	github.com/mitchellh/mapstructure v1.5.0 // indirect
	github.com/ryanuber/go-glob v1.0.0 // indirect
	golang.org/x/crypto v0.52.0 // indirect
	golang.org/x/net v0.55.0 // indirect
	golang.org/x/sync v0.21.0 // indirect
	golang.org/x/text v0.37.0 // indirect
	golang.org/x/time v0.15.0 // indirect
)

