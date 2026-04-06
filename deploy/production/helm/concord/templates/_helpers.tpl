{{/*
Common labels
*/}}
{{- define "concord.labels" -}}
app.kubernetes.io/part-of: concord
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Backend selector labels
*/}}
{{- define "concord.httpApi.selectorLabels" -}}
app.kubernetes.io/name: concord-http-api
app.kubernetes.io/component: backend
{{- end }}

{{/*
Frontend selector labels
*/}}
{{- define "concord.frontend.selectorLabels" -}}
app.kubernetes.io/name: concord-frontend
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Workload node selector — places pods on nodes matching a workload type.
Uses concord.corekinect.com/workload-<type>=true so multi-role nodes
are matched (e.g., a node with workload-platform=true AND workload-worker=true).

Usage: {{ include "concord.workloadNodeSelector" (dict "workload" "platform" "extra" .Values.httpApi.nodeSelector) }}
*/}}
{{- define "concord.workloadNodeSelector" -}}
{{- if .workload }}
nodeSelector:
  concord.corekinect.com/workload-{{ .workload }}: "true"
  {{- with .extra }}
  {{- toYaml . | nindent 2 }}
  {{- end }}
{{- else if .extra }}
nodeSelector:
  {{- toYaml .extra | nindent 2 }}
{{- end }}
{{- end }}
