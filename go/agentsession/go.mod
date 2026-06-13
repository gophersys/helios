module github.com/gophersys/libs/go/agentsession

go 1.26

require (
	github.com/gophersys/libs/go/errors v0.0.0
	github.com/gophersys/libs/go/secrets v0.0.0
)

replace (
	github.com/gophersys/libs/go/errors v0.0.0 => ../errors
	github.com/gophersys/libs/go/secrets v0.0.0 => ../secrets
)
