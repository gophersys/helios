# Environment Specification

## Hardware Requirements

| Resource | Required | Available | Notes |
|----------|----------|-----------|-------|
| CPU | 4+ cores | Available (codespace) | Build service needs CPU for firmware compilation |
| Memory | 8+ GB | Available | Docker-compose stack + Playwright + build containers |
| Disk | 20+ GB | Available | Docker images, build artifacts, MinIO storage |
| GPU | Not required | N/A | |

## External Resources

| Resource | Purpose | Access Method | Status |
|----------|---------|---------------|--------|
| MTIB <MTIB_HOST> | Hardware-in-loop testing (power, GPIO, UART, J-Link) | gRPC :50053 | Requires office network |
| J-Link 821009543 | Flash nRF52840 app processor | Via MTIB gRPC | On MTIB REV 1.2 |
| J-Link 821009541 | Flash nRF9151 comms coprocessor | Via MTIB gRPC | On MTIB REV 1.2 |
| DUT Alpha B0 (SNR 0964) | Device under test | Via MTIB (power, UART, J-Link) | No battery, ch0 only @ 4.5V |

## Software Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Node.js | 18+ | Playwright, SvelteKit frontend |
| Playwright | Latest | Browser automation |
| Python | 3.11+ | Backend services, validation runner |
| Docker | 24+ | Container runtime for services |
| Docker Compose | v2 | Service orchestration |
| PostgreSQL | 16 | Database (via docker-compose) |
| MinIO | Latest | S3-compatible storage (via docker-compose) |
| nrfjprog | 10.x | Firmware flashing (via MTIB K8s pod) |

## Network Requirements

| Endpoint | Purpose | Protocol | From Codespace | From Office |
|----------|---------|----------|:--------------:|:-----------:|
| auth.office.corekinect.cloud:2013 | User auth, CoreCloud auth | HTTPS | Reachable | Reachable |
| val.office.corekinect.cloud:2018 | CoreCloud REST API (devices, FUOTA) | HTTPS | Reachable | Reachable |
| api.bitbucket.org | Branch/PR management, repo access | HTTPS | Reachable | Reachable |
| <MTIB_HOST>:50053 | MTIB gRPC (power, GPIO, UART, flash) | gRPC | **UNREACHABLE** | Reachable |
| <MTIB_HOST>:22 | MTIB SSH (maintenance) | SSH | **UNREACHABLE** | Reachable |
| localhost:9001 | Concord HTTP API | HTTP | Local | Local |
| localhost:4200 | SvelteKit frontend | HTTP | Local | Local |
| localhost:5433 | PostgreSQL | TCP | Local | Local |
| localhost:8675 | MinIO | HTTP | Local | Local |

## Credentials (from deploy/development/.env)

| Credential | Env Variable | Location |
|-----------|-------------|----------|
| Bitbucket SSH key | `BITBUCKET_SSH_KEY` | deploy/development/.env (base64) |
| Bitbucket API token | `BITBUCKET_API_TOKEN` | deploy/development/.env |
| Bitbucket email | `BITBUCKET_EMAIL` | deploy/development/.env (mateo@corekinect.com) |
| Bitbucket workspace | `BITBUCKET_WORKSPACE` | corekinect |
| CoreCloud API key | `VAL_1_0_API_KEY` | .env (root) |
| CoreCloud auth user | `VAL_1_0_API_AUTH_USERNAME` | deploy/development/.env |
| CoreCloud auth pass | `VAL_1_0_API_AUTH_PASSWORD` | deploy/development/.env |
| CoreOps API key | `COREOPS_API_KEY` | infrastructure/clusters/office/secrets/.env |
| JWT secret | `JWT_SECRET_KEY` | deploy/development/.env |
| CI API key | hardcoded | ck_ci_admin_x8K2mP9vL4nQ7wR1tY6uI3oA5sD0fG |
| MinIO access key | `STORAGE_ACCESS_KEY` | deploy/development/.env |
| MinIO secret key | `STORAGE_SECRET_ACCESS_KEY` | deploy/development/.env |

## Detection Commands

```bash
# CPU
nproc

# Memory
free -g

# Disk
df -h /workspaces

# Docker
docker --version
docker compose version

# Node
node --version
npx playwright --version

# Python
python3 --version

# Network: CoreCloud
timeout 5 bash -c 'echo | openssl s_client -connect auth.office.corekinect.cloud:2013 2>&1 | head -1'

# Network: Bitbucket
curl -s -o /dev/null -w "%{http_code}" https://api.bitbucket.org/2.0/

# Network: MTIB
timeout 3 ping -c 1 <MTIB_HOST>

# Network: Other office hosts
timeout 3 ping -c 1 10.4.45.31
timeout 3 ping -c 1 <MTIB_HOST>
```

## Execution Environment Constraint

**CRITICAL:** Tests requiring MTIB hardware interaction (Stages 9, 10, and parts of Stage 12) MUST run from a machine on the 10.4.45.x office network. The current codespace (172.22.x.x) cannot reach the MTIB.

**Options:**
1. Run full suite from an office workstation
2. Run non-MTIB tests from codespace, MTIB tests from office
3. Expose MTIB via K8s ingress/service (future infrastructure work)
4. Run as K8s pod in the office cluster (same network as MTIB)

**Current recommendation:** Option 1 (office workstation) for simplicity. The suite is designed to run as a single sequential flow.
