# Engineering

The repository has one workflow boundary:

```text
host:      devcontainer cloud
container: nx <verb> <project> [-c <configuration>]
```

Nx owns project discovery, dependencies, caching, affected analysis, and
parallelism. Project targets may call small scripts or compiled tools, but those
implementations are not separate user interfaces.

Add structure only when real code requires it. A new application, library, tool,
or deployment unit begins as an Nx project with explicit inputs, outputs,
dependencies, and the smallest useful targets.
