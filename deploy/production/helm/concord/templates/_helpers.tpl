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
