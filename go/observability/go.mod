module github.com/gophersys/libs/go/observability

go 1.26

replace (
	github.com/gophersys/libs/go/dependencies v0.0.0 => ../dependencies
	github.com/gophersys/libs/go/testing v0.0.0 => ../testing
)

require (
	github.com/gophersys/libs/go/testing v0.0.0
	go.uber.org/goleak v1.3.0
	pgregory.net/rapid v1.3.0
)

require github.com/gophersys/libs/go/dependencies v0.0.0 // indirect
