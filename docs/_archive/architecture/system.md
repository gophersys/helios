# Concord System Architecture

> **Status:** Work-in-progress. This document captures the current state and intended direction of the Concord platform.

## Overview

Concord is a full-stack hardware testing platform for **manufacturing** and **validation** of embedded products. It orchestrates test execution across physical hardware nodes (MTIBs), manages firmware deployments, streams real-time results, and provides a web UI for operators.

The system runs on a Kubernetes (K3s) cluster with three tiers of nodes: server nodes for infrastructure, agent nodes for backend services and test runners, and edge nodes (MTIBs) for direct hardware interaction.

## Products

Concord supports multiple hardware products. Each product has its own firmware, test runners, and fixture configurations:

| Product | Description | Stage |
|---------|-------------|-------|
| **Sigma5** | Primary product line | Manufacturing + Validation |
| **Theta** | Newer product | Manufacturing |
| **Alpha** | Earlier product | Manufacturing |
| **ICLE** | Metering device | Validation |
| **IWSCK** | Firmware project | Firmware only |

## Cluster Topology

```
K3s HA Cluster (API: 10.4.45.10:6443)
|
+-- Server Nodes (Control Plane) x3
|   concordserver01-03 (.11-.13)
|   Runs: etcd, API server, CoreDNS, Traefik, metrics-server, ServiceLB
|
+-- Agent Nodes (Workload) x3
|   concordagent01-03 (.21-.23)
|   Runs: PostgreSQL, HTTP API, Operators, Test Runners, Longhorn storage
|
+-- Edge Nodes (MTIB Hardware) x5+
    verdin-imx8mm-* (.32-.36)
    Runs: MTIB Server containers (privileged, hardware access)
```

### Node Scheduling

- **Server nodes** run only K3s system components (CoreDNS, Traefik, ServiceLB, metrics-server)
- **Agent nodes** run all application workloads. Each product's test runner and operator are pinned to a specific agent via node affinity
- **Edge nodes** run MTIB server containers with privileged access to `/dev`, `/sys/class/gpio`, `/sys/bus/iio`

### Storage

- **Longhorn** distributed block storage across 3 agent nodes (3 replicas)
- **PostgreSQL** for structured application data (Prisma ORM)
- **MinIO** (S3-compatible) for firmware binaries and large assets
- **Filesystem** for legacy cluster/execution data (being migrated to Postgres)

## Service Architecture

```
                    +------------------+
                    |   Frontend (UI)  |
                    |   React / Vite   |
                    |   Port 4200      |
                    +--------+---------+
                             |
                    HTTP / WebSocket
                             |
                    +--------+---------+
                    |    HTTP API       |
                    |  Flask + SocketIO |
                    |  Port 9001       |
                    +--+-----+------+--+
                       |     |      |
              gRPC     |  Prisma    |  K8s API
              50052    |  (Postgres)|  (Jobs)
                       |     |      |
          +------------+  +--+--+   +----------+
          |               | DB  |              |
  +-------+--------+     +-----+    +---------+--------+
  | Cluster Operator|                | K8s Job Scheduler |
  |   (per product) |                | (validation runs) |
  +---+--------+---+                +------------------+
      |        |
    gRPC     gRPC
   (discover) (stream results)
      |        |
  +---+--------+---+
  |  Test Runners   |
  | (per test type) |
  | Ports 50060-62  |
  +---+-------------+
      |
    gRPC 50053
      |
  +---+-------------+
  |  MTIB Servers    |
  | (per edge node)  |
  | Hardware access   |
  +------------------+
```

### Services

| Service | Technology | Port | Role |
|---------|-----------|------|------|
| **Frontend** | React 19, Vite, Tailwind | 4200 | Web UI for operators |
| **HTTP API** | Python, Flask, SocketIO | 9001 | REST/WebSocket gateway |
| **Cluster Operator** | Python, gRPC | 50052 | Manages deployments and test execution per product |
| **Test Runners** | Python, gRPC | 50060-62 | Execute specific test types (electrical, fw flash, POST) |
| **MTIB Server** | Python, gRPC | 50053 | Hardware abstraction layer on edge nodes |
| **PostgreSQL** | Postgres | 5432 | Application database |
| **MinIO** | S3-compatible | 8675/8676 | Object storage for firmware |
| **Vault** | HashiCorp Vault | 8200 | Secrets management |
| **Grafana** | Grafana + Loki | 3000/3100 | Monitoring and logging |

### Communication Protocols

| Pattern | Technology | Use Case |
|---------|-----------|----------|
| REST/JSON | HTTP + Flask | CRUD operations, device management |
| WebSocket | Socket.IO + Eventlet | Real-time test result streaming to UI |
| gRPC Unary | Protocol Buffers | Health checks, single queries, test runner registration |
| gRPC Server Streaming | Protocol Buffers | Test execution result streaming (Operator -> API) |
| K8s Native | Kubernetes batch API | Validation test job scheduling |

### Protocol Definitions

Located in `libs/protocols/`:

- **`cluster_operator.proto`** -- Operator service: health check, cluster info, deployment info, list/execute/stop/register tests
- **`cluster_test.proto`** -- Test runner service: health check, execute (streaming), stop
- **`mtib.proto`** (V1) -- Hardware abstraction: GPIO, ADC, power, sensors, motion, firmware programming, UART
- **`mtib_v2.proto`** (V2) -- Extended: debug probes, power profiling, logic analyzer, bus interfaces, Zephyr integration

## Database

### Technology

- **PostgreSQL** via **Prisma** ORM (prisma-client-py 0.15.0, engine 5.17.0)
- Schema defined in `prisma/schema.prisma`
- Python client generated to `libs/python/database/`

### Schema (14 models, 8 enums)

See `prisma/schema.prisma` for the full definition with detailed doc comments.

**Users & Audit:**
- **User** -- Lightweight mirror of CoreOps Auth Server. Stores name, email, role (ADMIN/OPERATOR/VIEWER) for display and audit. Auth server remains source of truth
- **AuditLog** -- Append-only mutation log. Who did what, to which entity, when, with before/after details

**Products & Fixtures:**
- **Product** -- Hardware product (Sigma5, Theta, Alpha). Everything flows from here
- **Fixture** -- Physical test fixture for a product. Type is MANUFACTURING (multi-panel) or VALIDATION (individual units)
- **FixtureSlot** -- A position in a fixture, mapped to one MTIB node. Unique constraint ensures one node per slot

**Infrastructure:**
- **Node** -- MTIB compute node (Verdin iMX8MM). Hostname, IP, hardware revision, status. Protected from deletion if test history exists
- **Deployment** -- Software deployment record (test runners, operators). Tracks intent and history; live K8s state queried separately

**Sessions & Devices:**
- **Session** -- Operational run: "Manufacture 100 Theta units today." Tracks target/completed/passed/failed counts. Links to Product and optionally Fixture
- **Device** -- Individual DUT within a session. Serial number, pass/fail status, metadata (IMEI, ICCID). Same serial can appear in different sessions (retest)

**Testing:**
- **Test** -- Test definition for a product. Category (electrical/firmware/post), sort order, default config. Unique on [product, name]
- **TestExecution** -- A single run of a test on a node for a device. Links Test + Node + Device + Slot + User (who triggered it)
- **TestResult** -- Step-level result within an execution. Pass/fail boolean plus detailed result JSON

**System:**
- **Log** -- System and execution logs. Optional link to TestExecution
- **Setting** -- Key-value config store with descriptions

### Cascade Behavior

- Product deletion cascades to Fixtures, Tests, and (through Sessions -> Devices -> Executions) all test data
- Test and Node deletion is **restricted** if execution history exists -- disable/decommission instead
- Session deletion cascades through Devices -> TestExecutions -> TestResults (for dev cleanup; production sessions are completed, not deleted)

### Legacy Storage

The V1 system used a filesystem-based database (`storage/clusters/...`) for cluster info, deployments (YAML), and execution results (JSON). This is being migrated to PostgreSQL.

## Frontend

- **React 19** + **TypeScript** + **Vite** + **Tailwind CSS**
- Dark/light theme with custom color palette (aged gold accent)
- Sidebar navigation with 8 pages: Dashboard, Tests, Deployments, Nodes, Results, Logs, Statistics, Settings
- Only Dashboard is currently implemented (with placeholder stat cards)
- No API client layer yet -- pages need HTTP/WebSocket integration

## Authentication & Authorization

### Auth Server

CoreOps Auth Server (.NET) handles all authentication. It provides:
- OAuth2 access tokens (JWT, ECDSA-signed)
- API keys for service-to-service auth
- User logins (password or federated/SAML for Google Workspace)
- Service logins (for Concord HTTP API, operators, etc.)
- Role and permission management

### Integration with Concord

- HTTP API middleware validates tokens with the auth server on every request
- Permission-based route decorators: `@authMiddleware.check_permissions(["Concord.Tests.Execute"])`
- Can be disabled for development (`AUTH_ENABLED=false`)
- Concord mirrors user data in its own `User` table for display and audit (synced on login)

### Roles

| Role | Access | Use Case |
|------|--------|----------|
| **Admin** | Full access. Create products, fixtures, manage nodes, system settings | Engineering leads, IT |
| **Operator** | Run tests, manage sessions, view results. No product/fixture creation | Manufacturing floor staff |
| **Viewer** | Read-only. Results, logs, statistics, cluster status | QA, management, auditors |

### Permission Namespace

```
Concord.Products.*          Concord.Sessions.*
Concord.Fixtures.*          Concord.Tests.{Create,View,Update,Delete,Execute,Stop}
Concord.Nodes.*             Concord.Results.{View,Delete}
Concord.Deployments.*       Concord.Logs.{View,Delete}
Concord.Settings.*          Concord.Statistics.View
```

## Development Environment

Three DevContainer configurations in `.devcontainer/`:

| Container | Base | Adds | For |
|-----------|------|------|-----|
| **base** | Ubuntu 22.04 | Node 22, Go, Python 3, Docker, kubectl, Helm, K9s, Vault | Backend, infra |
| **ncs** | base | Zephyr SDK 0.17.4, NRF CLI Tools, JLink, west, CMake | Firmware development |
| **mtib** | base | JLink, i2c-tools, gpiod, minicom, FluidNC | MTIB hardware development |

## Container Registry

All images published to `containers.ad.corekinect.com`:

```
concord-http-api, concord-operator, concord-vault
concord-mtib-server, mtib-server (dev)
manufacturing-alpha, manufacturing-theta, concord-manufacturing-sigma5
concord-devcontainer-base, concord-devcontainer-ncs, concord-devcontainer-mtib
```

## Open Questions / In Progress

- [ ] Migration from filesystem DB to PostgreSQL for execution history
- [ ] Frontend page implementations (all placeholder except Dashboard)
- [ ] API client layer in the frontend
- [ ] V2 MTIB protocol integration into the main platform
- [ ] Multi-product operator management (currently one operator per product, manually deployed)
- [ ] Statistics/analytics pipeline
- [ ] K8s cluster monitoring in the frontend (admin: k9s-like view, viewer: health overview)
- [ ] User sync flow between CoreOps Auth Server and Concord User table
- [ ] Session-based workflow UI (start session, scan devices, run tests, close session)
