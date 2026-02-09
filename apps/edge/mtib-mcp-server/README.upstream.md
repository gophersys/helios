# MTIB MCP Server

MCP (Model Context Protocol) server that wraps the MTIB V2 gRPC API, enabling MCP-compatible clients to interact with embedded hardware test benches.

## Setup

```bash
# Install
pip install -e .

# Regenerate proto stubs (if mtib_v2.proto changes)
./generate_proto.sh
```

## MCP Client Configuration

Add to your MCP client config (`.mcp.json`):

```json
{
  "mcpServers": {
    "mtib": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "mtib_mcp.server"],
      "env": {
        "MTIB_HOST": "192.168.1.100",
        "MTIB_PORT": "50054"
      }
    }
  }
}
```

## Available tools

| Tool | Description |
|------|-------------|
| **Discovery** | |
| `mtib_health_check` | Check connectivity, version, capabilities |
| `mtib_list_targets` | List target devices and debug probes |
| **Flash** | |
| `mtib_flash` | Flash firmware to a target |
| `mtib_reset` | Reset a target device |
| **Debug** | |
| `mtib_debug_connect` | Open a debug session (returns session_id) |
| `mtib_debug_disconnect` | Close a debug session |
| `mtib_debug_status` | Get halt reason, PC, registers |
| `mtib_debug_control` | Halt, resume, step, step over |
| `mtib_debug_backtrace` | Get stack trace |
| `mtib_debug_memory` | Read/write target memory |
| `mtib_debug_breakpoint` | Set/clear breakpoints |
| **Serial & Logs** | |
| `mtib_uart_open` | Open UART and start background buffering |
| `mtib_uart_read` | Read buffered lines (cursor-based, no data loss) |
| `mtib_uart_close` | Close UART stream |
| `mtib_zephyr_shell` | Execute a Zephyr shell command |
| `mtib_zephyr_logs_open` | Start buffering Zephyr log entries |
| `mtib_zephyr_logs_read` | Read buffered log entries (cursor-based) |
| `mtib_zephyr_logs_close` | Close log stream |
| **Power** | |
| `mtib_power_measure` | Measure power over a duration |
| `mtib_power_control` | Enable/disable/query power channels |
| **Testing** | |
| `mtib_twister_run` | Run Twister test suite |
| **Bus I/O** | |
| `mtib_i2c_scan` | Scan I2C bus |
| `mtib_i2c_transfer` | Read/write I2C device |

### Streaming data guarantee

UART and Zephyr log streams use persistent background buffers.  When you call
`mtib_uart_open`, a background task continuously drains the gRPC stream into a
5,000-entry ring buffer.  Each entry gets a monotonic sequence number (cursor).

```
mtib_uart_open(target_id="nrf52840_dk")  →  { stream_key, status: "buffering" }
mtib_uart_read(stream_key, cursor=0)     →  { lines: [...], cursor: 347 }
# ... time passes, DUT keeps printing ...
mtib_uart_read(stream_key, cursor=347)   →  { lines: [...], cursor: 512 }
mtib_uart_close(stream_key)
```

As long as the ring buffer doesn't wrap (5,000 entries by default), **no data is
lost between reads**.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MTIB_HOST` | `localhost` | MTIB gRPC server hostname |
| `MTIB_PORT` | `50054` | MTIB gRPC server port |
