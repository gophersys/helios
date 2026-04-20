{{/*
  _common/templates/_helpers.tpl — shared template helpers.

  STATUS: stubs. Function signatures are committed so archetypes can
  reference them; bodies land when the first archetype is implemented
  end-to-end.

  See charts/_common/README.md for the helper catalog.
*/}}

{{/*
  common.labels: canonical label set applied to every rendered object.
  See charts/CONVENTIONS.md §2 for the full list. The composite
  identifier <project>-<app.name> is the app.kubernetes.io/name.
*/}}
{{- define "common.labels" -}}
# TODO: implement. Emit the full canonical label set from values.
# Expected (abridged):
#   app.kubernetes.io/name:       {{ .Values.project }}-{{ .Values.app.name }}
#   app.kubernetes.io/part-of:    {{ .Values.project }}
#   platform.gophersys/project:   {{ .Values.project }}
#   platform.gophersys/app:       {{ .Values.app.name }}
#   platform.gophersys/env:       {{ .Values.env }}
app.kubernetes.io/name: {{ printf "%s-%s" .Values.project .Values.app.name | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service | quote }}
{{- end }}

{{/*
  common.selectorLabels: subset of common.labels suitable for
  selectors. Must be immutable across upgrades.
*/}}
{{- define "common.selectorLabels" -}}
# TODO: implement.
app.kubernetes.io/name: {{ printf "%s-%s" .Values.project .Values.app.name | quote }}
app.kubernetes.io/instance: {{ .Release.Name | quote }}
{{- end }}

{{/*
  common.fullname: canonical identifier for the app. Equal to
  <project>-<app.name>. Use as the default release name and as the
  base for all resource names (Deployment, Service, etc.).
*/}}
{{- define "common.fullname" -}}
{{ printf "%s-%s" .Values.project .Values.app.name }}
{{- end }}

{{/*
  common.namespace: expected namespace name for this app, derived
  from project + env. Templates MAY render a check that fails if
  .Release.Namespace does not equal this value.
*/}}
{{- define "common.namespace" -}}
{{ printf "%s-%s" .Values.project .Values.env }}
{{- end }}

{{/*
  common.podSecurityContext: restricted PSS pod-level security context.
  See charts/CONVENTIONS.md §3.
*/}}
{{- define "common.podSecurityContext" -}}
# TODO: implement.
runAsNonRoot: true
{{- end }}

{{/*
  common.containerSecurityContext: restricted PSS container-level context.
*/}}
{{- define "common.containerSecurityContext" -}}
# TODO: implement.
allowPrivilegeEscalation: false
{{- end }}

{{/*
  common.externalSecret: emit one ExternalSecret per entry in
  values.secrets[]. Consuming template invokes this inside a range.
*/}}
{{- define "common.externalSecret" -}}
# TODO: implement.
{{- end }}

{{/*
  common.networkPolicy.baseline: emit the four baseline NetworkPolicy
  resources (deny-all + DNS + same-ns + metrics scrape).
*/}}
{{- define "common.networkPolicy.baseline" -}}
# TODO: implement.
{{- end }}

{{/*
  common.serviceMonitor: emit a ServiceMonitor from
  values.observability.metrics.
*/}}
{{- define "common.serviceMonitor" -}}
# TODO: implement.
{{- end }}

{{/*
  common.slo.recordingRules: emit a PrometheusRule with availability +
  latency recording rules from values.slo.
*/}}
{{- define "common.slo.recordingRules" -}}
# TODO: implement.
{{- end }}

{{/*
  common.pdb: emit a PodDisruptionBudget with archetype-aware defaults.
  Caller passes archetype context via dict.
*/}}
{{- define "common.pdb" -}}
# TODO: implement.
{{- end }}
