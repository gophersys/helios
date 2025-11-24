# K3s Cluster Architecture

## Overview

Highly available k3s cluster with dedicated node roles for stability and workload isolation.

**Cluster Type:** HA Control Plane (3 servers)  
**API Endpoint:** `https://10.4.45.10:6443`  
**K3s Version:** v1.33.5+k3s1 (servers), v1.28.7-k3s1 (edge)

## Node Architecture

### Server Nodes (Control Plane)
- **Purpose:** HA control plane + core system components + backend services
- **Count:** 3 nodes
- **Roles:** `control-plane`, `etcd`, `master`
- **Nodes:**
  - `concordserver01` - 10.4.45.11
  - `concordserver02` - 10.4.45.12
  - `concordserver03` - 10.4.45.13

### Agent Nodes (Workload)
- **Purpose:** Databases, general workloads, larger persistent volumes
- **Count:** 3 nodes
- **Roles:** None (workload nodes)
- **Nodes:**
  - `concordagent01` - 10.4.45.21
  - `concordagent02` - 10.4.45.22
  - `concordagent03` - 10.4.45.23

### Edge Node
- **Purpose:** Intermittent connectivity scenarios (IoT/edge workloads)
- **Count:** 1 node
- **Roles:** None
- **Nodes:**
  - `verdin-imx8mm-15005679` - 10.4.45.33 (ARM64, Torizon OS)

## System Component Configuration

All core k3s system components are restricted to server nodes only via node selectors:

- **CoreDNS** - DNS resolution
- **Metrics Server** - Resource metrics
- **Local Path Provisioner** - Default storage class
- **Traefik** - Ingress controller
- **svclb-traefik** - Service load balancer (DaemonSet)

**Node Selector:** `node-role.kubernetes.io/control-plane: "true"`

This ensures:
- Core infrastructure runs only on stable HA nodes
- Agent nodes remain free for workloads
- Edge nodes don't disrupt critical services during disconnections

## Configuration Commands

Run these commands on a fresh k3s installation to configure system components to run only on control-plane nodes:

```bash
# Restrict CoreDNS to control-plane nodes
kubectl patch deployment coredns -n kube-system -p '{"spec":{"template":{"spec":{"nodeSelector":{"node-role.kubernetes.io/control-plane":"true"}}}}}'

# Restrict Metrics Server to control-plane nodes
kubectl patch deployment metrics-server -n kube-system -p '{"spec":{"template":{"spec":{"nodeSelector":{"node-role.kubernetes.io/control-plane":"true"}}}}}'

# Restrict Local Path Provisioner to control-plane nodes
kubectl patch deployment local-path-provisioner -n kube-system -p '{"spec":{"template":{"spec":{"nodeSelector":{"node-role.kubernetes.io/control-plane":"true"}}}}}'

# Restrict Traefik to control-plane nodes
kubectl patch deployment traefik -n kube-system -p '{"spec":{"template":{"spec":{"nodeSelector":{"node-role.kubernetes.io/control-plane":"true"}}}}}'

# Restrict Traefik Load Balancer DaemonSet to control-plane nodes
kubectl patch daemonset svclb-traefik-$(kubectl get svc traefik -n kube-system -o jsonpath='{.metadata.annotations.kubectl\.kubernetes\.io/last-applied-configuration}' | grep -oP 'svclb-traefik-\K[a-z0-9]+') -n kube-system -p '{"spec":{"template":{"spec":{"nodeSelector":{"node-role.kubernetes.io/control-plane":"true"}}}}}'
```

**Note:** For the Traefik DaemonSet, you may need to find the actual DaemonSet name first:
```bash
# Find the Traefik DaemonSet name
kubectl get daemonset -n kube-system | grep svclb-traefik

# Then patch it (replace <NAME> with actual name)
kubectl patch daemonset <NAME> -n kube-system -p '{"spec":{"template":{"spec":{"nodeSelector":{"node-role.kubernetes.io/control-plane":"true"}}}}}'
```

## Verification

```bash
# Verify all system pods are on server nodes only
kubectl get pods -n kube-system -o wide | grep -E "coredns|metrics-server|traefik|local-path"

# Verify node selectors are set correctly
kubectl get deployment,daemonset -n kube-system -o jsonpath='{range .items[*]}{.metadata.name}{": "}{.spec.template.spec.nodeSelector}{"\n"}{end}'

# Check that no system pods are on agent/edge nodes
kubectl get pods -n kube-system -o wide | grep -E "concordagent|verdin"
```

## Longhorn Storage

Longhorn is configured to provide distributed block storage with volumes stored **only on agent nodes**.

### Installation

**Prerequisites on all nodes (including servers):**
```bash
# Install required packages on each node (servers and agents)
sudo apt-get update
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable iscsid
sudo systemctl start iscsid
```

**Install Longhorn:**
```bash
# Label agent nodes for Longhorn storage
kubectl label nodes concordagent01 concordagent02 concordagent03 node.longhorn.io/create-default-disk=true

# Install Longhorn
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.8.1/deploy/longhorn.yaml

# Configure Longhorn to only create disks on labeled nodes
kubectl patch setting.longhorn.io create-default-disk-labeled-nodes -n longhorn-system --type merge -p '{"value":"true"}' 2>/dev/null || kubectl create -f - <<EOF
apiVersion: longhorn.io/v1beta2
kind: Setting
metadata:
  name: create-default-disk-labeled-nodes
  namespace: longhorn-system
value: "true"
EOF
```

### Configuration

**Storage Location:** Volumes and replicas are stored **only on agent nodes**:
- `concordagent01`
- `concordagent02`
- `concordagent03`

**Storage Class:** `longhorn` (default storage class)
- **Replicas:** 3 (one per agent node)
- **File System:** ext4
- **Binding Mode:** Immediate

### Verification

```bash
# Verify Longhorn nodes (should only show agent nodes)
kubectl get nodes.longhorn.io -n longhorn-system

# Verify storage is only on agent nodes
kubectl get nodes.longhorn.io -n longhorn-system -o jsonpath='{range .items[*]}{.metadata.name}{": "}{.spec.disks}{"\n"}{end}'

# Test creating a PVC
kubectl create -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-longhorn-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: longhorn
  resources:
    requests:
      storage: 1Gi
EOF

# Verify PVC is bound
kubectl get pvc test-longhorn-pvc

# Check where replicas are stored (should only be on agent nodes)
kubectl get replicas.longhorn.io -n longhorn-system -o jsonpath='{range .items[*]}{.metadata.name}{": "}{.spec.nodeID}{"\n"}{end}' | grep test-longhorn
```

### Creating Persistent Volumes

When creating PVCs, use the `longhorn` storage class:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: longhorn
  resources:
    requests:
      storage: 10Gi
```

**Note:** All volume replicas will be distributed across the 3 agent nodes only. Server nodes and edge nodes are excluded from storage to maintain their dedicated roles.

## Networking and Load Balancing

### How Load Balancing Works in Private Office

In a private office environment (no cloud provider), K3s uses **ServiceLB** (formerly Klipper) to provide LoadBalancer functionality:

1. **ServiceLB Pods** run on server nodes only (already configured)
   - Bind to ports 80 and 443 on server node IPs
   - Forward traffic to Traefik Ingress controller
   - Each server node has a ServiceLB pod, providing HA

2. **Traefik Ingress Controller** handles routing
   - Routes traffic based on hostname/path
   - Terminates TLS/HTTPS
   - Routes to backend services

3. **Current Configuration:**
   - ServiceLB pods: `concordserver01`, `concordserver02`, `concordserver03`
   - Traefik service exposes: `10.4.45.11`, `10.4.45.12`, `10.4.45.13` on ports 80/443

### Architecture Flow

```
External Client
    ↓
[Router/Firewall] → Port 80/443
    ↓
Server Node IPs (10.4.45.11/12/13)
    ↓
ServiceLB Pod (hostPort 80/443)
    ↓
Traefik Ingress Controller
    ↓
Backend Services (pods)
```

### Multiple HTTPS Services

Traefik uses **Ingress resources** to route multiple services based on hostname:

**Example: Serving multiple services**

```yaml
# Ingress for service1.example.com
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: service1-ingress
  namespace: default
spec:
  ingressClassName: traefik
  rules:
  - host: service1.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: service1
            port:
              number: 8080
  tls:
  - hosts:
    - service1.example.com
    secretName: service1-tls

---
# Ingress for service2.example.com
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: service2-ingress
  namespace: default
spec:
  ingressClassName: traefik
  rules:
  - host: service2.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: service2
            port:
              number: 8080
  tls:
  - hosts:
    - service2.example.com
    secretName: service2-tls
```

### TLS/HTTPS Configuration

**Option 1: Using Certificates (Recommended for Internal)**

1. **Create TLS Secret** with your certificate:
```bash
kubectl create secret tls my-service-tls \
  --cert=/path/to/cert.pem \
  --key=/path/to/key.pem \
  -n <namespace>
```

2. **Reference in Ingress:**
```yaml
tls:
- hosts:
  - myservice.example.com
  secretName: my-service-tls
```

**Option 2: Traefik Auto TLS (Let's Encrypt - for public domains)**

Configure Traefik with Let's Encrypt via HelmChartConfig (not covered here).

**Note:** The certificate script you run installs **client CA certificates** (for trusting CoreKinect services). For **server TLS certificates** (HTTPS), you need:
- Server certificate and private key
- Create Kubernetes TLS secrets
- Reference in Ingress resources

### DNS Configuration

For services to be accessible:

1. **Internal DNS:** Point `service1.example.com` → `10.4.45.11` (or any server node IP)
2. **Or use IPs directly:** Access via `https://10.4.45.11` with appropriate Host header
3. **Load balancing:** Use all 3 server IPs in DNS round-robin for HA

### Verification

```bash
# Check ServiceLB pods are on server nodes only
kubectl get pods -n kube-system -l svccontroller.k3s.cattle.io/svcname=traefik -o wide

# Check Traefik service LoadBalancer IPs
kubectl get svc -n kube-system traefik

# List all Ingress resources
kubectl get ingress --all-namespaces

# Test access (from a machine that can reach the server nodes)
curl -H "Host: service1.example.com" http://10.4.45.11
```

### How Multiple Services Share Port 443 (HTTPS)

Traefik uses **SNI (Server Name Indication)** - when a client connects via HTTPS, the hostname is included in the TLS handshake. Traefik reads this hostname and routes to the matching Ingress/service.

**Example:** Both `app1.example.com` and `app2.example.com` can use port 443 simultaneously:

```yaml
# Service 1 - HTTPS on port 443
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app1-ingress
spec:
  ingressClassName: traefik
  rules:
  - host: app1.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: app1
            port:
              number: 80
  tls:
  - hosts:
    - app1.example.com
    secretName: app1-tls

---
# Service 2 - HTTPS on port 443 (same port!)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app2-ingress
spec:
  ingressClassName: traefik
  rules:
  - host: app2.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: app2
            port:
              number: 80
  tls:
  - hosts:
    - app2.example.com
    secretName: app2-tls
```

Both services share port 443 - Traefik routes based on the hostname in the TLS handshake.

### Accessing Services

**Without DNS (testing):**
```bash
# Using IP with Host header
curl -H "Host: webapp1.local" http://10.4.45.11
curl -H "Host: webapp2.local" http://10.4.45.11

# HTTPS with Host header
curl -k -H "Host: app1.example.com" https://10.4.45.11
```

**With DNS:**
Point `app1.example.com` → `10.4.45.11` (or any server IP) in your DNS, then:
```bash
curl https://app1.example.com
```

### Auto TLS Options

**Option 1: Manual Certificates (Internal/Private Office)**
```bash
# Create TLS secret from existing cert/key
kubectl create secret tls my-service-tls \
  --cert=/path/to/cert.pem \
  --key=/path/to/key.pem \
  -n default

# Reference in Ingress (see example above)
```

**Option 2: Traefik Auto TLS (Let's Encrypt - Public Domains Only)**
For automatic Let's Encrypt certificates, configure Traefik via HelmChartConfig:
```bash
# Create HelmChartConfig (this is k3s-specific)
cat > /var/lib/rancher/k3s/server/manifests/traefik-config.yaml <<EOF
apiVersion: helm.cattle.io/v1
kind: HelmChartConfig
metadata:
  name: traefik
  namespace: kube-system
spec:
  valuesContent: |-
    certificatesResolvers:
      letsencrypt:
        acme:
          email: your-email@example.com
          storage: /data/acme.json
          httpChallenge:
            entryPoint: web
EOF
```

**Note:** Auto TLS requires:
- Public DNS (Let's Encrypt needs to verify domain ownership)
- Ingress with proper hostname
- Traefik configured with certificate resolver

**For private office/internal services:** Use manual certificates (Option 1).

### Important Notes

1. **No External Load Balancer Needed:** ServiceLB handles everything internally
2. **Ports 80/443:** Reserved on server nodes for ServiceLB (cannot use HostPort/NodePort on these)
3. **HA:** All 3 server nodes can receive traffic (round-robin via DNS or external LB if you add one)
4. **Multiple Services on Same Port:** Use hostname-based routing via Ingress (Traefik uses SNI for HTTPS)
5. **Client Certificates vs Server Certificates:**
   - **Client CA certs** (your script): Trust CoreKinect services (registry, etc.) - already installed
   - **Server TLS certs**: Needed for HTTPS services - create per service via Ingress
6. **ServiceLB Restriction:** Label server nodes with `svccontroller.k3s.cattle.io/enablelb=true` to restrict LB pods to servers only
