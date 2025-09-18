module bitbucket.org/corekinect/concord

go 1.21

toolchain go1.23.4

require (
	github.com/emicklei/proto v1.13.2
	google.golang.org/grpc v1.65.0
	google.golang.org/protobuf v1.36.5
)

// Development tools
require (
	golang.org/x/tools v0.26.0 // gopls
	github.com/go-delve/delve v1.25.0 // dlv debugger
	honnef.co/go/tools v0.4.6 // staticcheck
	google.golang.org/protobuf/cmd/protoc-gen-go v1.36.5 // protoc-gen-go
	google.golang.org/grpc/cmd/protoc-gen-go-grpc v1.65.0 // protoc-gen-go-grpc
)

require (
	golang.org/x/net v0.26.0 // indirect
	golang.org/x/sys v0.21.0 // indirect
	golang.org/x/text v0.16.0 // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20240604185151-ef581f913117 // indirect
)
