module github.com/gophersys/libs/go/gitrepository

go 1.26

require (
	github.com/gophersys/libs/go/errors v0.0.0
	github.com/gophersys/libs/go/secrets v0.0.0
	github.com/gophersys/libs/go/testing v0.0.0
	go.uber.org/goleak v1.3.0
	golang.org/x/sync v0.21.0
	pgregory.net/rapid v1.3.0
)

require github.com/gophersys/libs/go/dependencies v0.0.0 // indirect

replace (
	github.com/gophersys/libs/go/dependencies v0.0.0 => ../dependencies
	github.com/gophersys/libs/go/envelope v0.0.0 => ../envelope
	github.com/gophersys/libs/go/errors v0.0.0 => ../errors
	github.com/gophersys/libs/go/secrets v0.0.0 => ../secrets
	github.com/gophersys/libs/go/testing v0.0.0 => ../testing
)
