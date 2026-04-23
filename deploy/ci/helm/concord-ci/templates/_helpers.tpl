{{/*
Common labels for all concord-ci resources.
*/}}
{{- define "concord-ci.labels" -}}
app.kubernetes.io/part-of: concord-ci
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
MinIO selector labels.
*/}}
{{- define "concord-ci.minio.selectorLabels" -}}
app.kubernetes.io/name: concord-ci-minio
app.kubernetes.io/component: storage
{{- end }}

{{/*
Admin dashboard selector labels.
*/}}
{{- define "concord-ci.admin.selectorLabels" -}}
app.kubernetes.io/name: concord-ci-admin
app.kubernetes.io/component: dashboard
{{- end }}

{{/*
Nightly CronJob labels.
*/}}
{{- define "concord-ci.nightly.labels" -}}
app.kubernetes.io/name: concord-ci-nightly
app.kubernetes.io/component: ci-runner
{{- end }}

{{/*
Weekly CronJob labels.
*/}}
{{- define "concord-ci.weekly.labels" -}}
app.kubernetes.io/name: concord-ci-weekly
app.kubernetes.io/component: ci-runner
{{- end }}

{{/*
Node selector — all CI workloads run on the devops node.
*/}}
{{- define "concord-ci.nodeSelector" -}}
nodeSelector:
  {{- toYaml .Values.global.nodeSelector | nindent 2 }}
{{- end }}

{{/*
CI MinIO internal endpoint.
*/}}
{{- define "concord-ci.minioEndpoint" -}}
http://concord-ci-minio:{{ .Values.minio.port }}
{{- end }}
