#!/usr/bin/env python3
"""
Live-cluster topology introspector -> emits the Topology contract
(apps/frontend/src/lib/topology/contract.ts) as JSON.

Reads a cluster through kubectl (KUBECONFIG) and derives nodes (workloads, services,
ingresses, PVCs) + edges (ingress->service routes with host/port, service->workload
selects, workload->pvc mounts, namespace grouping) + two views (architecture, data-flow).
Health is REAL: it reads pods (phase, restarts, CrashLoop) and endpoints (dangling
services), so a node is only "ok" when it actually is. The client (model.ts) derives the
rollups; this producer's job is accurate, enriched NODES.

Usage:
  KUBECONFIG=~/.kube/homelab.yaml python3 introspect-topology.py home "Home · k3s" > snapshots/home.json
"""
import json, subprocess, sys, datetime

SKIP_NS = {"kube-node-lease", "kube-public"}
CRASH_REASONS = {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "CreateContainerError",
                 "RunContainerError", "CreateContainerConfigError", "InvalidImageName"}

def kc(*args):
    out = subprocess.run(["kubectl", *args, "-o", "json"], capture_output=True, text=True)
    if out.returncode != 0:
        return {"items": []}
    return json.loads(out.stdout)

def image_stem(image):
    if not image:
        return ""
    name = image.split("/")[-1].split("@")[0]
    return name.split(":")[0]

def image_tag(image):
    if not image:
        return ""
    last = image.split("/")[-1]
    if "@" in last:                       # digest pin
        return last.split("@")[1][:19]
    return last.split(":")[1] if ":" in last else ""

def classify(name, image):
    # The semantic NodeKind (icon). Deliberately NARROW — only true data/infra roles; cert-manager
    # is a controller (a workload), not a secret store, so it is intentionally NOT matched here.
    s = (name + " " + (image or "")).lower()
    if any(k in s for k in ("postgres", "mysql", "mariadb", "cockroach", "couchdb", "mongo")):
        return "database"
    if any(k in s for k in ("redis", "memcached", "valkey", "dragonfly")):
        return "cache"
    if any(k in s for k in ("nats", "kafka", "rabbitmq", "pulsar")):
        return "queue"
    if "vault" in s or "sealed-secret" in s:
        return "secretstore"
    return None

def subset(sel, labels):
    return bool(sel) and all(labels.get(k) == v for k, v in sel.items())

def main():
    cluster_id, cluster_name = sys.argv[1], sys.argv[2]
    nodes, edges = {}, {}
    ns_with_content = set()

    def add_node(n):
        nodes[n["id"]] = n
    def add_edge(src, tgt, kind, label=None, meta=None):
        if src in nodes and tgt in nodes:
            eid = f"{kind}:{src}->{tgt}"
            e = {"id": eid, "source": src, "target": tgt, "kind": kind}
            if label:
                e["label"] = label
            if meta:
                e["meta"] = meta
            edges[eid] = e

    # ── pods: the real health source (indexed by namespace) ───────────────────────────────────────
    pods_by_ns = {}
    for pod in kc("get", "pods", "-A").get("items", []):
        ns = pod["metadata"]["namespace"]
        pods_by_ns.setdefault(ns, []).append(pod)

    def pod_health(ns, sel_labels):
        """Roll a workload's pods up to (restarts, crash_reason, pending, running_ready)."""
        restarts, crash, pending, ready_pods, total = 0, None, False, 0, 0
        for pod in pods_by_ns.get(ns, []):
            if not subset(sel_labels, pod["metadata"].get("labels", {})):
                continue
            total += 1
            pst = pod.get("status", {})
            if pst.get("phase") == "Pending":
                pending = True
            css = pst.get("containerStatuses", []) or []
            for cs in css:
                restarts += cs.get("restartCount", 0)
                waiting = (cs.get("state", {}) or {}).get("waiting") or {}
                if waiting.get("reason") in CRASH_REASONS:
                    crash = waiting["reason"]
            if css and all(cs.get("ready") for cs in css):
                ready_pods += 1
        return restarts, crash, pending, ready_pods, total

    workloads = []  # (id, ns, selLabels, pvcs)

    def handle_workload(item, k8s_kind, node_kind):
        ns = item["metadata"]["namespace"]
        if ns in SKIP_NS:
            return
        name = item["metadata"]["name"]
        nid = f"{k8s_kind}/{ns}/{name}"
        spec = item.get("spec", {})
        tmpl = spec.get("template", {}).get("spec", {})
        containers = tmpl.get("containers", [])
        image = containers[0].get("image", "") if containers else ""
        st = item.get("status", {})
        if k8s_kind == "ds":
            desired = st.get("desiredNumberScheduled", 0); ready = st.get("numberReady", 0)
            updated = st.get("updatedNumberScheduled", desired)
        else:
            desired = spec.get("replicas", st.get("replicas", 0)); ready = st.get("readyReplicas", 0) or 0
            updated = st.get("updatedReplicas", desired) or 0

        sel_labels = (spec.get("selector", {}).get("matchLabels", {})
                      or spec.get("template", {}).get("metadata", {}).get("labels", {})
                      or item["metadata"].get("labels", {}))
        restarts, crash, pending, _ready_pods, _total = pod_health(ns, sel_labels)

        # REAL status: crash/pull errors -> down; nothing ready -> down; rolling out -> progressing;
        # under-replicated or restart-churning -> warn; else ok.
        reason = None
        if crash:
            status, reason = "down", crash
        elif desired and ready == 0:
            status, reason = "down", "no replicas ready"
        elif desired and ready < desired:
            if updated < desired or pending:
                status, reason = "progressing", f"rolling out ({ready}/{desired})"
            else:
                status, reason = "warn", f"{ready}/{desired} ready"
        elif restarts >= 10:
            status, reason = "warn", f"{restarts} restarts (flapping)"
        else:
            status = "ok"

        kind = classify(name, image) or node_kind
        meta = {"kind": k8s_kind, "image": image_stem(image), "replicas": f"{ready}/{desired}"}
        tag = image_tag(image)
        if tag:
            meta["imageTag"] = tag
        created = item["metadata"].get("creationTimestamp")
        if created:
            meta["createdAt"] = created
        ports = [str(p.get("containerPort")) for c in containers for p in c.get("ports", []) if p.get("containerPort")]
        if ports:
            meta["ports"] = ",".join(ports[:6])
        health = {"ready": ready, "desired": desired, "restarts": restarts}
        if reason:
            health["reason"] = reason
        add_node({"id": nid, "kind": kind, "name": name, "namespace": ns, "meta": meta,
                  "status": status, "health": health, "group": f"ns/{ns}"})
        ns_with_content.add(ns)
        pvcs = [v["persistentVolumeClaim"]["claimName"] for v in tmpl.get("volumes", []) if v.get("persistentVolumeClaim")]
        workloads.append((nid, ns, sel_labels, pvcs))

    for item in kc("get", "deployments", "-A").get("items", []):
        handle_workload(item, "deploy", "deployment")
    for item in kc("get", "statefulsets", "-A").get("items", []):
        handle_workload(item, "sts", "statefulset")
    for item in kc("get", "daemonsets", "-A").get("items", []):
        handle_workload(item, "ds", "daemonset")

    # ── endpoints: a service with a selector but zero ready addresses is DANGLING (warn) ──────────
    ready_addr = {}
    for ep in kc("get", "endpoints", "-A").get("items", []):
        ns = ep["metadata"]["namespace"]; name = ep["metadata"]["name"]
        n = sum(len(s.get("addresses", []) or []) for s in (ep.get("subsets", []) or []))
        ready_addr[(ns, name)] = n

    services = []
    for item in kc("get", "services", "-A").get("items", []):
        ns = item["metadata"]["namespace"]
        if ns in SKIP_NS:
            continue
        name = item["metadata"]["name"]
        spec = item.get("spec", {})
        sel = spec.get("selector") or {}
        nid = f"svc/{ns}/{name}"
        meta = {"type": spec.get("type", "ClusterIP")}
        ports = [str(p.get("port")) for p in spec.get("ports", []) if p.get("port")]
        if ports:
            meta["ports"] = ",".join(ports[:6])
        if spec.get("clusterIP") and spec.get("clusterIP") != "None":
            meta["clusterIP"] = spec["clusterIP"]
        # a selector service with no ready backends is broken; selectorless (ExternalName/manual) is ok
        status = "warn" if (sel and ready_addr.get((ns, name), 0) == 0) else "ok"
        node = {"id": nid, "kind": "service", "name": name, "namespace": ns, "meta": meta, "status": status, "group": f"ns/{ns}"}
        if status == "warn":
            node["health"] = {"ready": 0, "desired": 1, "reason": "no ready endpoints"}
        add_node(node)
        ns_with_content.add(ns)
        services.append((nid, ns, sel))
        for wid, wns, wlabels, _ in workloads:
            if wns == ns and subset(sel, wlabels):
                add_edge(nid, wid, "selects")

    # ── ingresses: routes carry the host/path/port chain on the edge ──────────────────────────────
    for item in kc("get", "ingresses", "-A").get("items", []):
        ns = item["metadata"]["namespace"]
        if ns in SKIP_NS:
            continue
        name = item["metadata"]["name"]
        nid = f"ing/{ns}/{name}"
        spec = item.get("spec", {})
        hosts = sorted({r.get("host") for r in spec.get("rules", []) if r.get("host")})
        meta = {"hosts": ", ".join(hosts[:4]) if hosts else "*"}
        add_node({"id": nid, "kind": "ingress", "name": name, "namespace": ns, "meta": meta, "status": "ok", "group": f"ns/{ns}"})
        ns_with_content.add(ns)
        seen = {}  # service -> route meta (first wins)
        for r in spec.get("rules", []):
            host = r.get("host", "")
            for p in (r.get("http", {}) or {}).get("paths", []):
                b = p.get("backend", {}).get("service", {})
                bname = b.get("name")
                if not bname:
                    continue
                port = b.get("port", {})
                pstr = str(port.get("number") or port.get("name") or "")
                seen.setdefault(bname, {"host": host, "path": p.get("path", "/"), "port": pstr})
        db = spec.get("defaultBackend", {}).get("service", {})
        if db.get("name"):
            seen.setdefault(db["name"], {"host": hosts[0] if hosts else "", "path": "/", "port": str((db.get("port") or {}).get("number") or "")})
        for bname, rmeta in seen.items():
            add_edge(nid, f"svc/{ns}/{bname}", "routes", label=f"{rmeta['host']}{rmeta['path']}", meta=rmeta)

    # ── pvcs (only those a workload mounts) — phase drives health ─────────────────────────────────
    mounted = {(wns, c) for _, wns, _, pvcs in workloads for c in pvcs}
    for item in kc("get", "pvc", "-A").get("items", []):
        ns = item["metadata"]["namespace"]; name = item["metadata"]["name"]
        if (ns, name) not in mounted:
            continue
        nid = f"pvc/{ns}/{name}"
        spec = item.get("spec", {})
        phase = item.get("status", {}).get("phase", "")
        cap = item.get("status", {}).get("capacity", {}).get("storage", "")
        meta = {"storageClass": spec.get("storageClassName", ""), "capacity": cap}
        status = "ok" if phase == "Bound" else ("warn" if phase == "Pending" else "down")
        add_node({"id": nid, "kind": "pvc", "name": name, "namespace": ns, "meta": meta, "status": status, "group": f"ns/{ns}"})
    for wid, wns, _, pvcs in workloads:
        for c in pvcs:
            add_edge(wid, f"pvc/{wns}/{c}", "mounts")

    # ── exposure: anything reachable from an ingress route is public ──────────────────────────────
    public = set()
    for e in edges.values():
        if e["kind"] == "routes":
            public.add(e["source"]); public.add(e["target"])
    for e in edges.values():
        if e["kind"] == "selects" and e["source"] in public:
            public.add(e["target"])
    for n in nodes.values():
        if n["kind"] != "namespace":
            n["exposure"] = "public" if n["id"] in public else "internal"

    # namespace group nodes + contains edges
    for ns in sorted(ns_with_content):
        add_node({"id": f"ns/{ns}", "kind": "namespace", "name": ns, "meta": {}, "status": "ok"})
    for n in list(nodes.values()):
        if n["kind"] != "namespace" and n.get("namespace"):
            add_edge(f"ns/{n['namespace']}", n["id"], "contains")

    node_list = list(nodes.values())
    edge_list = list(edges.values())

    # views (data, not code): architecture = everything; data-flow = the request/data path only
    flow_kinds = {"ingress", "service", "deployment", "statefulset", "daemonset", "database", "cache", "queue", "pvc"}
    flow_nodes = [n["id"] for n in node_list if n["kind"] in flow_kinds]
    flow_edges = [e["id"] for e in edge_list if e["kind"] in ("routes", "selects", "mounts")]
    views = [
        {"id": "architecture", "title": "Architecture", "description": "Workloads, services, ingress and storage, grouped by namespace.", "nodes": [], "edges": []},
        {"id": "dataflow", "title": "Data flow", "description": "The request + storage path: ingress → service → workload → volume.", "nodes": flow_nodes, "edges": flow_edges},
    ]

    print(json.dumps({
        "clusterId": cluster_id, "clusterName": cluster_name,
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "live-introspection",
        "nodes": node_list, "edges": edge_list, "views": views,
    }, indent=2))

if __name__ == "__main__":
    main()
