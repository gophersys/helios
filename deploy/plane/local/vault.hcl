# Eden local Vault server config (ADR-0022 #1): REAL server mode with a file storage backend —
# NOT the in-memory `-dev` server. The one-shot init/unseal/seed is performed out-of-band by
# vault-seed.sh. TLS is disabled for the loopback-only local listener (the API is bound to
# 127.0.0.1 by the compose port mapping); production uses the Helm chart with TLS + the
# Kubernetes-ServiceAccount auth path instead of userpass.

ui = false
disable_mlock = true

storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

api_addr = "http://127.0.0.1:8200"
