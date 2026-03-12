{{/*
Expand the name of the chart.
*/}}
{{- define "shared-clickhouse.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "shared-clickhouse.fullname" -}}
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

{{/*
Common labels
*/}}
{{- define "shared-clickhouse.labels" -}}
helm.sh/chart: {{ include "shared-clickhouse.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "shared-clickhouse.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: database
{{- end }}

{{/*
Selector labels
*/}}
{{- define "shared-clickhouse.selectorLabels" -}}
app.kubernetes.io/name: {{ include "shared-clickhouse.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
