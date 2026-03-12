{{- define "shared-minio.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "shared-minio.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "shared-minio.labels" -}}
helm.sh/chart: {{ include "shared-minio.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "shared-minio.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: storage
{{- end }}

{{- define "shared-minio.selectorLabels" -}}
app.kubernetes.io/name: {{ include "shared-minio.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
