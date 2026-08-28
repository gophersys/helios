#!/usr/bin/env python3
"""
Build the unified per-cluster Eden observability dashboard (Grafana 12 schema-v2,
TabsLayout): one dashboard, six tabs (Overview / Compute / Networking / Storage /
Logs / Traces), progressive disclosure + cross-links. Reusable across clusters.

Env:
  GRAFANA_URL   e.g. http://10.168.0.241  or https://obsv.mateosegura.com
  GRAFANA_USER  default "admin"
  GRAFANA_PW    admin password
  PROM_UID      prometheus datasource uid   (homelab: prometheus | cloud: PBFA97CFB590B2093)
  LOKI_UID      loki datasource uid         (default "loki")
  TEMPO_UID     tempo datasource uid        (default "tempo")
  CLUSTER       display name e.g. "Home" / "Oracle"
  DASH_UID      dashboard uid e.g. "eden-home"
  FOLDER_UID    optional grafana folder uid
"""
import os, json, base64, urllib.request, urllib.error

URL = os.environ["GRAFANA_URL"].rstrip("/")
USER = os.environ.get("GRAFANA_USER", "admin")
PW = os.environ["GRAFANA_PW"]
PROM = os.environ.get("PROM_UID", "prometheus")
LOKI = os.environ.get("LOKI_UID", "loki")
TEMPO = os.environ.get("TEMPO_UID", "tempo")
CLUSTER = os.environ.get("CLUSTER", "Cluster")
DASH_UID = os.environ.get("DASH_UID", "eden-cluster")
FOLDER_UID = os.environ.get("FOLDER_UID", "")
HDR = {"Authorization": "Basic " + base64.b64encode((USER + ":" + PW).encode()).decode(),
       "Content-Type": "application/json"}
PV = "12.4.4"  # panel plugin schema version

_id = [0]
def nid():
    _id[0] += 1
    return _id[0]

def pq(expr, ds, group="prometheus", instant=False, legend="", refid="A", extra=None):
    spec = {"editorMode": "code", "expr": expr, "legendFormat": legend or "__auto",
            "range": not instant, "instant": instant}
    if extra:
        spec.update(extra)
    return {"kind": "PanelQuery", "spec": {"query": {"kind": "DataQuery", "group": group,
            "version": "v0", "datasource": {"name": ds}, "spec": spec}, "refId": refid, "hidden": False}}

def panel(title, viz, queries, opts=None, defaults=None, desc="", links=None):
    pid = nid()
    name = "panel-%d" % pid
    el = {"kind": "Panel", "spec": {"id": pid, "title": title, "description": desc,
          "links": links or [], "data": {"kind": "QueryGroup", "spec": {"queries": queries,
          "transformations": [], "queryOptions": {}}},
          "vizConfig": {"kind": "VizConfig", "group": viz, "version": PV,
          "spec": {"options": opts or {}, "fieldConfig": {"defaults": defaults or {}, "overrides": []}}}}}
    return name, el

def stat(title, expr, unit="none", color="value", graph="area", thresholds=None, desc="", links=None):
    d = {"unit": unit}
    if thresholds:
        d["thresholds"] = {"mode": "absolute", "steps": thresholds}
        d["color"] = {"mode": "thresholds"}
    o = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
         "colorMode": color, "graphMode": graph, "textMode": "auto", "orientation": "auto", "justifyMode": "auto"}
    return panel(title, "stat", [pq(expr, PROM, instant=True)], o, d, desc, links)

def gauge(title, expr, unit="percent", maxv=100, thresholds=None):
    d = {"unit": unit, "min": 0, "max": maxv}
    if thresholds:
        d["thresholds"] = {"mode": "absolute", "steps": thresholds}
    o = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "showThresholdLabels": False, "showThresholdMarkers": True}
    return panel(title, "gauge", [pq(expr, PROM, instant=True)], o, d)

def ts(title, series, unit="none", desc="", stack=False):
    qs = [pq(e, PROM, legend=lg, refid=chr(65 + i)) for i, (e, lg) in enumerate(series)]
    d = {"unit": unit, "custom": {"drawStyle": "line", "fillOpacity": 12, "showPoints": "never",
         "lineWidth": 1, "stacking": {"mode": "normal" if stack else "none"}}}
    o = {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["mean", "max"]},
         "tooltip": {"mode": "multi", "sort": "desc"}}
    return panel(title, "timeseries", qs, o, d, desc)

def table(title, expr, unit="none", desc=""):
    q = [pq(expr, PROM, instant=True)]
    o = {"showHeader": True, "cellHeight": "sm"}
    d = {"unit": unit, "custom": {"align": "auto", "filterable": True}}
    return panel(title, "table", q, o, d, desc)

def logs(title, expr, desc=""):
    q = [pq(expr, LOKI, group="loki")]
    o = {"showTime": True, "wrapLogMessage": False, "enableLogDetails": True, "dedupStrategy": "none", "sortOrder": "Descending"}
    return panel(title, "logs", q, o, {}, desc)

def gridify(elements):
    """2-up grid, width 12, height 8, in declaration order."""
    items = []
    for i, name in enumerate(elements):
        x = 0 if i % 2 == 0 else 12
        y = (i // 2) * 8
        items.append({"kind": "GridLayoutItem", "spec": {"x": x, "y": y, "width": 12, "height": 8,
                      "element": {"kind": "ElementReference", "name": name}}})
    return items

def kpi_row(elements):
    """6-up KPI strip: width 4, height 5, single row."""
    items = []
    for i, name in enumerate(elements):
        items.append({"kind": "GridLayoutItem", "spec": {"x": (i % 6) * 4, "y": (i // 6) * 5,
                      "width": 4, "height": 5, "element": {"kind": "ElementReference", "name": name}}})
    return items

ELEMENTS = {}
def add(t):
    name, el = t
    ELEMENTS[name] = el
    return name

# ---------------- OVERVIEW (KPIs + trends) ----------------
ov = []
ov.append(add(stat("Nodes Ready", 'sum(kube_node_status_condition{condition="Ready",status="true"})',
                   thresholds=[{"value": None, "color": "red"}, {"value": 1, "color": "green"}])))
ov.append(add(stat("Pods Running", 'sum(kube_pod_status_phase{phase="Running"})', color="value", graph="area")))
ov.append(add(stat("Pods Not-Running", 'sum(kube_pod_status_phase{phase=~"Failed|Pending|Unknown"})',
                   thresholds=[{"value": None, "color": "green"}, {"value": 1, "color": "orange"}, {"value": 5, "color": "red"}])))
ov.append(add(gauge("Cluster CPU", '100*(1-avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))',
                    thresholds=[{"value": None, "color": "green"}, {"value": 70, "color": "orange"}, {"value": 90, "color": "red"}])))
ov.append(add(gauge("Cluster Memory", '100*(1-sum(node_memory_MemAvailable_bytes)/sum(node_memory_MemTotal_bytes))',
                    thresholds=[{"value": None, "color": "green"}, {"value": 75, "color": "orange"}, {"value": 90, "color": "red"}])))
ov.append(add(stat("Network I/O", 'sum(rate(node_network_receive_bytes_total[5m]))+sum(rate(node_network_transmit_bytes_total[5m]))', unit="Bps")))
ov.append(add(ts("Cluster CPU / Memory utilisation",
                 [('100*(1-avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))', "CPU %"),
                  ('100*(1-sum(node_memory_MemAvailable_bytes)/sum(node_memory_MemTotal_bytes))', "Memory %")], unit="percent")))
ov.append(add(ts("Network throughput",
                 [('sum(rate(node_network_receive_bytes_total[5m]))', "RX"),
                  ('sum(rate(node_network_transmit_bytes_total[5m]))', "TX")], unit="Bps")))
OV_KPI = ov[:6]
OV_TREND = ov[6:]

# ---------------- COMPUTE ----------------
co = []
co.append(add(ts("CPU usage by node", [('100*(1-avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[5m])))', "{{instance}}")], unit="percent")))
co.append(add(ts("Memory usage by node", [('100*(1-node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)', "{{instance}}")], unit="percent")))
co.append(add(table("Top pods by CPU", 'topk(20, sum by(namespace,pod)(rate(container_cpu_usage_seconds_total{container!="",pod!=""}[5m])))', unit="none")))
co.append(add(table("Top pods by memory", 'topk(20, sum by(namespace,pod)(container_memory_working_set_bytes{container!="",pod!=""}))', unit="bytes")))
co.append(add(ts("Running pods by namespace", [('sum by(namespace)(kube_pod_status_phase{phase="Running"})', "{{namespace}}")], stack=True)))
co.append(add(ts("Container restarts (rate)", [('sum by(namespace)(rate(kube_pod_container_status_restarts_total[15m]))', "{{namespace}}")])))

# ---------------- NETWORKING ----------------
ne = []
ne.append(add(ts("Cluster network RX / TX", [('sum(rate(node_network_receive_bytes_total[5m]))', "RX"), ('sum(rate(node_network_transmit_bytes_total[5m]))', "TX")], unit="Bps")))
ne.append(add(ts("Receive by namespace", [('sum by(namespace)(rate(container_network_receive_bytes_total[5m]))', "{{namespace}}")], unit="Bps", stack=True)))
ne.append(add(ts("Transmit by namespace", [('sum by(namespace)(rate(container_network_transmit_bytes_total[5m]))', "{{namespace}}")], unit="Bps", stack=True)))
ne.append(add(ts("Network errors / drops", [('sum(rate(node_network_receive_errs_total[5m]))+sum(rate(node_network_transmit_errs_total[5m]))', "errors"), ('sum(rate(node_network_receive_drop_total[5m]))+sum(rate(node_network_transmit_drop_total[5m]))', "drops")])))
ne.append(add(ts("CoreDNS query rate", [('sum by(type)(rate(coredns_dns_requests_total[5m]))', "{{type}}")], unit="reqps", desc="Empty if CoreDNS metrics aren't scraped.")))
ne.append(add(ts("CoreDNS failures", [('sum(rate(coredns_dns_responses_total{rcode=~"SERVFAIL|REFUSED"}[5m]))', "failures")], unit="reqps")))

# ---------------- STORAGE ----------------
st = []
st.append(add(table("Volume usage %", '100*sum by(namespace,persistentvolumeclaim)(kubelet_volume_stats_used_bytes)/sum by(namespace,persistentvolumeclaim)(kubelet_volume_stats_capacity_bytes)', unit="percent")))
st.append(add(table("Volume used / capacity", 'sum by(namespace,persistentvolumeclaim)(kubelet_volume_stats_used_bytes)', unit="bytes")))
st.append(add(ts("Total volume available", [('sum(kubelet_volume_stats_available_bytes)', "available")], unit="bytes")))
st.append(add(stat("PVCs bound", 'sum(kube_persistentvolumeclaim_status_phase{phase="Bound"})')))

# ---------------- LOGS ----------------
lo = []
lo.append(add(ts("Log volume by namespace", [], unit="none")))  # replaced below with loki query
# build loki ts manually (loki query group)
_n = lo[-1]
ELEMENTS[_n]["spec"]["data"]["spec"]["queries"] = [pq('sum by(namespace)(count_over_time({namespace=~".+"}[5m]))', LOKI, group="loki", legend="{{namespace}}")]
lo.append(add(stat("Error log rate (5m)", "", desc="")))
_e = lo[-1]
ELEMENTS[_e]["spec"]["data"]["spec"]["queries"] = [pq('sum(count_over_time({namespace=~".+"} |~ `(?i)(error|fail|panic|fatal)`[5m]))', LOKI, group="loki", instant=True)]
ELEMENTS[_e]["spec"]["vizConfig"]["spec"]["fieldConfig"]["defaults"] = {"unit": "none", "color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"value": None, "color": "green"}, {"value": 1, "color": "orange"}, {"value": 50, "color": "red"}]}}
lo.append(add(logs("Live logs", '{namespace=~".+"}')))

# ---------------- TRACES ----------------
tr = []
_n, _el = panel("Recent traces", "table",
                [{"kind": "PanelQuery", "spec": {"query": {"kind": "DataQuery", "group": "tempo", "version": "v0",
                  "datasource": {"name": TEMPO}, "spec": {"queryType": "traceqlSearch", "limit": 20, "filters": []}}, "refId": "A", "hidden": False}}],
                desc="Apps send OTLP to alloy-gateway.observability.svc:4318 (gRPC 4317).")
ELEMENTS[_n] = _el
tr.append(_n)

# ---------------- assemble tabs ----------------
def tab(title, items):
    return {"kind": "TabsLayoutTab", "spec": {"title": title, "layout": {"kind": "GridLayout", "spec": {"items": items}}}}

overview_items = kpi_row(OV_KPI) + [
    {"kind": "GridLayoutItem", "spec": {"x": 0, "y": 5, "width": 12, "height": 8, "element": {"kind": "ElementReference", "name": OV_TREND[0]}}},
    {"kind": "GridLayoutItem", "spec": {"x": 12, "y": 5, "width": 12, "height": 8, "element": {"kind": "ElementReference", "name": OV_TREND[1]}}},
]

tabs = [
    tab("Overview", overview_items),
    tab("Compute", gridify(co)),
    tab("Networking", gridify(ne)),
    tab("Storage", gridify(st)),
    tab("Logs", gridify(lo)),
    tab("Traces", gridify(tr)),
]

variables = [{"kind": "QueryVariable", "spec": {"name": "namespace", "current": {"text": "All", "value": "$__all"},
             "hide": "dontHide", "refresh": "onDashboardLoad", "skipUrlSync": False,
             "query": {"kind": "DataQuery", "group": "prometheus", "version": "v0", "datasource": {"name": PROM},
                       "spec": {"query": "label_values(kube_pod_info, namespace)", "refId": "A"}},
             "regex": "", "sort": "alphabeticalAsc", "definition": "label_values(kube_pod_info, namespace)",
             "options": [], "multi": True, "includeAll": True, "allowCustomValue": False}}]

spec = {"title": "Eden / %s" % CLUSTER, "description": "Unified observability for the %s cluster." % CLUSTER,
        "editable": True, "cursorSync": "Crosshair", "liveNow": False, "preload": False,
        "tags": ["eden", "cluster", CLUSTER.lower()], "links": [], "annotations": [],
        "timeSettings": {"timezone": "", "from": "now-1h", "to": "now", "autoRefresh": "30s",
                         "autoRefreshIntervals": ["10s", "30s", "1m", "5m", "15m", "1h"],
                         "hideTimepicker": False, "fiscalYearStartMonth": 0},
        "variables": variables, "elements": ELEMENTS,
        "layout": {"kind": "TabsLayout", "spec": {"tabs": tabs}}}

meta = {"name": DASH_UID, "namespace": "default"}
if FOLDER_UID:
    meta["annotations"] = {"grafana.app/folder": FOLDER_UID}
body = json.dumps({"apiVersion": "dashboard.grafana.app/v2beta1", "kind": "Dashboard", "metadata": meta, "spec": spec}).encode()

# upsert: try POST, fall back to PUT on 409
base = URL + "/apis/dashboard.grafana.app/v2beta1/namespaces/default/dashboards"
try:
    r = urllib.request.urlopen(urllib.request.Request(base, data=body, headers=HDR, method="POST"), timeout=30)
    print("CREATED", r.status, "panels:", len(ELEMENTS))
except urllib.error.HTTPError as e:
    if e.code == 409:
        r = urllib.request.urlopen(urllib.request.Request(base + "/" + DASH_UID, data=body, headers=HDR, method="PUT"), timeout=30)
        print("UPDATED", r.status, "panels:", len(ELEMENTS))
    else:
        print("FAILED", e.code, e.read().decode()[:800])
        raise
