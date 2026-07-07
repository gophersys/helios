module github.com/gophersys/eden/apps/agentgateway

go 1.26

require (
	github.com/gophersys/libs/go/agentruntime v0.0.0
	github.com/gophersys/libs/go/agentsession v0.0.0
	github.com/gophersys/libs/go/codeinsight v0.0.0
	github.com/gophersys/libs/go/dependencies v0.0.0
	github.com/gophersys/libs/go/edenhttp v0.0.0
	github.com/gophersys/libs/go/errors v0.0.0
	github.com/gophersys/libs/go/forge v0.0.0
	github.com/gophersys/libs/go/gitrepository v0.0.0
	github.com/gophersys/libs/go/observability v0.0.0
	github.com/gophersys/libs/go/orchestrator v0.0.0
	github.com/gophersys/libs/go/secrets v0.0.0
	github.com/gophersys/libs/go/workspaceprovider v0.0.0
	github.com/jackc/pgx/v5 v5.7.6
	github.com/nats-io/nats-server/v2 v2.14.2
	github.com/nats-io/nats.go v1.52.0
	k8s.io/apimachinery v0.34.1
	k8s.io/client-go v0.34.1
)

require (
	github.com/jackc/pgpassfile v1.0.0 // indirect
	github.com/jackc/pgservicefile v0.0.0-20240606120523-5a60cdf6a761 // indirect
	github.com/jackc/puddle/v2 v2.2.2 // indirect
	github.com/klauspost/compress v1.18.6 // indirect
	github.com/nats-io/nkeys v0.4.16 // indirect
	github.com/nats-io/nuid v1.0.1 // indirect
	golang.org/x/crypto v0.52.0 // indirect
	golang.org/x/sync v0.21.0 // indirect
	golang.org/x/sys v0.45.0 // indirect
	golang.org/x/text v0.37.0 // indirect
)
