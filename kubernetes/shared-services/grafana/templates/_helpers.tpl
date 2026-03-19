{{- define "shared-grafana.name" -}}
grafana
{{- end -}}

{{- define "shared-grafana.fullname" -}}
grafana
{{- end -}}

{{- define "shared-grafana.labels" -}}
app: grafana
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "shared-grafana.selectorLabels" -}}
app: grafana
{{- end -}}
