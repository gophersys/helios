# MTIB MCP Server

MCP (Model Context Protocol) server that exposes MTIB V2 embedded test bench operations as tools for MCP-compatible clients. Enables AI-assisted firmware development, debugging, and hardware testing.

Upstream: [MateoSegura/mtib-mcp-server](https://github.com/MateoSegura/mtib-mcp-server)

## What it does

Connects to a running MTIB V2 gRPC server and exposes 22 MCP tools organized into categories:

| Category | Tools |
|----------|-------|
| Discovery | `mtib_health_check`, `mtib_list_targets` |
| Flash | `mtib_flash`, `mtib_reset` |
| Debug | `mtib_debug_connect`, `_disconnect`, `_status`, `_control`, `_backtrace`, `_memory`, `_breakpoint` |
| Serial | `mtib_uart_open`, `_read`, `_close`, `mtib_zephyr_shell`, `_logs_open`, `_logs_read`, `_logs_close` |
| Power | `mtib_power_measure`, `mtib_power_control` |
| Testing | `mtib_twister_run` |
| Bus I/O | `mtib_i2c_scan`, `mtib_i2c_transfer` |

## Prerequisites

- Python >= 3.10
- A running MTIB V2 gRPC server (real hardware or mock)

## Setup

```bash
cd apps/edge/mtib-mcp-server

# Install dependencies
pip install -e ".[dev]"

# Sync proto stubs from the monorepo (only needed after proto changes)
./sync_proto.sh
```

## Running

### With real hardware

Set `MTIB_HOST` and `MTIB_PORT` to point at the MTIB server, then run:

```bash
MTIB_HOST=192.168.1.100 MTIB_PORT=50054 mtib-mcp
```

Or configure in your MCP client settings (e.g. `mcp_config.json`):

```json
{
  "mcpServers": {
    "mtib": {
      "command": "mtib-mcp",
      "env": {
        "MTIB_HOST": "192.168.1.100",
        "MTIB_PORT": "50054"
      }
    }
  }
}
```

### Default connection

Without environment variables, connects to `localhost:50054`.

## Running tests

Tests use a mock gRPC server that implements all 71 RPCs with realistic responses.

```bash
cd apps/edge/mtib-mcp-server
pytest tests/ -v
```

The mock server starts automatically as a pytest fixture on a random port.

## Proto sync

The proto stubs (`src/mtib_mcp/proto/mtib_v2_pb2*.py`) are copied from `libs/protocols/mtib_v2/`. After regenerating protos in the monorepo, run:

```bash
./sync_proto.sh
```

This copies the files and patches the import paths for the MCP server's package structure.
