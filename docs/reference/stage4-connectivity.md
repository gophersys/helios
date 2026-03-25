# Stage 4 Validation Connectivity Status

## Services Verified (2026-03-05)

| Service | Endpoint | Status | Notes |
|---------|----------|--------|-------|
| MTIB gRPC | 10.4.45.33:50053 | OK | HealthCheck=ready, DUT power off |
| CoreOps proxy | http://10.4.45.30:8001 | OK | Device ID assignment works |
| Auth server | auth.office.corekinect.cloud:2013 | Reachable | Need user creds (not service creds) |
| VAL REST API | val.office.corekinect.cloud:2018/api | Reachable (401) | Needs auth token |
| VAL DB | validation.ad.corekinect.com:5432 | OK via tunnel | SSH through concordserver01 |
| CoreOps server | coreops.office.corekinect.cloud:2013 | Reachable | Direct access |

## DB Access
- Host: validation.ad.corekinect.com (10.4.41.2)
- Port: 5432 (firewalled from container, needs SSH tunnel)
- User: concord_val
- DB name: test
- SSH bastion: concordserver01.ad.corekinect.com (SSH key at ~/.ssh/keys/machines/concordserver01)
- 32 devices, 333K+ messages, ~600/hr active

## Auth Server
- Service creds from http-api .env (D64A.../C0EA...) are for Concord HTTP API service login
- These use grant_type=client_credentials, NOT grant_type=password
- Validation tests need USER creds (email:password) for grant_type=password
- API key from http-api .env may be scoped to coreops, not val REST server

## Device Status
- 70B3D584C01E1FCC (SNR 0964) registered in VAL CoreCloud (type=2, variant=3, active)
- Device personalized and public key uploaded
- FUOTA endpoints available at `/singleton/` path prefix (not `/api/`)

## FUOTA API Endpoints (confirmed 2026-03-06)
- Upload CFW: `POST /singleton/firmwareimages` (multipart/form-data)
- Create plan: `POST /singleton/firmwareupdates/plans` (JSON)
- Assign device: `POST /singleton/firmwareupdates/settings/devices` (JSON)
- Monitor: `GET /singleton/firmwareupdates/progress?deviceId=<DevEUI>`
- See `fuota-api-workflow.md` for full details

## Missing: Login Registration
- User `mateo@corekinect.com` has Auth Server credentials (token fetch works)
- API key provided IS the CoreCloud API key (confirmed by user)
- **Login NOT registered with VAL CoreCloud instance** → REST API returns 401
- Per Bringup Guide step 14: admin must POST to `/api/authentication/logins/register`
- Need: loginId from Auth Server, then register + assign role in VAL CoreCloud
- This is an admin-only operation (seed mode or existing admin needed)

## Dependency Issues
- paramiko 4.0 removed DSSKey → sshtunnel 0.4.0 crashes. Pin paramiko<4.0
- protobuf must be >=5.x for libs/protocols generated code
- nrfutil requires protobuf<4.0 (conflict — separate venv needed for flashing)
