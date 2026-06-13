module github.com/gophersys/libs/go/orchestrator

go 1.26

require (
	github.com/gophersys/libs/go/agentsession v0.0.0
	github.com/gophersys/libs/go/dependencies v0.0.0
	github.com/gophersys/libs/go/errors v0.0.0
	github.com/gophersys/libs/go/secrets v0.0.0
	github.com/gophersys/libs/go/workspaceprovider v0.0.0
)

replace (
	github.com/gophersys/libs/go/agentsession v0.0.0 => ../agentsession
	github.com/gophersys/libs/go/dependencies v0.0.0 => ../dependencies
	github.com/gophersys/libs/go/errors v0.0.0 => ../errors
	github.com/gophersys/libs/go/secrets v0.0.0 => ../secrets
	github.com/gophersys/libs/go/testing v0.0.0 => ../testing
	github.com/gophersys/libs/go/workspaceprovider v0.0.0 => ../workspaceprovider
)
