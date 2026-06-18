#!/usr/bin/env python3
"""
Live-cluster topology introspector -> emits the Topology contract
(apps/frontend/src/lib/topology/contract.ts) as JSON.

Reads a cluster through kubectl (KUBECONFIG) and derives nodes (workloads, services,
ingresses, PVCs) + edges (ingress->service routes, service->workload selects,
workload->pvc mounts, namespace grouping) + two views (architecture, data-flow).

Usage:
  KUBECONFIG=~/.kube/homelab.yaml python3 introspect-topology.py home "Home · k3s" > snapshots/home.json
"""
import json, subprocess, sys, datetime

SKIP_NS = {"kube-node-lease", "kube-public"}

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

def classify(name, image):
    s = (name + " " + (image or "")).lower()
    if any(k in s for k in ("postgres", "mysql", "mariadb", "cockroach", "couchdb", "mongo")):
        return "database"
    if any(k in s for k in ("redis", "memcached", "valkey", "dragonfly")):
        return "cache"
    if any(k in s for k in ("nats", "kafka", "rabbitmq", "pulsar")):
        return "queue"
    if any(k in s for k in ("vault", "sealed-secret", "cert-manager")):
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
    def add_edge(src, tgt, kind, label=None):
        if src in nodes and tgt in nodes:
            eid = f"{kind}:{src}->{tgt}"
            edges[eid] = {"id": eid, "source": src, "target": tgt, "kind": kind, **({"label": label} if label else {})}

    workloads = []  # (id, ns, podLabels, pvcs)

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
        # replicas / health
        st = item.get("status", {})
        if k8s_kind == "ds":
            desired = st.get("desiredNumberScheduled", 0); ready = st.get("numberReady", 0)
        else:
            desired = spec.get("replicas", st.get("replicas", 0)); ready = st.get("readyReplicas", 0)
        status = "ok" if (desired and ready >= desired) else ("warn" if ready else "down")
        kind = classify(name, image) or node_kind
        pod_labels = item["metadata"].get("labels", {})
        # service selector usually matches the pod template labels
        sel_labels = spec.get("selector", {}).get("matchLabels", {}) or item.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {}) or pod_labels
        meta = {"kind": k8s_kind, "image": image_stem(image), "replicas": f"{ready}/{desired}"}
        ports = [str(p.get("containerPort")) for c in containers for p in c.get("ports", []) if p.get("containerPort")]
        if ports:
            meta["ports"] = ",".join(ports[:6])
        add_node({"id": nid, "kind": kind, "name": name, "namespace": ns, "meta": meta, "status": status, "group": f"ns/{ns}"})
        ns_with_content.add(ns)
        pvcs = [v["persistentVolumeClaim"]["claimName"] for v in tmpl.get("volumes", []) if v.get("persistentVolumeClaim")]
        workloads.append((nid, ns, sel_labels, pvcs))

    for item in kc("get", "deployments", "-A").get("items", []):
        handle_workload(item, "deploy", "deployment")
    for item in kc("get", "statefulsets", "-A").get("items", []):
        handle_workload(item, "sts", "statefulset")
    for item in kc("get", "daemonsets", "-A").get("items", []):
        handle_workload(item, "ds", "daemonset")

    # services
    services = []
    for item in kc("get", "services", "-A").get("items", []):
        ns = item["metadata"]["namespace"]
        if ns in SKIP_NS:
            continue
        name = item["metadata"]["name"]
        spec = item.get("spec", {})
        sel = spec.get("selector") or {}
        if not sel and spec.get("type") != "LoadBalancer":
            # headless/no-selector services that aren't LBs add little signal; keep LBs + selector svcs
            if spec.get("type") not in ("LoadBalancer", "NodePort"):
                pass
        nid = f"svc/{ns}/{name}"
        meta = {"type": spec.get("type", "ClusterIP")}
        ports = [str(p.get("port")) for p in spec.get("ports", []) if p.get("port")]
        if ports:
            meta["ports"] = ",".join(ports[:6])
        if spec.get("clusterIP") and spec.get("clusterIP") != "None":
            meta["clusterIP"] = spec["clusterIP"]
        add_node({"id": nid, "kind": "service", "name": name, "namespace": ns, "meta": meta, "status": "ok", "group": f"ns/{ns}"})
        ns_with_content.add(ns)
        services.append((nid, ns, sel))
        # service -> workload (selector subset of workload labels)
        for wid, wns, wlabels, _ in workloads:
            if wns == ns and subset(sel, wlabels):
                add_edge(nid, wid, "selects")

    # ingresses
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
        backends = set()
        for r in spec.get("rules", []):
            for p in (r.get("http", {}) or {}).get("paths", []):
                b = p.get("backend", {}).get("service", {}).get("name")
                if b:
                    backends.add(b)
        db = spec.get("defaultBackend", {}).get("service", {}).get("name")
        if db:
            backends.add(db)
        for b in backends:
            add_edge(nid, f"svc/{ns}/{b}", "routes")

    # pvcs (only those a workload mounts -> keeps the graph meaningful)
    mounted = {(wns, c) for _, wns, _, pvcs in workloads for c in pvcs}
    for item in kc("get", "pvc", "-A").get("items", []):
        ns = item["metadata"]["namespace"]
        name = item["metadata"]["name"]
        if (ns, name) not in mounted:
            continue
        nid = f"pvc/{ns}/{name}"
        spec = item.get("spec", {})
        cap = item.get("status", {}).get("capacity", {}).get("storage", "")
        meta = {"storageClass": spec.get("storageClassName", ""), "capacity": cap}
        add_node({"id": nid, "kind": "pvc", "name": name, "namespace": ns, "meta": meta, "status": "ok", "group": f"ns/{ns}"})
    for wid, wns, _, pvcs in workloads:
        for c in pvcs:
            add_edge(wid, f"pvc/{wns}/{c}", "mounts")

    # namespace group nodes + contains edges
    for ns in sorted(ns_with_content):
        nid = f"ns/{ns}"
        add_node({"id": nid, "kind": "namespace", "name": ns, "meta": {}, "status": "ok"})
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
