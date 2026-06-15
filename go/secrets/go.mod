module github.com/gophersys/libs/go/secrets

go 1.26

require (
	github.com/gophersys/libs/go/errors v0.0.0
	github.com/hashicorp/vault/api v1.23.0
)

require (
	github.com/cenkalti/backoff/v4 v4.3.0 // indirect
	github.com/fatih/color v1.19.0 // indirect
	github.com/go-jose/go-jose/v4 v4.1.4 // indirect
	github.com/gophersys/libs/go/dependencies v0.0.0 // indirect
	github.com/hashicorp/errwrap v1.1.0 // indirect
	github.com/hashicorp/go-cleanhttp v0.5.2 // indirect
	github.com/hashicorp/go-multierror v1.1.1 // indirect
	github.com/hashicorp/go-retryablehttp v0.7.8 // indirect
	github.com/hashicorp/go-rootcerts v1.0.2 // indirect
	github.com/hashicorp/go-secure-stdlib/parseutil v0.2.0 // indirect
	github.com/hashicorp/go-secure-stdlib/strutil v0.1.2 // indirect
	github.com/hashicorp/go-sockaddr v1.0.7 // indirect
	github.com/hashicorp/hcl v1.0.1-vault-7 // indirect
	github.com/mitchellh/go-homedir v1.1.0 // indirect
	github.com/mitchellh/mapstructure v1.5.0 // indirect
	github.com/ryanuber/go-glob v1.0.0 // indirect
	golang.org/x/net v0.55.0 // indirect
	golang.org/x/text v0.37.0 // indirect
	golang.org/x/time v0.15.0 // indirect
)

// Test-only dependencies (the ADR-0020 test-taxonomy block): goleak (dimension b, leak),
// rapid (dimension a, property), and the testing pattern lib (dimension c, AssertLifecycle /
// LifecycleProbe). depguard's `test-taxonomy` rule permits these in *_test.go only.
require (
	github.com/gophersys/libs/go/testing v0.0.0
	go.uber.org/goleak v1.3.0
	pgregory.net/rapid v1.3.0
)

replace (
	github.com/gophersys/libs/go/dependencies v0.0.0 => ../dependencies
	github.com/gophersys/libs/go/errors v0.0.0 => ../errors
	github.com/gophersys/libs/go/testing v0.0.0 => ../testing
)
